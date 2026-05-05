import re
from collections import defaultdict
from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_chapter(chapter: str | None) -> str | None:
    if chapter is None:
        return None
    normalized = re.sub(r"\s+", " ", str(chapter)).strip()
    if not normalized:
        return None
    if normalized in {"默认", "未知", "未识别", "无", "N/A", "n/a", "null", "None"}:
        return None
    return normalized


def normalize_answer(value: Any) -> str:
    text = normalize_text(value).upper()
    letters = re.findall(r"[A-Z]", text)
    if len(letters) > 1:
        return "".join(sorted(dict.fromkeys(letters)))
    return text


def normalize_options(options: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if isinstance(options, dict):
        for key, value in options.items():
            label = str(key).strip().upper()
            if label:
                normalized.append({"label": label, "text": normalize_text(value)})
        return sorted(normalized, key=lambda x: x["label"])
    if isinstance(options, list):
        for item in options:
            if not isinstance(item, dict):
                continue
            label = normalize_text(item.get("label")).upper()
            text = normalize_text(item.get("text"))
            if label:
                normalized.append({"label": label, "text": text})
        return sorted(normalized, key=lambda x: x["label"])
    return []


def coalesce_question_fields(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": q.get("number"),
        "topic": q.get("topic"),
        "chapter": q.get("chapter"),
        "section": q.get("section"),
        "title": q.get("title") or q.get("question"),
        "options": q.get("options", {}),
        "correct_answer": q.get("correct_answer") or q.get("answer"),
        "analysis": q.get("analysis") or q.get("knowledge"),
        "type": q.get("type"),
    }


def normalize_question_record(question: dict[str, Any]) -> dict[str, Any]:
    q = coalesce_question_fields(question)
    return {
        "topic": normalize_chapter(q.get("topic")) or "",
        "chapter": normalize_chapter(q.get("chapter")) or "",
        "section": normalize_chapter(q.get("section")) or "",
        "number": str(q.get("number", "")).strip(),
        "title": normalize_text(q.get("title")),
        "options": normalize_options(q.get("options", {})),
        "answer": normalize_answer(q.get("correct_answer") or ""),
        "type": normalize_text(q.get("type")).lower(),
        "analysis": normalize_text(q.get("analysis") or ""),
    }


def questions_equal(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return normalize_question_record(existing) == normalize_question_record(candidate)


def question_key(question: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        normalize_chapter(question.get("topic")) or "",
        normalize_chapter(question.get("chapter")) or "",
        normalize_chapter(question.get("section")) or "",
        str(question.get("number", "")).strip(),
    )


def summarize_question(question: dict[str, Any]) -> dict[str, Any]:
    q = coalesce_question_fields(question)
    return {
        "id": question.get("id"),
        "number": str(q.get("number", "")).strip(),
        "topic": normalize_chapter(q.get("topic")) or "",
        "chapter": normalize_chapter(q.get("chapter")) or "",
        "section": normalize_chapter(q.get("section")) or "",
        "title": q.get("title") or "",
        "options": q.get("options", {}),
        "correct_answer": q.get("correct_answer") or "",
        "analysis": q.get("analysis") or "",
        "type": q.get("type"),
    }


def question_source_label(
    question: dict[str, Any],
    fallback_index: int,
    batch_no: int | None = None,
) -> str:
    number = normalize_text(question.get("number"))
    prefix = f"第 {batch_no} 批" if batch_no is not None else ""
    if number:
        return f"{prefix}题号 {number}" if prefix else f"题号 {number}"
    return f"{prefix}第 {fallback_index} 条" if prefix else f"第 {fallback_index} 条"


# ── 排序与校验 ─────────────────────────────────────────────────

_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse_chapter_num(text: str) -> tuple[int, int]:
    """从章节名提取数字用于排序。返回 (数值, 优先级)，0=已提取，1=兜底。"""
    m = re.search(r"(\d+)", text)
    if m:
        return (int(m.group(1)), 0)
    m = re.search(r"[专题章节编]?([一二三四五六七八九十]+)", text)
    if m:
        s = m.group(1)
        if s in _CN_NUM:
            return (_CN_NUM[s], 0)
        if "十" in s:
            parts = s.split("十")
            tens = _CN_NUM.get(parts[0], 1) * 10 if parts[0] else 10
            ones = _CN_NUM.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return (tens + ones, 0)
    return (0, 1)


def chapter_sort_key(chapter_name: str) -> tuple[Any, ...]:
    ch = normalize_chapter(chapter_name) or ""
    num, order = _parse_chapter_num(ch)
    return (order, num, ch)


def _parse_question_num(number_str: str) -> tuple[int, int]:
    s = str(number_str).strip()
    m = re.search(r"(\d+)", s)
    if m:
        return (0, int(m.group(1)))
    return (1, 0)


def sort_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        questions,
        key=lambda q: (
            chapter_sort_key(q.get("chapter") or ""),
            _parse_question_num(q.get("number") or ""),
        ),
    )


def validate_number_continuity(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """检查每章节内题号是否连续，返回缺失题号信息列表。"""
    by_chapter: dict[str, set[int]] = defaultdict(set)
    for q in questions:
        ch = normalize_chapter(q.get("chapter")) or "未设置"
        m = re.search(r"(\d+)", str(q.get("number", "")))
        if m:
            by_chapter[ch].add(int(m.group(1)))
    warnings = []
    for ch in sorted(by_chapter.keys()):
        nums = by_chapter[ch]
        if len(nums) < 2:
            continue
        lo, hi = min(nums), max(nums)
        missing = sorted(set(range(lo, hi + 1)) - nums)
        if missing:
            warnings.append({"chapter": ch, "missing": missing, "range": [lo, hi]})
    return warnings


def extract_question_number(question: dict[str, Any]) -> int | None:
    """从题目中提取整数题号，无法提取返回 None。"""
    m = re.search(r"(\d+)", str(question.get("number", "")))
    return int(m.group(1)) if m else None
