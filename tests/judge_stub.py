"""Deterministic integration fixture. It never executes submitted code."""

from uuid import uuid4

from codeforge.common.broker import Document
from codeforge.education.infrastructure.judge0 import encode
from fastapi import FastAPI

app = FastAPI()
results: dict[str, Document] = {}
CORRECT = {
    71: {
        encode("print(sum(map(int, input().split())))"),
        encode("print(max(map(int, input().split())))"),
    },
    54: {
        encode(
            "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}"
        ),
    },
}


@app.get("/languages")
async def languages() -> list[Document]:
    return [{"name": "Python (3.8.1)", "id": 71}, {"name": "C++ (GCC 9.2.0)", "id": 54}]


@app.post("/submissions/batch", status_code=201)
async def submit(data: Document) -> list[Document]:
    registrations = []
    for case in data["submissions"]:
        token = uuid4().hex
        source = case["source_code"]
        accepted = source in CORRECT.get(case["language_id"], set())
        if source == encode("raise ZeroDivisionError"):
            status = 11
        elif source == encode("while True: pass"):
            status = 5
        elif source == encode("bad C++ syntax"):
            status = 6
        else:
            status = 3 if accepted or "expected_output" not in case else 4
        results[token] = {
            "token": token,
            "status": {"id": status},
            "time": "0.015",
            "memory": 4096,
            "stdout": case.get("expected_output") if accepted else encode("0"),
            "stderr": encode("ZeroDivisionError") if status == 11 else None,
        }
        registrations.append({"token": token})
    return registrations


@app.get("/submissions/batch")
async def batch(tokens: str) -> Document:
    return {
        "submissions": [results.get(token) for token in reversed(tokens.split(","))]
    }
