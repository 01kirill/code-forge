from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
)

from codeforge.common.request_validation import CodeText
from codeforge.common.request_validation import Language as Language

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)]
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Source = Annotated[str, Field(min_length=1, max_length=65536)]
InputText = Annotated[str, Field(max_length=16384)]


class SuiteTest(BaseModel):
    stdin: InputText
    expected: InputText
    public: bool = False


class TaskSpec(BaseModel):
    title: Title
    statement: Annotated[str, Field(min_length=1, max_length=32000)]
    difficulty: Literal["easy", "medium", "hard"]
    templates: dict[Language, Source]
    time_ms: Annotated[int, Field(gt=0, le=10000)]
    memory_kb: Annotated[int, Field(ge=1024, le=262144)]
    tests: Annotated[list[SuiteTest], Field(min_length=1, max_length=30)]
    contest_ready: bool = False

    @model_validator(mode="after")
    def ready(self) -> Self:
        if not self.templates or not any(test.public for test in self.tests):
            raise ValueError("A language and a public test are required")
        return self


class Code(BaseModel):
    language: Language
    code: CodeText


class Submission(Code):
    lesson_id: str


class Run(Submission):
    stdin: InputText | None = None


class Module(BaseModel):
    title: Title
    lessons: list[str] = Field(default_factory=list, max_length=100)


class CourseEdit(BaseModel):
    title: Title
    description: Annotated[str, Field(min_length=1, max_length=8000)]
    language: Language
    topics: list[Title] = Field(default_factory=list, max_length=30)
    modules: list[Module] = Field(default_factory=list, max_length=30)
    published: bool = False

    @model_validator(mode="after")
    def unique_items(self) -> Self:
        ids = [lesson for module in self.modules for lesson in module.lessons]
        if len(set(self.topics)) != len(self.topics) or len(set(ids)) != len(ids):
            raise ValueError("Topics and lesson identifiers must be unique")
        if self.published and (not self.topics or not self.modules or not ids):
            raise ValueError("A published course requires topics and lessons")
        return self


class CourseCreate(CourseEdit):
    slug: Slug


class Question(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=1000)]
    options: Annotated[list[Title], Field(min_length=2, max_length=12)]
    correct: Annotated[list[int], Field(min_length=1, max_length=12)]
    multiple: bool = False

    @model_validator(mode="after")
    def valid_options(self) -> Self:
        if (
            len(set(self.correct)) != len(self.correct)
            or any(i < 0 or i >= len(self.options) for i in self.correct)
            or (not self.multiple and len(self.correct) != 1)
        ):
            raise ValueError("Invalid correct options")
        return self


class LessonBase(BaseModel):
    title: Title
    topic: Title


class Theory(LessonBase):
    type: Literal["theory"]
    body: Annotated[str, Field(min_length=1, max_length=32000)]


class Quiz(LessonBase):
    type: Literal["quiz"]
    questions: Annotated[list[Question], Field(min_length=1, max_length=30)]


class Practice(LessonBase):
    type: Literal["practice"]
    task_id: str


Lesson = Annotated[Theory | Quiz | Practice, Field(discriminator="type")]


class LessonCreate(BaseModel):
    course_slug: Slug
    module: Annotated[int, Field(ge=0, lt=30)]
    lesson: Lesson


class Answers(BaseModel):
    answers: Annotated[list[list[int]], Field(max_length=30)]
