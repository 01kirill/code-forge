from typing import Annotated, Literal

from pydantic import AfterValidator, Field

Language = Literal["python", "cpp"]


def check_source_bytes(code: str) -> str:
    if len(code.encode()) > 65536:
        raise ValueError("Maximum source size is 64 KiB")
    return code


CodeText = Annotated[
    str, Field(min_length=1, max_length=65536), AfterValidator(check_source_bytes)
]
