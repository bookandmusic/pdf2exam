from typing import Any

from pydantic import ValidationError

from eq_common import logger
from eq_models import ExtractionValidationError, QuestionPayload
from eq_normalize import (
    coalesce_question_fields,
    extract_question_number,
    normalize_chapter,
    normalize_options,
    normalize_text,
    question_key,
    question_source_label,
    questions_equal,
)


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(err["msg"] for err in exc.errors())


def _last_question_incomplete_reason(raw: Any) -> str | None:
    if not isinstance(raw, dict):
        return None
    q = coalesce_question_fields(raw)
    title = normalize_text(q.get("title"))
    answer = normalize_text(q.get("correct_answer"))
    analysis = normalize_text(q.get("analysis"))
    options = normalize_options(q.get("options", {}))
    if not title:
        return "题干为空"
    if len(options) != 4:
        return f"选项数量不是4个（实际 {len(options)} 个）"
    if not answer:
        return "答案为空"
    if not analysis:
        return "解析为空"
    return None


def _parse_question_payloads(result: dict[str, Any]) -> list[QuestionPayload]:
    if not isinstance(result, dict):
        raise ExtractionValidationError("模型返回结果结构不合法: 顶层不是 JSON 对象")
    raw_questions = result.get("questions", [])
    if not isinstance(raw_questions, list):
        raise ExtractionValidationError("模型返回结果结构不合法: questions 不是数组")

    parsed: list[QuestionPayload] = []
    total = len(raw_questions)
    for idx, raw in enumerate(raw_questions, start=1):
        if idx == total:
            reason = _last_question_incomplete_reason(raw)
            if reason is not None:
                number = raw.get("number") if isinstance(raw, dict) else idx
                logger.warning("⚠️  丢弃最后一道不完整题目：题号 %s（%s）", number, reason)
                break
        try:
            parsed.append(QuestionPayload.model_validate(raw))
        except ValidationError as exc:
            message = _validation_message(exc)
            if idx == total:
                number = raw.get("number") if isinstance(raw, dict) else idx
                logger.warning("⚠️  丢弃最后一道校验失败题目：题号 %s（%s）", number, message)
                break
            raise ExtractionValidationError(f"模型返回结果结构不合法: {message}") from exc
    return parsed


def finalize_extract_result(
    result: dict[str, Any],
    default_topic: str | None = None,
    default_chapter: str | None = None,
    default_section: str | None = None,
) -> tuple[dict[str, Any], str | None, str | None, str | None]:
    parsed_questions = _parse_question_payloads(result)
    current_topic = normalize_chapter(default_topic)
    current_chapter = normalize_chapter(default_chapter) or ""
    current_section = normalize_chapter(default_section) or ""
    normalized_questions: list[dict[str, Any]] = []
    seen_questions: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    previous_number: int | None = None
    current_scope = (current_topic, current_chapter, current_section)
    closed_scopes: set[tuple[str | None, str, str]] = set()

    for idx, item in enumerate(parsed_questions, start=1):
        q = item.to_record()
        source_label = question_source_label(q, idx)
        q_number = extract_question_number(q)
        explicit_topic = normalize_chapter(q.get("topic"))
        explicit_chapter = normalize_chapter(q.get("chapter"))
        explicit_section = normalize_chapter(q.get("section"))

        if q_number is None:
            raise ExtractionValidationError(f"{source_label} 题号无法解析为整数，无法做连续性校验")

        # 目录继承逻辑（适配 9B 模型）：
        # - AI 只填空题号=1 的目录，其他题目留空 ""
        # - Python 自动继承：题号=1 的目录 → 后续所有题目
        # - 题号=1 时，根据提供的最高层级决定继承策略：
        #   * 有 topic → 不继承，清空 chapter 和 section
        #   * 只有 chapter → 继承 topic，清空 section
        #   * 只有 section → 继承 topic 和 chapter
        resolved_topic = current_topic
        resolved_chapter = current_chapter
        resolved_section = current_section

        # 题号=1 时的特殊处理：根据提供的最高层级决定继承
        if q_number == 1:
            if explicit_topic:
                # 提供了 topic → 不继承任何上级目录
                resolved_topic = explicit_topic
                resolved_chapter = explicit_chapter or ""
                resolved_section = explicit_section or ""

                # 层级约束：有section必须有chapter
                if explicit_section and not explicit_chapter:
                    if not current_chapter:
                        raise ExtractionValidationError(
                            f"{source_label} 题号=1 提供了专题和节但没有章，且无可继承的章"
                        )
                    resolved_chapter = current_chapter
            elif explicit_chapter:
                # 只提供了 chapter → 继承 topic，不继承 section
                if not current_topic:
                    raise ExtractionValidationError(f"{source_label} 题号=1 提供了章但没有可继承的专题")
                resolved_topic = current_topic
                resolved_chapter = explicit_chapter
                resolved_section = explicit_section or ""
            elif explicit_section:
                # 只提供了 section → 继承 topic 和 chapter
                if not current_topic or not current_chapter:
                    raise ExtractionValidationError(
                        f"{source_label} 题号=1 提供了节但没有可继承的专题或章"
                    )
                resolved_topic = current_topic
                resolved_chapter = current_chapter
                resolved_section = explicit_section
            # else: 题号=1 但没有提供任何目录 → 继承所有（保持 current_*）
        else:
            # 题号≠1：继承当前目录，不处理 explicit_* 字段（应该都是空的）
            pass

        # 最终验证：确保目录层级完整性
        if resolved_section and not resolved_chapter:
            raise ExtractionValidationError(f"{source_label} 有节但没有章，目录层级不完整")
        if resolved_chapter and not resolved_topic:
            raise ExtractionValidationError(f"{source_label} 有章但没有专题，目录层级不完整")

        new_scope = (resolved_topic, resolved_chapter, resolved_section)
        scope_changed = new_scope != current_scope

        if scope_changed:
            if previous_number is None and current_scope != (None, "", "") and q_number != 1:
                scope_label = (
                    f"{resolved_topic}/{resolved_chapter}/{resolved_section}"
                    if resolved_section
                    else f"{resolved_topic}/{resolved_chapter}"
                    if resolved_chapter
                    else resolved_topic
                )
                raise ExtractionValidationError(
                    f"{source_label} 切到新目录「{scope_label}」但题号为 {q_number}。"
                    "新目录必须从 1 开始；这通常表示漏解析了前序图片，或上一批/本批目录识别错误。"
                )
            if previous_number is not None and q_number != 1:
                scope_label = (
                    f"{resolved_topic}/{resolved_chapter}/{resolved_section}"
                    if resolved_section
                    else f"{resolved_topic}/{resolved_chapter}"
                    if resolved_chapter
                    else resolved_topic
                )
                raise ExtractionValidationError(
                    f"{source_label} 新目录「{scope_label}」必须从题号 1 开始，当前为 {q_number}"
                )
            if new_scope in closed_scopes:
                scope_label = (
                    f"{resolved_topic}/{resolved_chapter}/{resolved_section}"
                    if resolved_section
                    else f"{resolved_topic}/{resolved_chapter}"
                    if resolved_chapter
                    else resolved_topic
                )
                raise ExtractionValidationError(
                    f"{source_label} 目录「{scope_label}」在同一批次内重复出现，目录分段异常"
                )
            if previous_number is not None and current_scope != (None, "", ""):
                closed_scopes.add(current_scope)
            previous_number = None

        if q_number == 1:
            if not resolved_topic:
                raise ExtractionValidationError(f"{source_label} 题号从 1 开始，必须显式提供或继承专题 topic")
            if previous_number is not None and not scope_changed:
                previous_number = None
        else:
            # 题号≠1：允许继承上一题或上一批的目录，不强制要求 AI 填入
            if not resolved_topic:
                raise ExtractionValidationError(f"{source_label} 未识别到明确的专题，且不存在可沿用的上一题专题上下文")
            if previous_number is not None and q_number != previous_number + 1:
                raise ExtractionValidationError(
                    f"{source_label} 题号不连续：上一题为 {previous_number}，当前为 {q_number}。"
                    "同一目录内题号必须连续；新目录必须从 1 开始。"
                )

        q["topic"] = resolved_topic
        q["chapter"] = resolved_chapter
        q["section"] = resolved_section
        current_topic = resolved_topic
        current_chapter = resolved_chapter
        current_section = resolved_section
        current_scope = new_scope

        key = question_key(q)
        existing = seen_questions.get(key)
        if existing is not None and not questions_equal(existing, q):
            scope_label = (
                f"{resolved_topic}/{resolved_chapter}/{resolved_section}"
                if resolved_section
                else f"{resolved_topic}/{resolved_chapter}"
                if resolved_chapter
                else resolved_topic
            )
            logger.warning(
                "⚠️  %s 目录疑似错误：同一批次内目录「%s」题号 %s 出现了不同内容，保留给合并阶段按内容去重处理",
                source_label,
                scope_label,
                q.get("number", ""),
            )
        seen_questions[key] = q
        normalized_questions.append(q)
        previous_number = q_number
    return {"questions": normalized_questions}, current_topic, current_chapter, current_section
