"""Populate the demo catalog using the same API as the browser."""

import argparse
import asyncio
import os
from typing import Any

import httpx
from codeforge.common.broker import Document

PY_TEMPLATE = (
    "# Прочитайте два числа и выведите ответ.\na, b = map(int, input().split())\n"
)
CPP_TEMPLATE = (
    "#include <iostream>\n\nint main() {\n"
    "    int a, b;\n    std::cin >> a >> b;\n    // Выведите ответ.\n}\n"
)
ACCOUNTS = (
    ("teacher@example.com", "demo_teacher"),
    ("student1@example.com", "demo_alina"),
    ("student2@example.com", "demo_denis"),
    ("author2@example.com", "demo_author"),
)


async def call(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> Any:
    response = await client.request(method, f"/api{path}", **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json() if response.status_code != 204 else None


async def login(client: httpx.AsyncClient, email: str, password: str) -> None:
    pair = await call(
        client, "POST", "/auth/login", json={"email": email, "password": password}
    )
    client.headers["Authorization"] = f"Bearer {pair['access_token']}"


async def task(
    client: httpx.AsyncClient,
    title: str,
    statement: str,
    operation: str,
    contest: bool,
) -> str:
    existing = await call(client, "GET", "/edu/tasks")
    for item in existing:
        if item["title"] == title:
            return str(item["task_id"])
    pairs = [
        (2, 3),
        (-5, -8),
        (0, 0),
        (1, -1),
        (8, 11),
        (99, -10),
        (-1, 110),
        (12, 3),
        (5, 5),
        (6, 8),
    ]
    if operation == "max":
        pairs = pairs[:3]
    doc = await call(
        client,
        "POST",
        "/edu/tasks",
        json={
            "title": title,
            "statement": statement,
            "difficulty": "easy",
            "templates": {"python": PY_TEMPLATE, "cpp": CPP_TEMPLATE},
            "time_ms": 1000,
            "memory_kb": 65536,
            "contest_ready": contest,
            "tests": [
                {
                    "stdin": f"{a} {b}\n",
                    "expected": f"{max(a, b) if operation == 'max' else a + b}\n",
                    "public": index == 0,
                }
                for index, (a, b) in enumerate(pairs)
            ],
        },
    )
    return str(doc["task_id"])


async def course(
    client: httpx.AsyncClient,
    slug: str,
    title: str,
    description: str,
    language: str,
    lessons: list[Document],
    *,
    publish: bool = True,
) -> None:
    existing = await call(client, "GET", "/edu/me/courses")
    present = next((item for item in existing if item["slug"] == slug), None)
    if present is not None and (present["published"] or not publish):
        return
    topics = ["Основы", "Ввод и вывод"]
    modules: list[Document] = [{"title": topic, "lessons": []} for topic in topics]
    spec = {
        "slug": slug,
        "title": title,
        "description": description,
        "language": language,
        "topics": topics,
        "modules": modules,
        "published": False,
    }
    if present is None:
        detail = await call(client, "POST", "/edu/courses", json=spec)
    else:
        detail = await call(client, "GET", f"/edu/courses/{slug}?author=true")
    for index, group in enumerate(detail["modules"]):
        modules[index]["lessons"] = [item["id"] for item in group["lessons"]]
    seen = {item["title"] for group in detail["modules"] for item in group["lessons"]}
    for lesson in lessons:
        if lesson["title"] in seen:
            continue
        index = topics.index(lesson["topic"])
        added = await call(
            client,
            "POST",
            "/edu/lessons",
            json={
                "course_slug": slug,
                "module": index,
                "lesson": lesson,
            },
        )
        modules[index]["lessons"].append(added["id"])
    if publish:
        detail = await call(client, "GET", f"/edu/courses/{slug}?author=true")
        await call(
            client,
            "PATCH",
            f"/edu/courses/{slug}",
            headers={"If-Match": f'"{detail["revision"]}"'},
            json=spec | {"published": True},
        )


async def seed(url: str, admin: str, password: str, demo_password: str) -> None:
    async with httpx.AsyncClient(base_url=url, timeout=15) as client:
        await login(client, admin, password)
        for email, name in ACCOUNTS:
            response = await client.post(
                "/api/auth/register",
                json={
                    "name": name,
                    "email": email,
                    "password": demo_password,
                },
            )
            if response.status_code not in (201, 409):
                response.raise_for_status()
            if email in ("teacher@example.com", "author2@example.com"):
                users = await call(client, "GET", "/auth/users", params={"q": email})
                found = next(user for user in users if user["email"] == email)
                if found["role"] == "student":
                    await call(
                        client,
                        "PATCH",
                        f"/auth/users/{found['id']}/role",
                        json={"role": "teacher"},
                    )

        await login(client, "teacher@example.com", demo_password)
        sum_id = await task(
            client,
            "Сумма двух чисел",
            "Даны два целых числа на одной строке. Выведите их сумму.\n\n"
            "Каждое число лежит в диапазоне от −1000 до 1000.",
            "sum",
            True,
        )
        await task(
            client,
            "Большее из двух чисел",
            "Прочитайте два целых числа и выведите большее из них.",
            "max",
            True,
        )
        class_id = await task(
            client,
            "Сложение для разминки",
            "Прочитайте два целых числа и выведите сумму.",
            "sum",
            False,
        )
        await course(
            client,
            "python-basics",
            "Python с нуля",
            "Переменные, арифметика и ввод данных. "
            "Первый курс с теорией, тестами и задачей.",
            "python",
            [
                {
                    "title": "Переменные и числа",
                    "topic": "Основы",
                    "type": "theory",
                    "body": "Имя переменной связывается со значением. "
                    "Для целых чисел Python "
                    "использует тип `int`.\n\n"
                    "```python\napples = 2\nprint(apples + 3)\n```",
                },
                {
                    "title": "Проверка арифметики",
                    "topic": "Основы",
                    "type": "quiz",
                    "questions": [
                        {
                            "text": "Чему равно 2 + 3?",
                            "options": ["4", "5", "6"],
                            "correct": [1],
                            "multiple": False,
                        }
                    ],
                },
                {
                    "title": "Чтение строки",
                    "topic": "Ввод и вывод",
                    "type": "quiz",
                    "questions": [
                        {
                            "text": "Какие вызовы преобразуют строку в число?",
                            "options": ['int("5")', 'float("5")', "str(5)"],
                            "correct": [0, 1],
                            "multiple": True,
                        }
                    ],
                },
                {
                    "title": "Сумма двух чисел",
                    "topic": "Ввод и вывод",
                    "type": "practice",
                    "task_id": sum_id,
                },
            ],
        )
        await course(
            client,
            "cpp-start",
            "Первые шаги в C++",
            "Соберите первую программу, прочитайте входные данные и выведите ответ.",
            "cpp",
            [
                {
                    "title": "Чтение из std::cin",
                    "topic": "Основы",
                    "type": "theory",
                    "body": "Оператор `>>` читает значение из потока ввода.\n\n"
                    "```cpp\nint a;\nstd::cin >> a;\n```",
                },
                {
                    "title": "Сложение для разминки",
                    "topic": "Ввод и вывод",
                    "type": "practice",
                    "task_id": class_id,
                },
            ],
        )
        await login(client, "author2@example.com", demo_password)
        await course(
            client,
            "algorithms-draft",
            "Введение в алгоритмы",
            "Черновик курса.",
            "python",
            [],
            publish=False,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--admin", required=True)
    args = parser.parse_args()
    asyncio.run(
        seed(
            args.url,
            args.admin,
            os.environ["CODEFORGE_ADMIN_PASSWORD"],
            os.environ["CODEFORGE_DEMO_PASSWORD"],
        )
    )


if __name__ == "__main__":
    main()
