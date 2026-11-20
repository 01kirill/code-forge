import asyncio
import csv
import io
import os
import time
from uuid import uuid4

import httpx
import pytest
from codeforge.common.broker import Document

pytestmark = pytest.mark.integration
BASE = os.getenv("CODEFORGE_TEST_URL")
DEMO = os.getenv("CODEFORGE_DEMO_PASSWORD")
ADMIN = os.getenv("CODEFORGE_TEST_ADMIN")
ADMIN_PASSWORD = os.getenv("CODEFORGE_ADMIN_PASSWORD")
SOLUTION = "print(sum(map(int, input().split())))"


def client() -> httpx.AsyncClient:
    if not BASE:
        pytest.skip("Set CODEFORGE_TEST_URL to the fixture stack")
    return httpx.AsyncClient(base_url=BASE, timeout=15)


async def post_json(
    http: httpx.AsyncClient,
    path: str,
    data: Document,
    status: int,
) -> Document:
    response = await http.post(f"/api{path}", json=data)
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


async def get(http: httpx.AsyncClient, path: str) -> Document:
    response = await http.get(f"/api{path}")
    assert response.status_code == 200, response.text
    return response.json()


async def login(http: httpx.AsyncClient, email: str, password: str) -> None:
    response = await post_json(
        http, "/auth/login", {"email": email, "password": password}, 200
    )
    http.headers["Authorization"] = f"Bearer {response['access_token']}"


async def student(http: httpx.AsyncClient) -> tuple[str, str]:
    name = "u_" + uuid4().hex[:10]
    email, password = f"{name}@example.com", "Testing-Only42"
    await post_json(
        http,
        "/auth/register",
        {"email": email, "name": name, "password": password},
        201,
    )
    await login(http, email, password)
    return email, password


async def await_result(http: httpx.AsyncClient, path: str) -> Document:
    async with asyncio.timeout(12):
        while True:
            doc = await get(http, path)
            if doc["state"] == "done":
                return doc["result"]
            await asyncio.sleep(0.2)


async def test_registration_and_refresh_reuse() -> None:
    async with client() as first, client() as second:
        email, password = await student(first)
        name = (await get(first, "/auth/me"))["name"]
        await post_json(
            first,
            "/auth/register",
            {
                "name": name.upper(),
                "email": email.upper(),
                "password": password,
            },
            409,
        )
        await login(second, email, password)
        old = first.cookies.get("cf_refresh")
        assert old
        rotated = await post_json(first, "/auth/refresh", {}, 200)
        assert first.cookies.get("cf_refresh") != old
        first.headers["Authorization"] = f"Bearer {rotated['access_token']}"
        assert (await get(first, "/auth/me"))["name"] == name
        first.cookies.clear()
        first.cookies.set("cf_refresh", old, path="/api/auth")
        assert (await post_json(first, "/auth/refresh", {}, 401))[
            "code"
        ] == "session_reused"
        assert (await second.post("/api/auth/refresh")).status_code == 401
        assert (await second.get("/api/edu/me/profile")).status_code == 401


async def test_gaming_profile_and_gradebook() -> None:
    if not DEMO:
        pytest.skip("Seed the demo catalog and set CODEFORGE_DEMO_PASSWORD")
    async with client() as learner, client() as teacher, client() as stranger:
        courses = (await learner.get("/api/edu/courses")).json()
        assert {row["slug"] for row in courses} >= {"python-basics", "cpp-start"}
        assert (
            await learner.get("/api/edu/courses/algorithms-draft")
        ).status_code == 404
        await student(learner)
        doc = await get(learner, "/edu/courses/python-basics")
        lessons = [lesson for module in doc["modules"] for lesson in module["lessons"]]
        theory, quiz, multiquiz, practice = [row["id"] for row in lessons]
        assert (await learner.get(f"/api/edu/lessons/{theory}")).status_code == 403
        await post_json(learner, "/edu/courses/python-basics/enroll", {}, 204)
        await post_json(learner, "/edu/courses/python-basics/enroll", {}, 204)
        await post_json(learner, f"/edu/lessons/{theory}/complete", {}, 200)
        await post_json(learner, f"/edu/lessons/{theory}/complete", {}, 200)
        details = await get(learner, f"/edu/lessons/{quiz}")
        assert "correct" not in details["questions"][0]
        assert not (
            await post_json(
                learner, f"/edu/lessons/{quiz}/quiz", {"answers": [[0]]}, 200
            )
        )["passed"]
        assert (
            await post_json(
                learner, f"/edu/lessons/{quiz}/quiz", {"answers": [[1]]}, 200
            )
        )["passed"]
        assert (
            await post_json(
                learner,
                f"/edu/lessons/{multiquiz}/quiz",
                {"answers": [[1, 0]]},
                200,
            )
        )["passed"]
        task = (await get(learner, f"/edu/lessons/{practice}"))["task"]
        assert "tests" not in task and len(task["examples"]) == 1
        endpoint = f"/edu/tasks/{task['task_id']}"
        payload = {"language": "python", "lesson_id": practice}
        run = await post_json(
            learner, f"{endpoint}/run", payload | {"code": SOLUTION}, 202
        )
        assert (await await_result(learner, f"/edu/submissions/{run['id']}"))[
            "verdict"
        ] == "AC"
        assert (await learner.get(f"/api{endpoint}/submissions")).json() == []
        assert (await get(learner, "/edu/me/profile"))["xp"] == 30
        wrong = await post_json(
            learner, f"{endpoint}/submissions", payload | {"code": "print(0)"}, 202
        )
        await post_json(
            learner, f"{endpoint}/submissions", payload | {"code": SOLUTION}, 429
        )
        assert (await await_result(learner, f"/edu/submissions/{wrong['id']}"))[
            "verdict"
        ] == "WA"
        await asyncio.sleep(3)
        right = await post_json(
            learner, f"{endpoint}/submissions", payload | {"code": SOLUTION}, 202
        )
        assert (await await_result(learner, f"/edu/submissions/{right['id']}"))[
            "verdict"
        ] == "AC"
        assert (await get(learner, "/edu/me/profile"))["xp"] == 60
        assert (await get(learner, f"/edu/submissions/{right['id']}"))[
            "code"
        ] == SOLUTION
        await student(stranger)
        assert (
            await stranger.get(f"/api/edu/submissions/{right['id']}")
        ).status_code == 404
        assert (
            await stranger.get("/api/edu/courses/python-basics/gradebook")
        ).status_code == 403

        await login(teacher, "teacher@example.com", DEMO)
        table = await get(teacher, "/edu/courses/python-basics/gradebook")
        learner_id = (await get(learner, "/auth/me"))["id"]
        row = next(row for row in table["rows"] if row["id"] == learner_id)
        assert row["percent"] == 100 and row["cells"][-1]["task_xp"] == 20
        download = await teacher.get(
            "/api/edu/courses/python-basics/gradebook?format=csv"
        )
        csv_rows = list(csv.reader(io.StringIO(download.text.lstrip("\ufeff"))))
        assert [list(r.values())[1] for r in table["rows"]] == [
            row[0] for row in csv_rows[1:]
        ]


async def test_contest_membership_clock_and_private_result() -> None:
    if not DEMO:
        pytest.skip("Seed the demo catalog and set CODEFORGE_DEMO_PASSWORD")
    async with client() as owner, client() as guest, client() as outsider:
        await student(owner)
        await student(guest)
        bank = (await owner.get("/api/edu/contest-tasks")).json()
        assert len(bank) >= 2 and all("statement" not in row for row in bank)
        room = await post_json(
            owner,
            "/contest/contests",
            {
                "title": "Integration room",
                "duration": 5,
                "description": "",
            },
            201,
        )
        base = f"/contest/contests/{room['id']}"
        first = room["invite"]
        renewed = await post_json(owner, f"{base}/invite", {}, 200)
        assert len(first) == len(renewed["invite"]) == 22
        await post_json(guest, f"/contest/join/{first}", {}, 404)
        await post_json(guest, f"/contest/join/{renewed['invite']}", {}, 200)
        await post_json(guest, f"/contest/join/{renewed['invite']}", {}, 200)
        assert len((await get(owner, base))["participants"]) == 2
        body = {
            "task_ids": [
                next(
                    row["task_id"] for row in bank if row["title"] == "Сумма двух чисел"
                ),
            ]
        }
        assert (await owner.put(f"/api{base}/problems", json=body)).status_code == 200
        assert (await guest.get(f"/api{base}/problems")).status_code == 403
        await post_json(guest, f"{base}/start", {}, 403)
        started = await post_json(owner, f"{base}/start", {}, 200)
        assert started["state"] == "countdown"
        assert (await post_json(owner, f"{base}/start", {}, 200))[
            "start_at"
        ] == started["start_at"]
        await student(outsider)
        assert (await outsider.get(f"/api{base}/standings")).status_code == 403
        endpoint = f"{base}/problems/A/submissions"
        payload = {"language": "python", "code": SOLUTION}
        if (await get(owner, base))["state"] == "countdown":
            await post_json(owner, endpoint, payload, 409)
        deadline = time.monotonic() + 12
        while (await get(guest, base))["state"] == "countdown":
            assert time.monotonic() < deadline
            await asyncio.sleep(0.25)
        saved = await post_json(owner, endpoint, payload, 202)
        assert (await await_result(owner, f"{base}/submissions/{saved['id']}"))[
            "verdict"
        ] == "AC"
        assert (
            await guest.get(f"/api{base}/submissions/{saved['id']}")
        ).status_code == 404
        owner_board, guest_board = await asyncio.gather(
            get(owner, f"{base}/standings"),
            get(guest, f"{base}/standings"),
        )
        assert owner_board == guest_board and owner_board["rows"][0]["solved"] == 1


async def test_role_update_revokes_protected_actions() -> None:
    if not ADMIN or not ADMIN_PASSWORD:
        pytest.skip("Set CODEFORGE_TEST_ADMIN and CODEFORGE_ADMIN_PASSWORD")
    async with client() as admin, client() as account:
        email, password = await student(account)
        id_ = (await get(account, "/auth/me"))["id"]
        await login(admin, ADMIN, ADMIN_PASSWORD)
        endpoint = f"/api/auth/users/{id_}/role"
        assert (
            await account.patch(endpoint, json={"role": "teacher"})
        ).status_code == 403
        assert (
            await admin.patch(endpoint, json={"role": "teacher"})
        ).status_code == 200
        assert (await account.get("/api/edu/me/courses")).status_code == 200
        assert (
            await admin.patch(endpoint, json={"role": "student"})
        ).status_code == 200
        assert (await account.get("/api/edu/me/courses")).status_code == 403
        assert (await admin.patch(endpoint, json={"active": False})).status_code == 200
        assert (await account.get("/api/edu/me/profile")).status_code == 403
        assert (await account.post("/api/auth/refresh")).status_code == 401
        assert (
            await account.post(
                "/api/auth/login",
                json={
                    "email": email,
                    "password": password,
                },
            )
        ).status_code == 403
