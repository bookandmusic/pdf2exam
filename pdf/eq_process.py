import json
import re
import time
from collections import defaultdict
from collections.abc import Callable
from difflib import SequenceMatcher, unified_diff
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError, OpenAI, RateLimitError

from eq_common import image_sequence, logger
from eq_extract import build_consensus_judge_prompt, build_extraction_schema, build_prompt, extract
from eq_io import collect_images, dump, encode_image, image_format
from eq_models import RetryLimitExceededError, normalize_question_payload
from eq_normalize import (
    coalesce_question_fields,
    extract_question_number,
    normalize_answer,
    normalize_chapter,
    normalize_options,
    normalize_text,
    question_key,
    question_source_label,
    questions_equal,
    sort_questions,
    summarize_question,
    validate_number_continuity,
)
from eq_settings import RuntimeSettings

# ── 批量 AI 裁决 ──────────────────────────────────────────────


def _normalize_judgment_number(value: Any) -> str:
    text = str(value or "").strip()
    if "#" in text:
        text = text.rsplit("#", 1)[-1].strip()
    m = re.search(r"(\d+)", text)
    return m.group(1) if m else text


def build_batch_judge_schema() -> dict[str, Any]:
    """构建批量 AI 裁决的响应格式 schema。"""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "batch_conflict_judgment",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "judgments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "number": {"type": "string"},
                                "decision": {"type": "string"},
                                "confidence": {"type": "string"},
                                "reason": {"type": "string"},
                                "corrected_question": {
                                    "type": "object",
                                    "properties": {
                                        "number": {"type": "string"},
                                        "topic": {"type": "string"},
                                        "chapter": {"type": "string"},
                                        "section": {"type": "string"},
                                        "title": {"type": "string"},
                                        "options": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "label": {"type": "string"},
                                                    "text": {"type": "string"},
                                                },
                                                "required": ["label", "text"],
                                                "additionalProperties": False,
                                            },
                                        },
                                        "correct_answer": {"type": "string"},
                                        "analysis": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                    "required": [
                                        "number",
                                        "topic",
                                        "chapter",
                                        "section",
                                        "title",
                                        "options",
                                        "correct_answer",
                                        "analysis",
                                        "type",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["number", "decision", "confidence", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["judgments"],
                "additionalProperties": False,
            },
        },
    }


def build_batch_judge_prompt(conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]]) -> str:
    """
    构建批量 AI 裁决 prompt。
    conflicts: [(题号, 版本1, 版本2), ...]
    """
    conflict_details = []
    for number, q1, q2 in conflicts:
        c1 = coalesce_question_fields(q1)
        c2 = coalesce_question_fields(q2)
        detail = f"""
题号 {number}

【版本1】
身份字段（corrected_question 必须原样沿用）：
- number：{c1.get("number") or ""}
- topic：{c1.get("topic") or ""}
- chapter：{c1.get("chapter") or ""}
- section：{c1.get("section") or ""}
题干：{c1.get("title") or ""}
选项：{json.dumps(c1.get("options", {}), ensure_ascii=False)}
答案：{c1.get("correct_answer") or ""}
解析：{c1.get("analysis") or ""}

【版本2】
身份字段（仅供对照，不得用于改写 corrected_question 的身份字段）：
- number：{c2.get("number") or ""}
- topic：{c2.get("topic") or ""}
- chapter：{c2.get("chapter") or ""}
- section：{c2.get("section") or ""}
题干：{c2.get("title") or ""}
选项：{json.dumps(c2.get("options", {}), ensure_ascii=False)}
答案：{c2.get("correct_answer") or ""}
解析：{c2.get("analysis") or ""}
"""
        conflict_details.append(detail)

    conflicts_text = "\n---\n".join(conflict_details)

    return f"""你是题目冲突裁决专家。任务是对比图片中的原始内容和两个识别版本，判断哪个版本正确。

冲突题目列表：
{conflicts_text}

工作流程：
1. 仔细阅读图片中每道题的原始内容（题干、选项、答案、解析）
2. **重要**：只能基于当前批次图片中的内容进行判断，不能凭空补充任何信息
3. **跨页拼接**：
   - 图片按页码顺序排列
   - 如果题目在当前页的最后，且内容不完整（如选项不全、解析缺失），必须查看下一页是否有续接内容
   - 将跨页的内容拼接后再判断是否完整
   - 只有在所有图片中都找不到完整信息时，才判断为 incomplete
4. 如果图片中题目信息不完整（选项不全、答案缺失、解析缺失等），必须返回 decision: "incomplete"
5. 对比每道题的两个版本，判断：
   - 如果版本1与图片完全一致 → decision: "version1"
   - 如果版本2与图片完全一致 → decision: "version2"
   - 如果两个版本都有错误但图片信息完整 → decision: "corrected"，并在 corrected_question 中给出正确的完整题目数据
   - 如果图片信息不完整 → decision: "incomplete"

6. **身份字段保护**：
   - number、topic、chapter、section 是题目身份字段，必须逐字复制版本1"身份字段"中的原值
   - 即使图片里出现标题，也不要根据图片重新拆分、改写或调换 topic/chapter/section
   - 例如版本1的 topic 是"专题三 说明书"时，corrected_question.topic 仍应为"专题三 说明书"
   - chapter/section 仍沿用版本1原值
   - 如果版本1的 chapter 或 section 为空字符串，corrected_question 中也必须保持为空字符串
   - corrected_question 只用于修正 title、options、correct_answer、analysis、type

7. **符号规范**：
   - JSON 语法必须保持标准 JSON
   - JSON 字符串内容中的中文文本，符号优先使用中文符号
   - 图片原文符号清晰可辨时以图片为准；半角/全角难以区分或两个版本仅符号不同时，优先选择中文符号
   - 英文缩写、网址、型号、法条编号、专利号、年份、选项标签 A/B/C/D、答案字母等保持原样

8. confidence 取值：
   - "high": 图片清晰，判断明确
   - "medium": 图片有轻微模糊但可判断
   - "low": 图片模糊或内容难以辨认

9. reason: 简要说明判断依据

输出格式：
{{
  "judgments": [
    {{
      "number": "题号",
      "decision": "version1" | "version2" | "corrected" | "incomplete",
      "confidence": "high" | "medium" | "low",
      "reason": "判断依据",
      "corrected_question": {{
        "number": "沿用版本1题号",
        "topic": "沿用版本1的topic",
        "chapter": "沿用版本1的chapter",
        "section": "沿用版本1的section",
        "title": "完整题干",
        "options": [
          {{"label": "A", "text": "选项A文本"}},
          {{"label": "B", "text": "选项B文本"}},
          {{"label": "C", "text": "选项C文本"}},
          {{"label": "D", "text": "选项D文本"}}
        ],
        "correct_answer": "正确答案（如A或ABC）",
        "analysis": "完整解析",
        "type": "single或multiple"
      }}
    }}
  ]
}}

注意：
- 必须为每道冲突题目返回一个判断结果
- decision="corrected" 时，corrected_question 字段必须提供，且必须包含完整的题目数据
- decision="incomplete" 时，表示图片信息不完整，该题目将被删除
- corrected_question 的结构必须严格按照上述格式，包含所有必需字段
"""


def _stream_chat_with_fallback(
    client: OpenAI,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    max_tokens: int,
    response_format_candidates: list[dict[str, Any] | None],
    timeout: float,
) -> str:
    """流式调用 API，自动回退响应格式。返回原始文本。"""
    for fmt in response_format_candidates:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if fmt is not None:
            kwargs["response_format"] = fmt
            logger.info("🧩 裁决响应格式：%s", fmt.get("type") if isinstance(fmt, dict) else fmt)
        else:
            logger.info("🧩 裁决响应格式：text/未指定")

        try:
            stream = client.chat.completions.create(**kwargs, timeout=timeout)
            chunks: list[str] = []
            first_token_logged = False
            started_at = time.time()
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunks.append(delta.content)
                        if not first_token_logged:
                            logger.info("📥 裁决收到首个 token，耗时 %.1f 秒", time.time() - started_at)
                            first_token_logged = True
            result_text = "".join(chunks)
            elapsed = time.time() - started_at
            logger.info("📥 裁决响应完成，用时 %.1f 秒，共 %d 字符", elapsed, len(result_text))
            if result_text.strip():
                return result_text
            logger.warning("API 返回空内容，尝试回退响应格式")
        except BadRequestError as e:
            msg = str(e).lower()
            unsupported_format = (
                "response_format.type" in msg or "json_object" in msg or "json_schema" in msg or "unsupported" in msg
            )
            if fmt is not None and unsupported_format:
                fmt_type = fmt.get("type") if isinstance(fmt, dict) else fmt
                logger.warning("当前后端不支持响应格式 %s，回退后重试", fmt_type)
                continue
            raise
        except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError):
            raise
        except Exception:
            raise
    raise ValueError("所有响应格式均返回空内容或不受支持")


def ai_judge_conflicts_batch(
    image_paths: list[str],
    conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]],
    settings: RuntimeSettings,
    artifact_paths: Any = None,
    batch_no: int | None = None,
    raw_filename: str = "batch_judge_raw.json",
) -> dict[str, dict[str, Any]]:
    """
    批量调用 AI 裁决多道冲突题目。

    参数：
        image_paths: 图片路径列表
        conflicts: [(题号, 版本1, 版本2), ...]
        settings: 运行时配置

    返回：{题号: 裁决结果}

    异常：AI 裁决失败时抛出 RetryLimitExceededError
    """
    if not conflicts:
        return {}

    prompt = build_batch_judge_prompt(conflicts)

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

    for p in image_paths:
        fmt = image_format(p)
        b64 = encode_image(p, max_size=settings.image_max_size, jpeg_quality=settings.image_jpeg_quality)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{b64}"}})

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
        result_text = _stream_chat_with_fallback(
            client=client,
            model=settings.model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=settings.max_output_tokens,
            response_format_candidates=[build_batch_judge_schema(), {"type": "json_object"}, None],
            timeout=settings.request_timeout,
        )
        raw_out_path = None
        if artifact_paths is not None and batch_no is not None:
            raw_out_path = artifact_paths.batch_dir(batch_no, image_paths) / raw_filename
            raw_out_path.parent.mkdir(parents=True, exist_ok=True)
            raw_out_path.write_text(result_text, encoding="utf-8")
        result = json.loads(result_text)
        judgments = result.get("judgments", [])
        if not isinstance(judgments, list):
            location = f"；原始返回已保存: {raw_out_path}" if raw_out_path else ""
            raise ValueError(f"AI 裁决返回字段 judgments 不是数组{location}")

        logger.info("   🤖 批量 AI 裁决返回 %d 条结果", len(judgments))
        if not judgments:
            location = f"；原始返回已保存: {raw_out_path}" if raw_out_path else ""
            raise ValueError(f"AI 裁决返回空 judgments，期望 {len(conflicts)} 条{location}")

        # 构建题号到裁决结果的映射
        judgment_map: dict[str, dict[str, Any]] = {}
        normalized_judgment_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for j in judgments:
            number = str(j.get("number", ""))
            if number:
                judgment_map[number] = j
                normalized_judgment_map[_normalize_judgment_number(number)].append(j)
        expected_numbers = [str(number) for number, _q1, _q2 in conflicts]
        missing_numbers = []
        ambiguous_numbers = []
        for number in expected_numbers:
            if number in judgment_map:
                continue
            normalized = _normalize_judgment_number(number)
            candidates = normalized_judgment_map.get(normalized, [])
            if len(candidates) == 1:
                judgment_map[number] = candidates[0]
            elif len(candidates) > 1:
                # 尝试用 corrected_question 的完整层级路径做歧义消解
                matched: dict[str, Any] | None = None
                if "#" in number:
                    expected_path = number.rsplit("#", 1)[0].strip()
                    for cand in candidates:
                        cq = cand.get("corrected_question", {})
                        cand_parts = [
                            part for part in (
                                cq.get("topic", ""),
                                cq.get("chapter", ""),
                                cq.get("section", "")
                            ) if part
                        ]
                        cand_path = "/".join(cand_parts) if cand_parts else ""
                        if cand_path and cand_path == expected_path:
                            matched = cand
                            break
                if matched is not None:
                    judgment_map[number] = matched
                else:
                    ambiguous_numbers.append(number)
            else:
                missing_numbers.append(number)
        if ambiguous_numbers:
            location = f"；原始返回已保存: {raw_out_path}" if raw_out_path else ""
            raise ValueError(f"AI 裁决题号匹配歧义: {', '.join(ambiguous_numbers)}{location}")
        if missing_numbers:
            location = f"；原始返回已保存: {raw_out_path}" if raw_out_path else ""
            raise ValueError(f"AI 裁决缺少题号: {', '.join(missing_numbers)}{location}")

        return judgment_map

    except Exception as e:
        logger.error("   ❌ 批量 AI 裁决失败: %s", e)
        raise RetryLimitExceededError(f"批量 AI 裁决失败: {e}") from e


# ── 共识检测 ─────────────────────────────────────────────────


def _judge_diff_with_llm(
    q1: dict[str, Any],
    q2: dict[str, Any],
    settings: RuntimeSettings,
    artifact_paths: Any = None,
    batch_no: int | None = None,
    question_number: str | None = None,
    image_paths: list[str] | None = None,
    attempt1: int = 1,
    attempt2: int = 2,
) -> tuple[bool, int]:
    """
    使用大模型判断两个题目的差异是否实质性。
    返回 (is_substantial, preferred_index)。
    is_substantial=True 表示实质性差异，无法选择。
    is_substantial=False 表示非实质性差异，preferred_index 指示选择哪个版本（0或1）。
    """
    from eq_io import save_consensus_diff, save_consensus_llm

    json1 = json.dumps(q1, ensure_ascii=False, indent=2)
    json2 = json.dumps(q2, ensure_ascii=False, indent=2)

    diff_lines = list(
        unified_diff(
            json1.splitlines(keepends=True),
            json2.splitlines(keepends=True),
            lineterm="",
            n=0,
        )
    )

    if not diff_lines:
        return False, 0

    diff_text = "".join(diff_lines[:100])  # 限制差异长度

    # 保存 diff
    if artifact_paths and batch_no is not None and image_paths is not None:
        if question_number is not None:
            # 批次间重复页面对比
            from eq_io import save_overlapping_diff

            save_overlapping_diff(artifact_paths, batch_no, image_paths, question_number, "".join(diff_lines))
        else:
            # 批次内共识对比
            save_consensus_diff(artifact_paths, batch_no, image_paths, attempt1, attempt2, "".join(diff_lines))

    prompt = f"""两次提取同一道题目，结果存在差异。请判断：

差异内容：
```diff
{diff_text}
```

判断标准：
1. 非实质性差异：标点符号差异（中文符号/英文符号、全角/半角括号、连字符/波浪号）、多余空格、同义词替换
2. 实质性差异：题干内容不同、选项文字不同、答案不同、解析逻辑不同

符号规范：
- JSON 语法必须保持标准 JSON。
- 如果是非实质性差异，选择更规范的版本：中文文本中的符号优先使用中文符号（，。；：？！ （） “” 《》 、）和完整表述。
- 英文缩写、网址、型号、法条编号、专利号、年份、选项标签 A/B/C/D、答案字母等保持原样。

返回JSON格式：
{{"is_substantial": true/false, "preferred_index": 0/1, "reason": "简短说明"}}"""

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
        content_text = _stream_chat_with_fallback(
            client=client,
            model=settings.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
            response_format_candidates=[{"type": "json_object"}, None],
            timeout=settings.request_timeout,
        )
        result = json.loads(content_text)
        is_substantial = result.get("is_substantial", True)
        preferred = result.get("preferred_index", 0)
        reason = result.get("reason", "")

        # 保存 LLM 决策
        if artifact_paths and batch_no is not None and image_paths is not None:
            llm_result = {
                "is_substantial": is_substantial,
                "preferred_index": preferred,
                "reason": reason,
                "question_number": q1.get("number", ""),
            }
            if question_number is not None:
                # 批次间重复页面对比
                from eq_io import save_overlapping_llm

                save_overlapping_llm(artifact_paths, batch_no, image_paths, question_number, llm_result)
            else:
                # 批次内共识对比
                save_consensus_llm(artifact_paths, batch_no, image_paths, attempt1, attempt2, llm_result)

        if not is_substantial:
            logger.info("   🤖 LLM判断：非实质性差异，选择版本 %d（%s）", preferred, reason)
        else:
            logger.warning("   🤖 LLM判断：实质性差异（%s）", reason)

        return is_substantial, preferred
    except Exception as e:
        logger.warning("   ⚠️  LLM差异判断失败，视为实质性差异: %s", e)
        return True, 0


def _judge_with_images(
    q1: dict[str, Any],
    q2: dict[str, Any],
    image_paths: list[str],
    settings: RuntimeSettings,
    artifact_paths: Any = None,
    batch_no: int | None = None,
    attempt1: int = 1,
    attempt2: int = 2,
) -> dict[str, Any]:
    """
    使用图片和详细prompt让AI裁决两个版本，返回正确的题目。
    """
    from eq_io import save_consensus_llm

    question_number = str(q1.get("number", "unknown"))
    prompt = build_consensus_judge_prompt(
        question_number,
        topic=q1.get("topic", ""),
        chapter=q1.get("chapter", ""),
        section=q1.get("section", ""),
    )

    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "text", "text": f"\n版本1：\n{json.dumps(q1, ensure_ascii=False, indent=2)}"},
        {"type": "text", "text": f"\n版本2：\n{json.dumps(q2, ensure_ascii=False, indent=2)}"},
    ]

    for p in image_paths:
        fmt = image_format(p)
        b64 = encode_image(p, max_size=settings.image_max_size, jpeg_quality=settings.image_jpeg_quality)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{b64}"}})

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
        result_text = _stream_chat_with_fallback(
            client=client,
            model=settings.model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=settings.max_output_tokens,
            response_format_candidates=[{"type": "json_object"}, None],
            timeout=settings.request_timeout,
        )
        result = json.loads(result_text)

        correct_q = result.get("correct_question", q1)
        judgment = result.get("judgment", {})

        if artifact_paths and batch_no is not None:
            save_consensus_llm(
                artifact_paths,
                batch_no,
                image_paths,
                attempt1,
                attempt2,
                {
                    "question_number": question_number,
                    "judgment": judgment,
                    "decision": judgment.get("decision", ""),
                    "confidence": judgment.get("confidence", ""),
                },
            )

        logger.info("   🤖 AI裁决：%s（置信度：%s）", judgment.get("decision", ""), judgment.get("confidence", ""))
        return correct_q
    except Exception as e:
        logger.warning("   ⚠️  AI裁决失败，使用版本1: %s", e)
        return q1


def _judge_overlapping_with_images(
    existing_q: dict[str, Any],
    new_q: dict[str, Any],
    batch_image_paths: list[str],
    context_pages_before: int,
    context_pages_after: int,
    settings: RuntimeSettings,
    artifact_paths: Any = None,
    batch_no: int | None = None,
) -> dict[str, Any]:
    """
    批次间重复页面的AI裁决，只传递交叉的图片。
    """
    from eq_io import save_overlapping_llm

    question_number = str(new_q.get("number", "unknown"))

    # 计算交叉图片：前 context_pages_before 张
    intersection_images = batch_image_paths[:context_pages_before] if context_pages_before > 0 else []

    if not intersection_images:
        logger.warning("   ⚠️  批次间裁决：无交叉图片，使用新版本")
        return new_q

    prompt = build_consensus_judge_prompt(
        question_number,
        topic=new_q.get("topic", ""),
        chapter=new_q.get("chapter", ""),
        section=new_q.get("section", ""),
    )

    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "text", "text": f"\n版本1（已有）：\n{json.dumps(existing_q, ensure_ascii=False, indent=2)}"},
        {"type": "text", "text": f"\n版本2（新批次）：\n{json.dumps(new_q, ensure_ascii=False, indent=2)}"},
    ]

    for p in intersection_images:
        fmt = image_format(p)
        b64 = encode_image(p)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{b64}"}})

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
        result_text = _stream_chat_with_fallback(
            client=client,
            model=settings.model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=settings.max_output_tokens,
            response_format_candidates=[{"type": "json_object"}, None],
            timeout=settings.request_timeout,
        )
        result = json.loads(result_text)

        correct_q = result.get("correct_question", existing_q)
        judgment = result.get("judgment", {})

        if artifact_paths and batch_no is not None:
            save_overlapping_llm(
                artifact_paths,
                batch_no,
                batch_image_paths,
                question_number,
                {
                    "question_number": question_number,
                    "judgment": judgment,
                    "decision": judgment.get("decision", ""),
                    "confidence": judgment.get("confidence", ""),
                    "intersection_images": len(intersection_images),
                },
            )

        logger.info(
            "   🤖 批次间裁决：%s（置信度：%s，交叉图片：%d张）",
            judgment.get("decision", ""),
            judgment.get("confidence", ""),
            len(intersection_images),
        )
        return correct_q
    except Exception as e:
        logger.warning("   ⚠️  批次间裁决失败，保留已有版本: %s", e)
        return existing_q


def _judge_batch_diff_with_llm(
    batch1: list[dict[str, Any]],
    batch2: list[dict[str, Any]],
    settings: RuntimeSettings,
    artifact_paths: Any = None,
    batch_no: int | None = None,
    image_paths: list[str] | None = None,
) -> tuple[bool, str]:
    """
    整体对比两次提取的结果，判断是否需要重试。
    返回 (needs_retry, reason)。
    needs_retry=True 表示差异较大，需要重试。
    needs_retry=False 表示差异可接受，无需重试。
    """
    json1 = json.dumps({"questions": batch1}, ensure_ascii=False, indent=2)
    json2 = json.dumps({"questions": batch2}, ensure_ascii=False, indent=2)

    diff_lines = list(
        unified_diff(
            json1.splitlines(keepends=True),
            json2.splitlines(keepends=True),
            lineterm="",
            n=1,
        )
    )

    if not diff_lines:
        return False, "两次结果完全一致"

    diff_text = "".join(diff_lines[:200])  # 限制差异长度

    # 保存 diff
    if artifact_paths and batch_no is not None and image_paths is not None:
        from eq_io import save_consensus_diff

        save_consensus_diff(artifact_paths, batch_no, image_paths, 1, 2, "".join(diff_lines))

    prompt = f"""两次提取同一批题目，结果存在差异。请整体判断是否需要重试：

差异内容：
```diff
{diff_text}
```

判断标准：
1. 可接受的差异（无需重试）：
   - 标点符号差异（中文符号/英文符号、全角/半角括号、连字符）
   - 多余空格、换行格式
   - 同义词替换（含义相同）
   - 个别题目的非关键字段差异

2. 需要重试的差异：
   - 多道题目的题干、选项、答案不同
   - 题目数量不一致
   - 大量题目结构错误

符号规范：
- JSON 语法必须保持标准 JSON。
- 判断首选结果时，中文文本中的符号优先使用中文符号（，。；：？！ （） “” 《》 、）。
- 英文缩写、网址、型号、法条编号、专利号、年份、选项标签 A/B/C/D、答案字母等保持原样。

返回JSON格式：
{{"needs_retry": true/false, "reason": "简短说明差异情况和判断依据"}}"""

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
        content_text = _stream_chat_with_fallback(
            client=client,
            model=settings.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
            response_format_candidates=[{"type": "json_object"}, None],
            timeout=settings.request_timeout,
        )
        result = json.loads(content_text)
        needs_retry = result.get("needs_retry", True)
        reason = result.get("reason", "")

        # 保存 LLM 决策
        if artifact_paths and batch_no is not None and image_paths is not None:
            from eq_io import save_consensus_llm

            save_consensus_llm(
                artifact_paths,
                batch_no,
                image_paths,
                1,
                2,
                {
                    "needs_retry": needs_retry,
                    "reason": reason,
                    "batch_comparison": True,
                },
            )

        return needs_retry, reason
    except Exception as e:
        logger.warning("   ⚠️  LLM整体判断失败，默认需要重试: %s", e)
        return True, str(e)


def _group_by_equality(results: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """将结果按内容相等分组，返回 {group_id: [members]}。"""
    groups: list[list[dict[str, Any]]] = []
    for r in results:
        found = False
        for g in groups:
            if questions_equal(g[0], r):
                g.append(r)
                found = True
                break
        if not found:
            groups.append([r])
    return dict(enumerate(groups))


def _has_consensus(results: list[dict[str, Any]]) -> bool:
    """至少有一个结果出现了 ≥2 次。"""
    if len(results) < 2:
        return False
    groups = _group_by_equality(results)
    return any(len(g) >= 2 for g in groups.values())


def _pick_consensus_result(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从结果列表中选出共识结果（出现次数最多的那组），无共识返回 None。"""
    groups = _group_by_equality(results)
    best_group = max(groups.values(), key=len, default=[])
    if len(best_group) >= 2:
        return best_group[0]
    return None


def _question_text_similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    """计算两道题各字段的加权文本相似度 (0~1)。"""
    ca = coalesce_question_fields(a)
    cb = coalesce_question_fields(b)

    def sim(x: Any, y: Any) -> float:
        if not x and not y:
            return 1.0
        if not x or not y:
            return 0.0
        return SequenceMatcher(None, str(x), str(y)).ratio()

    title_s = sim(normalize_text(ca.get("title")), normalize_text(cb.get("title")))
    opt_a_raw = normalize_options(ca.get("options", {}))
    opt_b_raw = normalize_options(cb.get("options", {}))
    opt_a: dict[str, str] = {o["label"]: o["text"] for o in opt_a_raw}
    opt_b: dict[str, str] = {o["label"]: o["text"] for o in opt_b_raw}
    labels = set(opt_a.keys()) | set(opt_b.keys())
    opt_s = sum(sim(opt_a.get(label, ""), opt_b.get(label, "")) for label in labels) / max(1, len(labels))
    ca_ans = normalize_answer(ca.get("correct_answer") or "")
    cb_ans = normalize_answer(cb.get("correct_answer") or "")
    ans_s = 1.0 if ca_ans == cb_ans else 0.0
    analysis_s = sim(normalize_text(ca.get("analysis")), normalize_text(cb.get("analysis")))

    return title_s * 0.35 + opt_s * 0.35 + ans_s * 0.15 + analysis_s * 0.15


def _pick_highest_similarity(results: list[dict[str, Any]]) -> dict[str, Any]:
    """无共识时，选与所有其他结果平均相似度最高的那个。"""
    if len(results) == 1:
        return results[0]
    best = results[0]
    best_avg = -1.0
    for r in results:
        total = sum(_question_text_similarity(r, other) for other in results if other is not r)
        avg = total / max(1, len(results) - 1)
        if avg > best_avg:
            best_avg = avg
            best = r
    return best


def _normalize_corrected_question_for_conflict(
    corrected: dict[str, Any],
    identity_source: dict[str, Any],
    source_label: str,
) -> dict[str, Any]:
    """
    AI 修正版只用于修正文案内容；题目身份沿用原冲突题。

    否则模型可能把 "专题三 说明书" 拆成 topic="说明书"、
    chapter="专题三"，导致同一批题被连续性校验误分到不同专题。
    """
    normalized = normalize_question_payload(corrected, source_label)
    for field in ("number", "topic", "chapter", "section"):
        value = identity_source.get(field)
        if value not in (None, ""):
            normalized[field] = value
    return normalized


def _remove_question_by_key(
    questions: list[dict[str, Any]],
    key: tuple[str, str, str, str],
) -> list[dict[str, Any]]:
    return [q for q in questions if question_key(q) != key]


def _select_judged_question(
    results: list[dict[str, Any]],
    judgment: dict[str, Any],
    identity_source: dict[str, Any],
    source_label: str,
) -> dict[str, Any] | None:
    decision = judgment.get("decision", "")
    if decision == "incomplete":
        return None
    if decision == "version1":
        return results[0]
    if decision == "version2":
        return results[1]
    if decision == "corrected":
        corrected = judgment.get("corrected_question")
        if corrected:
            try:
                return _normalize_corrected_question_for_conflict(corrected, identity_source, source_label)
            except Exception as e:
                logger.warning("   ⚠️  AI 修正版本格式错误: %s，使用版本1", e)
                return results[0]
        logger.warning("   ⚠️  AI 判定需修正但未提供 corrected_question，使用版本1")
        return results[0]
    logger.warning("   ⚠️  未知的裁决结果: %s，使用版本1", decision)
    return results[0]


def _resolve_question(
    results: list[dict[str, Any]],
    settings: RuntimeSettings | None = None,
    artifact_paths: Any = None,
    batch_no: int | None = None,
    image_paths: list[str] | None = None,
) -> tuple[dict[str, Any], bool]:
    """
    从多次提取结果中确定最佳题目。
    返回 (best_result, is_consensus)。
    """
    consensus = _pick_consensus_result(results)
    if consensus is not None:
        return consensus, True

    # 无简单共识：如果只有2个结果，使用AI详细裁决
    if len(results) == 2 and settings is not None and image_paths is not None:
        correct_q = _judge_with_images(results[0], results[1], image_paths, settings, artifact_paths, batch_no, 1, 2)
        return correct_q, True

    # 多个结果或无法裁决：使用相似度选择
    return _pick_highest_similarity(results), False


# ── 批次提取（含共识重试）───────────────────────────────────


def _extract_batch_with_consensus(
    paths: list[str],
    settings: RuntimeSettings,
    default_topic: str | None,
    batch_image_names: list[str],
    batch_no: int,
    prompt_fn: Callable[..., Any],
    schema_fn: Callable[..., Any],
    stop_requested_fn: Callable[..., Any] | None = None,
    default_chapter: str | None = None,
    default_section: str | None = None,
    artifact_paths: Any = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, str | None, str | None]:
    """
    对同一批图片多次调用 API，通过共识机制确认每道题。
    返回 (confirmed_questions, conflict_questions, final_topic, final_chapter, final_section)。
    """
    max_attempts = 1 if not settings.consensus else 2  # 共识模式最多2次，第2次后AI裁决
    all_results: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    all_batches: list[list[dict[str, Any]]] = []  # 保存每次提取的完整结果
    initial_topic = default_topic
    final_topic = default_topic or ""
    final_chapter = default_chapter
    final_section = default_section

    for attempt in range(1, max_attempts + 1):
        if stop_requested_fn and stop_requested_fn():
            break

        result, result_topic, result_chapter, result_section = extract(
            paths,
            settings,
            initial_topic,
            prompt_fn=prompt_fn,
            schema_fn=schema_fn,
            default_chapter=default_chapter,
            default_section=default_section,
            batch_no=batch_no,
            artifact_paths=artifact_paths,
            consensus_attempt=attempt,
        )
        final_topic = result_topic if result_topic is not None else (initial_topic or "")
        if result_chapter is not None:
            final_chapter = result_chapter
        if result_section is not None:
            final_section = result_section

        qs = result.get("questions", [])
        normalized_qs = []
        for idx, q in enumerate(qs, start=1):
            source_label = question_source_label(q, idx, batch_no=batch_no)
            try:
                q = normalize_question_payload(q, source_label)
            except Exception:
                continue
            q_topic = q.get("topic") or result_topic or initial_topic or "未设置"
            q["topic"] = q_topic
            key = question_key(q)
            all_results[key].append(q)
            normalized_qs.append(q)

        all_batches.append(normalized_qs)

        if not settings.consensus:
            break
        if attempt == 1:
            logger.info("   🔄 第 1 次提取完成，进行第 2 次确认…")
            continue

        # 第2次提取后：检查共识状态
        if attempt >= 2:
            uncertain_keys = [key for key, results in all_results.items() if not _has_consensus(results)]
            has_full_consensus = len(uncertain_keys) == 0

            if has_full_consensus:
                logger.info("   ✅ 所有题目已达成共识")
                break

            # 显示存疑题目（将通过AI裁决解决）
            uncertain_labels = [f"{key[0]}/{key[1]}/{key[2]}#{key[3]}" for key in uncertain_keys]
            logger.info("   🤖 存疑题目 %d 道，将通过AI裁决：%s", len(uncertain_keys), ", ".join(uncertain_labels))

    # ── 第一轮：收集有共识的题目和存疑题目 ──
    confirmed: list[dict[str, Any]] = []
    uncertain_items: list[tuple[Any, list[dict[str, Any]]]] = []  # (key, results)

    if not settings.consensus:
        for results in all_results.values():
            if not results:
                continue
            best = results[0]
            best["_consensus"] = False
            best["_attempts"] = len(results)
            confirmed.append(best)
        logger.info(
            "   📊 单次模式结果：%d 道确认 / 0 道存疑",
            len(confirmed),
        )
        return confirmed, [], final_topic, final_chapter, final_section

    for key, results in all_results.items():
        consensus = _pick_consensus_result(results)
        if consensus is not None:
            consensus["_consensus"] = True
            consensus["_attempts"] = len(results)
            confirmed.append(consensus)
        else:
            uncertain_items.append((key, results))

    # ── 第二轮：批量 AI 裁决存疑题目 ──
    conflict_qs: list[dict[str, Any]] = []

    if uncertain_items and len(all_batches) == 2:
        # 准备批量裁决的数据：[(题号, 版本1, 版本2), ...]
        batch_conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for _key, results in uncertain_items:
            if len(results) == 2:
                number = str(results[0].get("number", "unknown"))
                batch_conflicts.append((number, results[0], results[1]))

        # 添加这一批的最后一道题（即使有共识也要裁决，检查是否跨页）
        if confirmed and len(all_batches) == 2:
            last_question = confirmed[-1]
            last_number = str(last_question.get("number", "unknown"))
            # 检查最后一道题是否已经在冲突列表中
            if not any(num == last_number for num, _, _ in batch_conflicts):
                # 从 all_batches 中找到这道题的两个版本
                last_key = question_key(last_question)
                if last_key in all_results:
                    results = all_results[last_key]
                    if len(results) == 2:
                        batch_conflicts.append((last_number, results[0], results[1]))
                        logger.info("   📌 添加最后一道题（题号 %s）到裁决列表，检查是否跨页", last_number)

        if batch_conflicts:
            logger.info("   🤖 批量裁决 %d 道存疑题目", len(batch_conflicts))
            # AI 裁决失败会抛出异常，不再继续执行
            judgment_map = ai_judge_conflicts_batch(
                paths,
                batch_conflicts,
                settings,
                artifact_paths=artifact_paths,
                batch_no=batch_no,
                raw_filename="1-2-judge-raw.json",
            )

            # 保存 llm 裁决结果
            if artifact_paths and batch_no is not None:
                from eq_io import save_consensus_llm

                for number, judgment in judgment_map.items():
                    save_consensus_llm(
                        artifact_paths,
                        batch_no,
                        paths,
                        1,
                        2,
                        {
                            "question_number": number,
                            "judgment": judgment,
                            "decision": judgment.get("decision", ""),
                            "confidence": judgment.get("confidence", ""),
                            "reason": judgment.get("reason", ""),
                        },
                    )

            # 根据裁决结果处理每道题
            processed_conflict_keys: set[tuple[str, str, str, str]] = set()
            for _key, results in uncertain_items:
                if len(results) != 2:
                    # 不是2个结果，使用相似度选择
                    best = _pick_highest_similarity(results)
                    best["_consensus"] = False
                    best["_attempts"] = len(results)
                    best["_all_alternatives"] = [summarize_question(r) for r in results]
                    conflict_qs.append(best)
                    continue

                number = str(results[0].get("number", "unknown"))
                identity_key = question_key(results[0])
                judgment = judgment_map.get(number)

                if judgment is None:
                    # AI 未返回该题的裁决结果
                    logger.error("   ❌ 题号 %s 未获得 AI 裁决结果", number)
                    raise RetryLimitExceededError(f"题号 {number} 未获得 AI 裁决结果")

                decision = judgment.get("decision", "")
                confidence = judgment.get("confidence", "")
                reason = judgment.get("reason", "")

                logger.info("   🤖 题号 %s：%s（置信度：%s）- %s", number, decision, confidence, reason)

                best = _select_judged_question(results, judgment, results[0], "ai_corrected")
                if best is None:
                    logger.warning("   ⚠️  题号 %s 图片信息不完整，删除该题目", number)
                    confirmed = _remove_question_by_key(confirmed, identity_key)
                    processed_conflict_keys.add(identity_key)
                    continue

                best["_consensus"] = True
                best["_attempts"] = len(results)
                confirmed = _remove_question_by_key(confirmed, identity_key)
                confirmed.append(best)
                processed_conflict_keys.add(identity_key)

            # 额外加入裁决列表的最后一道题本来已在 confirmed 中，也要应用裁决结果。
            for number, q1, q2 in batch_conflicts:
                identity_key = question_key(q1)
                if identity_key in processed_conflict_keys:
                    continue

                judgment = judgment_map.get(number)
                if judgment is None:
                    logger.error("   ❌ 题号 %s 未获得 AI 裁决结果", number)
                    raise RetryLimitExceededError(f"题号 {number} 未获得 AI 裁决结果")

                decision = judgment.get("decision", "")
                confidence = judgment.get("confidence", "")
                reason = judgment.get("reason", "")
                logger.info("   🤖 题号 %s：%s（置信度：%s）- %s", number, decision, confidence, reason)

                best = _select_judged_question([q1, q2], judgment, q1, "ai_corrected")
                confirmed = _remove_question_by_key(confirmed, identity_key)
                if best is None:
                    logger.warning("   ⚠️  题号 %s 图片信息不完整，删除该题目", number)
                    continue
                best["_consensus"] = True
                best["_attempts"] = 2
                confirmed.append(best)
        else:
            # 没有2个结果的冲突，使用相似度选择
            for _key, results in uncertain_items:
                best = _pick_highest_similarity(results)
                best["_consensus"] = False
                best["_attempts"] = len(results)
                best["_all_alternatives"] = [summarize_question(r) for r in results]
                conflict_qs.append(best)
    else:
        # 不是2次提取或没有存疑题目，使用相似度选择
        for _key, results in uncertain_items:
            best = _pick_highest_similarity(results)
            best["_consensus"] = False
            best["_attempts"] = len(results)
            best["_all_alternatives"] = [summarize_question(r) for r in results]
            conflict_qs.append(best)

    logger.info(
        "   📊 共识结果：%d 道确认 / %d 道存疑",
        len(confirmed),
        len(conflict_qs),
    )
    return confirmed, conflict_qs, final_topic, final_chapter, final_section


# ── 批次连续性校验 ──────────────────────────────────────────────


def _check_batch_continuity(
    new_questions: list[dict[str, Any]],
    indexed_questions: dict[tuple[str, str, str, str], dict[str, Any]],
    fallback_topic: str,
) -> list[str]:
    new_by_topic: dict[str, list[int]] = defaultdict(list)
    for q in new_questions:
        tp = normalize_chapter(q.get("topic")) or fallback_topic or "未设置"
        num = extract_question_number(q)
        if num is not None:
            new_by_topic[tp].append(num)

    existing_max: dict[str, int] = {}
    for key in indexed_questions:
        tp = normalize_chapter(key[0]) or fallback_topic or "未设置"
        m = re.search(r"(\d+)", str(key[3]))
        if m:
            n = int(m.group(1))
            existing_max[tp] = max(existing_max.get(tp, 0), n)

    gaps = []
    for tp, nums in new_by_topic.items():
        if not nums:
            continue
        min_new = min(nums)
        expected = existing_max.get(tp, 0) + 1
        if min_new > expected:
            gaps.append(f"专题「{tp}」期望题号 {expected}，实际最小题号 {min_new}（跳过 {min_new - expected} 题）")
    return gaps


def _verify_conflict_label(key: tuple[str, str, str, str]) -> str:
    topic, chapter, section, number = key
    parts = [part for part in (topic, chapter, section) if part]
    prefix = "/".join(parts) if parts else "未设置"
    return f"{prefix}#{number}"


def verify_existing_directory(
    dir_path: str,
    settings: RuntimeSettings,
    default_topic: str | None = None,
    default_chapter: str | None = None,
    default_section: str | None = None,
    step: int | None = None,
    context: int | None = None,
    context_before: int | None = None,
    context_after: int | None = None,
    start_from: int | None = None,
    end_at: int | None = None,
    existing_qs: list[dict[str, Any]] | None = None,
    existing_index: dict[tuple[str, str, str, str], dict[str, Any]] | None = None,
    artifact_dir: str | None = None,
    artifact_name: str | None = None,
    subject_id: str | None = None,
    subject_name: str | None = None,
    serialize_subject: Any = None,
    stop_requested_fn: Any = None,
    prompt_fn: Callable[..., Any] = build_prompt,
    schema_fn: Callable[..., Any] = build_extraction_schema,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    from eq_io import ArtifactPaths, append_run_log

    if not artifact_dir or not artifact_name:
        raise ValueError("校验现有 JSON 模式必须提供 --artifact-dir 和 --artifact-name")
    if serialize_subject is None:
        raise ValueError("校验现有 JSON 模式缺少 serialize_subject")

    artifact_paths = ArtifactPaths(artifact_dir, artifact_name)
    artifact_paths.create_dirs()
    output_path = str(artifact_paths.final_output)
    run_log_file = artifact_paths.run_log
    append_run_log(
        run_log_file,
        f"校验现有题库开始 | 模型: {settings.model_name}",
        "开始",
    )

    images = collect_images(dir_path)
    step_size = max(1, step or 1)
    default_before = settings.context_pages_before
    default_after = settings.context_pages_after
    if context is not None:
        default_before = max(0, context)
        default_after = max(0, context)
    context_pages_before = default_before if context_before is None else max(0, context_before)
    context_pages_after = default_after if context_after is None else max(0, context_after)
    n = len(images)

    start_index = 0
    if start_from is not None:
        for idx, image in enumerate(images):
            seq = image_sequence(image)
            if seq is not None and seq >= start_from:
                start_index = idx
                logger.info("⏭️  从图片序号 %d 开始校验，保留前后邻页上下文", start_from)
                break
        else:
            raise FileNotFoundError(f"目录中没有序号大于等于 {start_from} 的图片: {dir_path}")

    end_index_exclusive = n
    if end_at is not None:
        last_match = None
        for idx, image in enumerate(images):
            seq = image_sequence(image)
            if seq is not None and seq <= end_at:
                last_match = idx
        if last_match is None:
            raise FileNotFoundError(f"目录中没有序号小于等于 {end_at} 的图片: {dir_path}")
        end_index_exclusive = last_match + 1
        logger.info("⏹️  校验到图片序号 %d 为止，保留终点页上下文", end_at)

    if start_index >= end_index_exclusive:
        raise ValueError(f"起始图片序号 {start_from} 不能大于结束图片序号 {end_at}")

    logger.info(
        "🔎 校验现有题库 | %d 张图片 | 主批次 %d 页 | 前文 %d 页 | 后文 %d 页",
        n,
        step_size,
        context_pages_before,
        context_pages_after,
    )
    logger.info("⚙️  %s | %s", settings.model_name, settings.api_url)

    indexed_questions: dict[tuple[str, str, str, str], dict[str, Any]] = dict(existing_index or {})
    if not indexed_questions:
        logger.warning("现有题库为空，校验模式会把图片提取到的题目作为新增内容写入")

    stats = {
        "extracted": 0,
        "matched": 0,
        "added": 0,
        "conflicts": 0,
        "kept": 0,
        "updated": 0,
        "corrected": 0,
        "incomplete": 0,
    }

    # 从已有题库中获取最后的目录状态作为初始值
    detected_topic = default_topic
    detected_chapter = default_chapter
    detected_section = default_section
    if existing_qs:
        # 向前查找最近的非空目录
        for q in reversed(existing_qs):
            if not detected_topic and q.get("topic"):
                detected_topic = q.get("topic")
            if not detected_chapter and q.get("chapter"):
                detected_chapter = q.get("chapter")
            if not detected_section and q.get("section"):
                detected_section = q.get("section")
            # 如果都找到了就停止
            if detected_topic and detected_chapter:
                break

    batch_no = 0

    i = start_index
    while i < end_index_exclusive:
        if stop_requested_fn and stop_requested_fn():
            logger.warning("🛑 已停止后续校验，保留当前已写回结果")
            break

        core_end = min(end_index_exclusive, i + step_size)
        left = max(0, i - context_pages_before)
        right = min(n, core_end + context_pages_after)
        batch = images[left:right]
        if not batch:
            break

        batch_no += 1
        paths = [str(p) for p in batch]
        logger.info(
            "🔎 #%d  校验主批次 [%s ~ %s] | 上下文 [%s ~ %s]",
            batch_no,
            images[i].name,
            images[core_end - 1].name,
            batch[0].name,
            batch[-1].name,
        )

        result, result_topic, result_chapter, result_section = extract(
            paths,
            settings,
            detected_topic,
            prompt_fn=prompt_fn,
            schema_fn=schema_fn,
            default_chapter=detected_chapter,
            default_section=detected_section,
            batch_no=batch_no,
            artifact_paths=artifact_paths,
            consensus_attempt=1,
        )
        detected_topic = result_topic or detected_topic
        if result_chapter is not None:
            detected_chapter = result_chapter
        if result_section is not None:
            detected_section = result_section
        extracted_qs = result.get("questions", [])
        stats["extracted"] += len(extracted_qs)

        verify_conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        verify_keys: list[tuple[str, str, str, str]] = []

        for q in extracted_qs:
            q_topic = q.get("topic") or detected_topic or "未设置"
            q["topic"] = q_topic
            key = question_key(q)
            existing = indexed_questions.get(key)
            if existing is None:
                indexed_questions[key] = q
                stats["added"] += 1
                logger.info("   ➕ 新增缺失题目：%s", _verify_conflict_label(key))
            elif questions_equal(existing, q):
                stats["matched"] += 1
            else:
                verify_conflicts.append((_verify_conflict_label(key), existing, q))
                verify_keys.append(key)

        if verify_conflicts:
            stats["conflicts"] += len(verify_conflicts)
            logger.info("   🤖 校验发现 %d 道差异题，进入 AI 裁决", len(verify_conflicts))
            judgment_map = ai_judge_conflicts_batch(
                paths,
                verify_conflicts,
                settings,
                artifact_paths=artifact_paths,
                batch_no=batch_no,
                raw_filename="verify_judge_raw.json",
            )

            if artifact_paths and batch_no is not None:
                from eq_io import save_overlapping_llm

                for label, judgment in judgment_map.items():
                    save_overlapping_llm(
                        artifact_paths,
                        batch_no,
                        paths,
                        label,
                        {
                            "question_number": label,
                            "judgment": judgment,
                            "decision": judgment.get("decision", ""),
                            "confidence": judgment.get("confidence", ""),
                            "reason": judgment.get("reason", ""),
                            "verify_existing": True,
                        },
                    )

            for idx, (label, existing_q, extracted_q) in enumerate(verify_conflicts):
                key = verify_keys[idx]
                judgment = judgment_map.get(label)
                if judgment is None:
                    logger.error("   ❌ 校验题目 %s 未获得 AI 裁决结果", label)
                    raise RetryLimitExceededError(f"校验题目 {label} 未获得 AI 裁决结果")

                decision = judgment.get("decision", "")
                confidence = judgment.get("confidence", "")
                reason = judgment.get("reason", "")
                logger.info("   🤖 校验 %s：%s（置信度：%s）- %s", label, decision, confidence, reason)

                if decision == "incomplete":
                    stats["incomplete"] += 1
                    logger.warning("   ⚠️  校验题目 %s 图片信息不完整，保留现有 JSON 内容", label)
                elif decision == "version1":
                    stats["kept"] += 1
                elif decision == "version2":
                    indexed_questions[key] = extracted_q
                    stats["updated"] += 1
                elif decision == "corrected":
                    corrected = judgment.get("corrected_question")
                    if not corrected:
                        raise RetryLimitExceededError(f"校验题目 {label} 判定 corrected 但缺少 corrected_question")
                    corrected_normalized = _normalize_corrected_question_for_conflict(
                        corrected,
                        existing_q,
                        "verify_corrected",
                    )
                    indexed_questions[key] = corrected_normalized
                    stats["corrected"] += 1
                else:
                    raise RetryLimitExceededError(f"校验题目 {label} 返回未知裁决结果: {decision}")

        sorted_qs = sort_questions(list(indexed_questions.values()))
        dump(serialize_subject(sorted_qs, output_path, subject_id, subject_name), output_path)
        report_path = artifact_paths.batch_dir(batch_no, paths) / "verify_report.json"
        report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("💾 校验写回: %s（累计 %d 道）", output_path, len(sorted_qs))

        append_run_log(
            run_log_file,
            f"校验批次{batch_no} | 图片{images[i].name}-{images[core_end - 1].name} | "
            f"提取{len(extracted_qs)}题 | 新增{stats['added']} | 更新{stats['updated']} | 修正{stats['corrected']}",
            "校验",
        )
        i += step_size

    final_qs = sort_questions(list(indexed_questions.values()))
    append_run_log(
        run_log_file,
        f"校验完成 | 总计{len(final_qs)}题 | 新增{stats['added']} | 更新{stats['updated']} | 修正{stats['corrected']}",
        "完成",
    )
    return final_qs, stats


# ── 目录处理（含共识机制）───────────────────────────────────


def process_directory(
    dir_path: str,
    settings: RuntimeSettings,
    default_topic: str | None = None,
    default_chapter: str | None = None,
    default_section: str | None = None,
    step: int | None = None,
    context: int | None = None,
    context_before: int | None = None,
    context_after: int | None = None,
    start_from: int | None = None,
    end_at: int | None = None,
    existing_qs: list[dict[str, Any]] | None = None,
    existing_index: dict[tuple[str, str, str, str], dict[str, Any]] | None = None,
    artifact_dir: str | None = None,
    artifact_name: str | None = None,
    subject_id: str | None = None,
    subject_name: str | None = None,
    serialize_subject: Any = None,
    stop_requested_fn: Any = None,
    prompt_fn: Callable[..., Any] = build_prompt,
    schema_fn: Callable[..., Any] = build_extraction_schema,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    from eq_io import ArtifactPaths, append_run_log

    # 创建产物目录结构
    artifact_paths: ArtifactPaths | None = None
    run_log_file = None
    output_path = None
    if artifact_dir and artifact_name:
        artifact_paths = ArtifactPaths(artifact_dir, artifact_name)
        artifact_paths.create_dirs()
        run_log_file = artifact_paths.run_log
        output_path = str(artifact_paths.final_output)
        append_run_log(
            run_log_file,
            f"提取任务开始 | 模型: {settings.model_name} | 共识: {'开启' if settings.consensus else '关闭'}",
            "开始",
        )

    images = collect_images(dir_path)
    step_size = max(1, step or 1)
    default_before = settings.context_pages_before
    default_after = settings.context_pages_after
    if context is not None:
        default_before = max(0, context)
        default_after = max(0, context)
    context_pages_before = default_before if context_before is None else max(0, context_before)
    context_pages_after = default_after if context_after is None else max(0, context_after)
    n = len(images)

    start_index = 0
    if start_from is not None:
        for idx, image in enumerate(images):
            seq = image_sequence(image)
            if seq is not None and seq >= start_from:
                start_index = idx
                logger.info("⏭️  从图片序号 %d 开始处理，保留前后邻页上下文", start_from)
                break
        else:
            raise FileNotFoundError(f"目录中没有序号大于等于 {start_from} 的图片: {dir_path}")

    end_index_exclusive = n
    if end_at is not None:
        last_match = None
        for idx, image in enumerate(images):
            seq = image_sequence(image)
            if seq is not None and seq <= end_at:
                last_match = idx
        if last_match is None:
            raise FileNotFoundError(f"目录中没有序号小于等于 {end_at} 的图片: {dir_path}")
        end_index_exclusive = last_match + 1
        logger.info("⏹️  处理到图片序号 %d 为止，保留终点页上下文", end_at)

    if start_index >= end_index_exclusive:
        raise ValueError(f"起始图片序号 {start_from} 不能大于结束图片序号 {end_at}")

    logger.info(
        "📸 %d 张图片 | 主批次 %d 页 | 前文 %d 页 | 后文 %d 页",
        n,
        step_size,
        context_pages_before,
        context_pages_after,
    )
    logger.info("⚙️  %s | %s", settings.model_name, settings.api_url)
    if settings.consensus:
        logger.info("🔁 共识模式：每批次至少 %d 次 API 调用", 2)
    else:
        logger.info("🔁 单次模式：每批次 1 次 API 调用")

    conflicts: list[dict[str, Any]] = []
    indexed_questions: dict[tuple[str, str, str, str], dict[str, Any]] = dict(existing_index or {})
    batch_no = 0

    # 从已有题库中获取最后的目录状态作为初始值
    detected_topic = default_topic
    detected_chapter = default_chapter
    detected_section = default_section
    if existing_qs:
        # 向前查找最近的非空目录
        for q in reversed(existing_qs):
            if not detected_topic and q.get("topic"):
                detected_topic = q.get("topic")
            if not detected_chapter and q.get("chapter"):
                detected_chapter = q.get("chapter")
            if not detected_section and q.get("section"):
                detected_section = q.get("section")
            # 如果都找到了就停止
            if detected_topic and detected_chapter:
                break

    topics_found: set[str] = set()

    i = start_index
    while i < end_index_exclusive:
        if stop_requested_fn and stop_requested_fn():
            logger.warning("🛑 已停止后续批次，保留当前已提取结果")
            break
        core_end = min(end_index_exclusive, i + step_size)
        left = max(0, i - context_pages_before)
        right = min(n, core_end + context_pages_after)
        batch = images[left:right]
        if not batch:
            break
        batch_no += 1
        paths = [str(p) for p in batch]
        logger.info(
            "🔄 #%d  主批次 [%s ~ %s] | 上下文 [%s ~ %s]",
            batch_no,
            images[i].name,
            images[core_end - 1].name,
            batch[0].name,
            batch[-1].name,
        )
        batch_image_names = [p.name for p in batch]

        # ── 共识提取 ──
        confirmed_qs, uncertain_qs, final_topic, final_chapter, final_section = _extract_batch_with_consensus(
            paths,
            settings,
            detected_topic,
            batch_image_names,
            batch_no,
            prompt_fn=prompt_fn,
            schema_fn=schema_fn,
            stop_requested_fn=stop_requested_fn,
            default_chapter=default_chapter,
            default_section=default_section,
            artifact_paths=artifact_paths,
        )
        if uncertain_qs:
            unresolved_labels = [
                f"{q.get('topic', '空')}/{q.get('chapter', '空')}/{q.get('section', '空')}#{q.get('number', '空')}"
                for q in uncertain_qs
            ]
            raise RetryLimitExceededError(
                f"第 {batch_no} 批在达到最大重试次数后仍有 {len(uncertain_qs)} 道题未解决冲突："
                f"{', '.join(unresolved_labels)}"
            )
        if final_topic and final_topic != detected_topic:
            logger.info("📖 专题切换：%s → %s", detected_topic or "无专题", final_topic)
        detected_topic = final_topic or detected_topic
        if final_chapter is not None:
            default_chapter = final_chapter
        if final_section is not None:
            default_section = final_section
        topics_found.add(detected_topic or "未设置")

        # 题号连续性检查：同时考虑确认题目和存疑题目
        all_extracted_qs = confirmed_qs + uncertain_qs
        if all_extracted_qs:
            gaps = _check_batch_continuity(all_extracted_qs, indexed_questions, detected_topic or "")
            if gaps:
                for g in gaps:
                    logger.error("⛔ 题号不连续：%s", g)
                logger.error("⛔ 已保存当前进度。请检查图片/提示词后，用 --start-from 继续。")
                break

        new_count = 0
        same_count = 0
        conflict_count = 0
        consensus_count = 0

        # ── 第一轮：收集批次间冲突 ──
        batch_overlapping_conflicts: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        batch_overlapping_keys: list[Any] = []

        for q in confirmed_qs:
            q_topic = q.get("topic") or detected_topic or "未设置"
            q["topic"] = q_topic
            topics_found.add(q_topic)
            key = question_key(q)
            existing_question = indexed_questions.get(key)

            is_consensus = q.get("_consensus", False)
            attempts = q.get("_attempts", 0)
            if is_consensus:
                consensus_count += 1

            if existing_question is None:
                # 新题目，直接添加
                indexed_questions[key] = q
                new_count += 1
            else:
                # 重叠上下文中已出现过的同目录同题号题目直接跳过。
                same_count += 1
                continue

        # ── 第二轮：批量 AI 裁决批次间冲突 ──
        if batch_overlapping_conflicts:
            logger.info("   🤖 批量裁决 %d 道批次间冲突", len(batch_overlapping_conflicts))

            # 计算交叉图片：前 context_pages_before 张
            intersection_images = paths[:context_pages_before] if context_pages_before > 0 else paths

            # AI 裁决失败会抛出异常，不再继续执行
            judgment_map = ai_judge_conflicts_batch(
                intersection_images,
                batch_overlapping_conflicts,
                settings,
                artifact_paths=artifact_paths,
                batch_no=batch_no,
                raw_filename="overlapping_judge_raw.json",
            )

            # 保存 llm 裁决结果
            if artifact_paths and batch_no is not None:
                from eq_io import save_overlapping_llm

                for number, judgment in judgment_map.items():
                    save_overlapping_llm(
                        artifact_paths,
                        batch_no,
                        intersection_images,
                        number,
                        {
                            "question_number": number,
                            "judgment": judgment,
                            "decision": judgment.get("decision", ""),
                            "confidence": judgment.get("confidence", ""),
                            "reason": judgment.get("reason", ""),
                        },
                    )

            for idx, (number, _existing_q, new_q) in enumerate(batch_overlapping_conflicts):
                key = batch_overlapping_keys[idx]
                judgment = judgment_map.get(number)

                if judgment is None:
                    # AI 未返回该题的裁决结果
                    logger.error("   ❌ 题号 %s 批次间冲突未获得 AI 裁决结果", number)
                    raise RetryLimitExceededError(f"题号 {number} 批次间冲突未获得 AI 裁决结果")

                decision = judgment.get("decision", "")
                confidence = judgment.get("confidence", "")
                reason = judgment.get("reason", "")

                logger.info("   🤖 题号 %s 批次间冲突：%s（置信度：%s）- %s", number, decision, confidence, reason)

                if decision == "incomplete":
                    # 图片信息不完整，删除该题目
                    logger.warning("   ⚠️  题号 %s 图片信息不完整，从索引中删除", number)
                    if key in indexed_questions:
                        del indexed_questions[key]
                elif decision == "version1":
                    # 保留已有版本
                    same_count += 1
                elif decision == "version2":
                    # 使用新版本
                    indexed_questions[key] = new_q
                    same_count += 1
                elif decision == "corrected":
                    corrected = judgment.get("corrected_question")
                    if corrected:
                        try:
                            corrected_normalized = _normalize_corrected_question_for_conflict(
                                corrected,
                                new_q,
                                "ai_corrected",
                            )
                            indexed_questions[key] = corrected_normalized
                            same_count += 1
                        except Exception as e:
                            logger.warning("   ⚠️  AI 修正版本格式错误: %s，使用新版本", e)
                            indexed_questions[key] = new_q
                            same_count += 1
                    else:
                        logger.warning("   ⚠️  AI 判定需修正但未提供 corrected_question，使用新版本")
                        indexed_questions[key] = new_q
                        same_count += 1
                else:
                    logger.warning("   ⚠️  未知的裁决结果: %s，使用新版本", decision)
                    indexed_questions[key] = new_q
                    same_count += 1

        # ── 清理元数据字段 ──
        for q in confirmed_qs:
            q.pop("_consensus", None)
            q.pop("_attempts", None)
            q.pop("_all_alternatives", None)

        for q in uncertain_qs:
            q_topic = q.get("topic") or detected_topic or "未设置"
            q["topic"] = q_topic
            topics_found.add(q_topic)
            key = question_key(q)
            existing_question = indexed_questions.get(key)
            q.pop("_consensus", None)
            attempts = q.pop("_attempts", 0)
            all_alternatives = q.pop("_all_alternatives", [])
            conflict_count += 1
            conflicts.append(
                {
                    "number": str(q.get("number", "")),
                    "topic": q_topic,
                    "chapter": q.get("chapter", ""),
                    "section": q.get("section", ""),
                    "title": q.get("title", ""),
                    "source_images": batch_image_names,
                    "dedupe_key": [q_topic, str(q.get("number", ""))],
                    "existing": summarize_question(existing_question) if existing_question is not None else None,
                    "incoming": summarize_question(q),
                    "all_alternatives": all_alternatives,
                    "consensus": False,
                    "attempts": attempts,
                }
            )
            logger.warning(
                "   ⚠️  题号 %s：%d 次提取无共识，仅记录冲突，不写入主结果",
                q.get("number", ""),
                attempts,
            )

        logger.info(
            "✅ 新增 %d 道（相同跳过 %d，冲突 %d，共识 %d）",
            new_count,
            same_count,
            conflict_count,
            consensus_count,
        )

        # 记录批次日志
        if run_log_file:
            append_run_log(
                run_log_file,
                f"批次{batch_no} | 图片{images[i].name}-{images[core_end - 1].name} | "
                f"提取{new_count}题 | 跳过{same_count}题 | 冲突{conflict_count}题",
                "批次",
            )

        if output_path and serialize_subject is not None:
            sorted_qs = sort_questions(list(indexed_questions.values()))
            dump(serialize_subject(sorted_qs, output_path, subject_id, subject_name), output_path)
            logger.info("💾 已实时写入: %s（累计 %d 道）", output_path, len(sorted_qs))

        i += step_size

    final_qs = sort_questions(list(indexed_questions.values()))
    for w in validate_number_continuity(final_qs):
        logger.warning(
            "⚠️  题号连续性：专题「%s」缺少题号 %s（范围 %d-%d）",
            w["chapter"],
            w["missing"],
            w["range"][0],
            w["range"][1],
        )
    resolved = detected_topic or default_topic or "未设置"
    if topics_found:
        topics_found.add(resolved)

    # 记录完成日志
    if run_log_file:
        append_run_log(run_log_file, f"提取完成 | 总计{len(final_qs)}题 | 冲突{len(conflicts)}题", "完成")

    return final_qs, conflicts, sorted(topics_found) if topics_found else [resolved]
