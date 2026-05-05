from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from eq_normalize import (
    coalesce_question_fields,
    normalize_answer,
    normalize_chapter,
    normalize_options,
    normalize_text,
)


class JsonParseError(Exception):
    pass


class RetryLimitExceededError(Exception):
    pass


class ExtractionValidationError(Exception):
    pass


class QuestionPayload(BaseModel):
    number: str
    topic: str | None = None
    chapter: str | None = None
    section: str | None = None
    title: str
    options: list[dict[str, str]] = Field(default_factory=list)
    correct_answer: str
    analysis: str
    type: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_source_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        q = coalesce_question_fields(value)
        return {
            "number": q.get("number"),
            "topic": q.get("topic"),
            "chapter": q.get("chapter"),
            "section": q.get("section"),
            "title": q.get("title"),
            "options": normalize_options(q.get("options", {})),
            "correct_answer": q.get("correct_answer"),
            "analysis": q.get("analysis"),
            "type": q.get("type"),
        }

    @field_validator("number", "title", "correct_answer", "analysis", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: Any) -> str:
        return normalize_text(value)

    @field_validator("topic", "chapter", "section", mode="before")
    @classmethod
    def normalize_hierarchy_fields(cls, value: Any) -> str | None:
        return normalize_chapter(value)

    @field_validator("correct_answer")
    @classmethod
    def normalize_answer_field(cls, value: str) -> str:
        return normalize_answer(value)

    @field_validator("options", mode="before")
    @classmethod
    def normalize_options_field(cls, value: Any) -> list[dict[str, str]]:
        return normalize_options(value)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type_field(cls, value: Any) -> str | None:
        normalized = normalize_text(value).lower()
        return normalized or None

    @model_validator(mode="after")
    def ensure_required_fields(self) -> "QuestionPayload":
        if not self.number:
            raise ValueError("缺少题号 number")
        if not self.title:
            raise ValueError("题目标题为空")
        if not self.options:
            raise ValueError("选项为空")
        for opt in self.options:
            if not opt.get("label") or not opt.get("text"):
                raise ValueError(f"选项不完整：{opt}")
        if not self.correct_answer:
            raise ValueError("答案为空")
        if not self.analysis:
            raise ValueError("解析为空")
        return self

    def to_record(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "topic": self.topic,
            "chapter": self.chapter,
            "section": self.section,
            "title": self.title,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "analysis": self.analysis,
            "type": self.type,
        }


class ExtractResultPayload(BaseModel):
    questions: list[QuestionPayload] = Field(default_factory=list)


def normalize_question_payload(question: dict[str, Any], source_label: str) -> dict[str, Any]:
    try:
        return QuestionPayload.model_validate(question).to_record()
    except ValidationError as exc:
        message = "; ".join(err["msg"] for err in exc.errors())
        raise ExtractionValidationError(f"{source_label} 校验失败: {message}") from exc
