import hashlib
import json
import re
from pathlib import Path
from typing import Any

from eq_normalize import (
    _parse_question_num,
    chapter_sort_key,
    coalesce_question_fields,
    normalize_chapter,
    normalize_options,
)


def slugify_subject_id(value: str) -> str:
    normalized = re.sub(r"\.json$", "", value.strip(), flags=re.IGNORECASE)
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or "subject"


def derive_subject_meta(
    output_path: str | None,
    subject_id: str | None,
    subject_name: str | None,
) -> tuple[str, str]:
    stem = Path(output_path).stem if output_path else "subject"
    resolved_name = (subject_name or stem).strip() or "题库"
    resolved_id = slugify_subject_id(subject_id or stem)
    return resolved_id, resolved_name


def to_builtin_subject(
    questions: list[dict[str, Any]],
    subject_id: str,
    subject_name: str,
) -> dict[str, Any]:
    chapter_ids: dict[str, str] = {}
    chapters: list[dict[str, Any]] = []
    built_questions: list[dict[str, Any]] = []

    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for q in questions:
        from eq_normalize import question_key

        key = question_key(q)
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    questions = deduped

    def ensure_chapter_id(chapter_name: str) -> str:
        normalized = normalize_chapter(chapter_name) or "未设置"
        if normalized not in chapter_ids:
            chapter_ids[normalized] = f"{subject_id}-ch{len(chapter_ids) + 1}"
            chapters.append({"id": chapter_ids[normalized], "name": normalized})
        return chapter_ids[normalized]

    def stable_question_id(q: dict[str, Any]) -> str:
        identity = [
            normalize_chapter(q.get("topic")) or "",
            normalize_chapter(q.get("chapter")) or "",
            normalize_chapter(q.get("section")) or "",
            str(q.get("number", "")).strip(),
        ]
        digest = hashlib.sha1(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        return f"{subject_id}-q-{digest}"

    for idx, q in enumerate(questions, start=1):
        c = coalesce_question_fields(q)
        chapter_name = normalize_chapter(c.get("topic")) or c.get("chapter") or "未设置"
        chapter_id = ensure_chapter_id(chapter_name)
        options_raw = normalize_options(c.get("options", {}))
        options_dict = {o["label"]: o["text"] for o in options_raw}
        answer = str(c.get("correct_answer") or "")
        explicit_type = str(c.get("type") or "").strip().lower()
        inferred_type = "multiple" if len(re.findall(r"[A-Z]", answer)) > 1 else "single"
        q_type = explicit_type if explicit_type in {"single", "multiple"} else inferred_type
        built = {
            "id": stable_question_id(c),
            "number": str(c.get("number", idx)),
            "topic": normalize_chapter(c.get("topic")) or "",
            "chapter": normalize_chapter(c.get("chapter")) or "",
            "section": normalize_chapter(c.get("section")) or "",
            "question": c.get("title") or "",
            "options": options_dict,
            "answer": answer,
            "type": q_type,
            "knowledge": c.get("analysis") or "",
            "chapterId": chapter_id,
        }
        if q_type == "multiple":
            built["answers"] = re.findall(r"[A-Z]", answer)
        built_questions.append(built)

    chapters.sort(key=lambda ch: chapter_sort_key(ch["name"]))
    remap_chapter_id: dict[str, str] = {}
    for idx, ch in enumerate(chapters, start=1):
        new_id = f"{subject_id}-ch{idx}"
        remap_chapter_id[ch["id"]] = new_id
        ch["id"] = new_id
    built_questions.sort(
        key=lambda q: (
            chapter_sort_key(q.get("topic", "")),
            chapter_sort_key(q.get("chapter", "")),
            chapter_sort_key(q.get("section", "")),
            _parse_question_num(q.get("number", "")),
        )
    )
    for q in built_questions:
        q["chapterId"] = remap_chapter_id.get(q["chapterId"], q["chapterId"])
    return {
        "id": subject_id,
        "name": subject_name,
        "chapters": chapters,
        "questions": built_questions,
    }


def serialize_subject(
    questions: list[dict[str, Any]],
    output_path: str | None,
    subject_id: str | None,
    subject_name: str | None,
) -> dict[str, Any]:
    resolved_id, resolved_name = derive_subject_meta(output_path, subject_id, subject_name)
    return to_builtin_subject(questions, resolved_id, resolved_name)
