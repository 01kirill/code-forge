import asyncio
import base64
import binascii
from typing import Any

import httpx

from codeforge.common.contracts import JUDGE_LANGUAGES, Document
from codeforge.education.application.ports import JudgeUnavailable
from codeforge.education.domain import Verdict
from codeforge.education.domain.verdicts import Case, Execution

TERMINAL_STATUS = {
    3: Verdict.AC,
    4: Verdict.WA,
    5: Verdict.TLE,
    6: Verdict.CE,
    7: Verdict.RE,
    8: Verdict.RE,
    9: Verdict.RE,
    10: Verdict.RE,
    11: Verdict.RE,
    12: Verdict.RE,
}


def encode(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def decode(value: str | None) -> str:
    try:
        return base64.b64decode(value or "").decode(errors="replace")[:16384]
    except (ValueError, binascii.Error):
        return ""


def verdict(row: Document) -> Verdict:
    status = row["status"]["id"]
    if row.get("limit_reason") == "cgroup_oom_kill" and status in range(7, 13):
        return Verdict.MLE
    return TERMINAL_STATUS.get(status, Verdict.TECHNICAL)


def execution(row: Document) -> Execution:
    outcome = verdict(row)
    if outcome == Verdict.TECHNICAL:
        return Execution(outcome)
    return Execution(
        outcome,
        round(float(row.get("time") or 0) * 1000),
        int(row.get("memory") or 0),
        decode(row.get("stdout")),
        decode(row.get("compile_output") or row.get("stderr")),
    )


class Judge:
    def __init__(
        self, client: httpx.AsyncClient, *, trusted_limits: bool = False
    ) -> None:
        self.client = client
        self.languages: dict[str, int] = {}
        self.trusted_limits = trusted_limits

    async def request(self, method: str, url: str, **options: Any) -> httpx.Response:
        delay = 0.15
        for attempt in range(4):
            try:
                response = await self.client.request(method, url, **options)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise JudgeUnavailable from exc
                if attempt == 3:
                    raise JudgeUnavailable from exc
            except httpx.RequestError as exc:
                if (
                    attempt == 3
                    or method == "POST"
                    and not isinstance(exc, httpx.ConnectError)
                ):
                    raise JudgeUnavailable from exc
            await asyncio.sleep(delay)
            delay *= 2
        raise JudgeUnavailable

    async def start(
        self,
        task: Document,
        language: str,
        code: str,
        cases: list[Case],
    ) -> list[str]:
        if language not in self.languages:
            response = await self.request("GET", "/languages")
            available = {entry["name"]: entry["id"] for entry in response.json()}
            self.languages = {
                key: available[spec["name"]]
                for key, spec in JUDGE_LANGUAGES.items()
                if spec["name"] in available
            }
        if language not in self.languages:
            raise JudgeUnavailable
        time_limit = task["time_ms"] / 1000
        base = {
            "language_id": self.languages[language],
            "source_code": encode(code),
            "cpu_time_limit": time_limit,
            "wall_time_limit": max(2, time_limit + 2),
            "memory_limit": task["memory_kb"],
            "max_processes_and_or_threads": 60,
            "max_file_size": 128,
            "enable_network": False,
        }
        response = await self.request(
            "POST",
            "/submissions/batch",
            params={"base64_encoded": "true"},
            json={
                "submissions": [
                    base
                    | {"stdin": encode(case.stdin)}
                    | (
                        {"expected_output": encode(case.expected)}
                        if case.expected is not None
                        else {}
                    )
                    for case in cases
                ]
            },
        )
        tokens = [entry.get("token") for entry in response.json()]
        if len(tokens) != len(cases) or not all(
            isinstance(token, str) for token in tokens
        ):
            raise JudgeUnavailable
        return tokens

    async def collect(self, tokens: list[str]) -> list[Execution]:
        results: dict[str, Document] = {}
        fields = "token,status,stdout,stderr,compile_output,time,memory"
        if self.trusted_limits:
            fields += ",limit_reason"
        while len(results) < len(tokens):
            pending = [token for token in tokens if token not in results]
            response = await self.request(
                "GET",
                "/submissions/batch",
                params={
                    "tokens": ",".join(pending),
                    "base64_encoded": "true",
                    "fields": fields,
                },
            )
            for row in response.json()["submissions"]:
                if row and row.get("token") in pending and row["status"]["id"] > 2:
                    if not self.trusted_limits:
                        row.pop("limit_reason", None)
                    results[row["token"]] = row
            if len(results) < len(tokens):
                await asyncio.sleep(0.2)
        return [execution(results[token]) for token in tokens]
