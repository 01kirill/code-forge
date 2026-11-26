from typing import Annotated

from pydantic import AfterValidator, Field, WithJsonSchema

from codeforge.common.contracts import JUDGE_LANGUAGES


def check_language(language: str) -> str:
    if language not in JUDGE_LANGUAGES:
        raise ValueError("Unsupported Judge0 language")
    return language


Language = Annotated[
    str,
    AfterValidator(check_language),
    WithJsonSchema({"type": "string", "enum": list(JUDGE_LANGUAGES)}),
]


def check_source_bytes(code: str) -> str:
    if len(code.encode()) > 65536:
        raise ValueError("Maximum source size is 64 KiB")
    return code


CodeText = Annotated[
    str, Field(min_length=1, max_length=65536), AfterValidator(check_source_bytes)
]
