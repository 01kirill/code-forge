from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from codeforge.common.request_validation import CodeText, Language


class RoomEdit(BaseModel):
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    description: Annotated[str, Field(max_length=4000)] = ""
    duration: Annotated[int, Field(ge=5, le=600)]


class Problems(BaseModel):
    task_ids: list[str] = Field(default_factory=list, max_length=26)

    @field_validator("task_ids")
    @classmethod
    def distinct(cls, ids: list[str]) -> list[str]:
        if len(ids) != len(set(ids)):
            raise ValueError("Task identifiers must be unique")
        return ids


class ContestCode(BaseModel):
    language: Language
    code: CodeText
