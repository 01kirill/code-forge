from dataclasses import dataclass

from codeforge.common.contracts import Document
from codeforge.education.domain import Verdict

HINTS = {
    "indentationerror": "Проверьте отступы в блоках кода.",
    "nameerror": "Проверьте имя переменной и где она была объявлена.",
    "was not declared": "Объявите переменную перед использованием.",
    "zerodivisionerror": "Проверьте, что делитель не равен нулю.",
    "indexerror": "Проверьте границы индекса.",
}


@dataclass(frozen=True)
class Case:
    stdin: str
    expected: str | None
    public: bool


@dataclass(frozen=True)
class Execution:
    verdict: Verdict
    time_ms: int = 0
    memory_kb: int = 0
    stdout: str = ""
    diagnostic: str = ""


def aggregate(cases: list[Case], rows: list[Execution]) -> Document:
    if len(cases) != len(rows) or not rows:
        return technical()
    kinds = [row.verdict for row in rows]
    if Verdict.TECHNICAL in kinds:
        return technical()
    first = next(
        (index for index, kind in enumerate(kinds) if kind != Verdict.AC), None
    )
    kind = Verdict.AC if first is None else kinds[first]
    details: list[Document] = []
    for index, (case, row, outcome) in enumerate(zip(cases, rows, kinds, strict=True)):
        if not case.public and index != first:
            continue
        info: Document = {
            "number": index + 1,
            "public": case.public,
            "verdict": outcome,
        }
        if case.public:
            raw = row.diagnostic
            info.update(
                stdin=case.stdin,
                expected=case.expected,
                stdout=row.stdout,
                diagnostic=raw,
                hint=next(
                    (value for needle, value in HINTS.items() if needle in raw.lower()),
                    None,
                ),
            )
        elif outcome == Verdict.RE:
            info["hint"] = "Проверьте обработку граничных входных данных."
        details.append(info)
    return {
        "verdict": kind,
        "passed": kinds.count(Verdict.AC),
        "total": len(rows),
        "first_failed": None if first is None else first + 1,
        "time_ms": max(row.time_ms for row in rows),
        "memory_kb": max(row.memory_kb for row in rows),
        "details": details,
    }


def technical() -> Document:
    return {
        "verdict": Verdict.TECHNICAL,
        "passed": 0,
        "total": 0,
        "details": [],
        "first_failed": None,
        "time_ms": None,
        "memory_kb": None,
    }
