import json
import re
import time
from collections.abc import Callable
from typing import Any

from openai import BadRequestError, OpenAI

from eq_chapter import finalize_extract_result
from eq_common import ensure_not_stopped, logger, wait_for_api_interval
from eq_io import encode_image, image_format, save_raw_response
from eq_models import ExtractionValidationError, JsonParseError
from eq_settings import RuntimeSettings


def build_extraction_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "exam_extraction",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
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
                },
                "required": ["questions"],
                "additionalProperties": False,
            },
        },
    }


def build_response_format_candidates(
    settings: RuntimeSettings,
    schema_fn: Callable[[], dict[str, Any]] = build_extraction_schema,
) -> list[dict[str, Any] | None]:
    fmt = settings.response_format.lower()
    if fmt == "text" or fmt == "none":
        return [None]
    if fmt == "json_object":
        return [{"type": "json_object"}, None]
    if fmt == "json_schema":
        return [schema_fn(), {"type": "json_object"}, None]
    # auto 或其他值：默认使用 json_object
    return [{"type": "json_object"}, None]


def build_prompt() -> str:
    return """你是试卷选择题提取器。输入是连续页面图片，双栏排版：左侧题目（题干 + 选项），右侧解析，底部页码。

【核心规则】
1. 只提取完整题目（题干 + 4 选项 + 答案 + 解析齐全）
2. 不完整题目直接丢弃（尤其是最后一页的题目）
3. 原文照抄，禁止改写/补全/推测
4. **题号保留**：
   - 题干中的题号（如 "1. "、"2. "）必须原样保留在 title 字段开头
   - 解析中的题号和答案（如 "1. A。"、"4. ABD。"）必须原样保留在 analysis 字段开头

【任务流程】
第一步：按底部页码排序图片。

第二步：逐题读取（按题号顺序，**跨目录连续提取**）
1. 题干：从左侧栏读取，支持跨页拼接。
2. 选项：从左侧栏读取 A/B/C/D 四个选项，支持跨页拼接。
3. 解析：从右侧栏读取，从答案标记（如"3. CD。"）开始，直到遇到下一题号。
   - **解析跨页拼接**：解析到页面底部但未结束 → 必须读下一页右侧栏继续拼接，直到遇到下一题号或解析自然结束。
   - 最后一页的解析到底部 → 标记为【已截断】，该题目丢弃。
4. **跨目录连续提取**：同一批图片可能包含多个专题/章节/节。遇到"专题 X"、"第 X 章"或"第 X 节"等新标题时，**不要停止**。
   继续提取新目录下的题目（题号会从 1 重新开始）。必须提取完所有图片中的所有题目。

第三步：完整性检查（全部通过才能提取）
- 题干完整（无截断）
- 4 个选项齐全（A/B/C/D 都有）
- 答案明确（解析开头有答案标记）
- 解析完整（未截断）
- 任一不通过 → 丢弃

【目录规则（极简）】
- 只识别题号 = "1" 的题目目录
- 找到题号 1 后，看它上方最近的标题，按格式填入：
  * topic：只有"专题 X XXXX"格式才填
  * chapter：只有"第 X 章 XXXX"格式才填
  * section：只有"第 X 节 XXXX"格式才填
- 题号 ≠ 1 的题目，topic/chapter/section 全部填 ""
- 不确定时全部填 ""
- **重要**：遇到新专题/新章/新节标题时，题号会重新从 1 开始，此时该题号=1 的题目需要填入新目录信息。
  **继续提取后续题目，不要停止**

【输出格式】
{
  "questions": [{
    "number": "1", "topic": "专题一 XXXX", "chapter": "第一章 XXXX", "section": "第一节 XXXX",
    "title": "1. 根据民法典总则编及相关规定，因下列哪些行为...(单选)",
    "options": [
      {"label": "A", "text": "选项 A"}, {"label": "B", "text": "选项 B"},
      {"label": "C", "text": "选项 C"}, {"label": "D", "text": "选项 D"}
    ],
    "correct_answer": "A", "analysis": "1. A。A选项行政机关参与民事活动属于...", "type": "single"
  }]
}
- **title 必须以题号开头**（如 "1. "、"2. "），与图片原文一致
- **analysis 必须以题号+答案开头**（如 "1. A。"、"4. ABD。"），与图片原文一致
- type：单字母→"single"，多字母→"multiple"
- 所有字段字符串
- 无完整题目时返回 {"questions": []}
- **必须提取完所有图片中的所有题目，不能因为遇到新专题/新章标题就停止**"""


def build_retry_prompt(question_numbers: list[str]) -> str:
    """构建重新提取指定题号的prompt"""
    numbers_str = "、".join(question_numbers)
    base_prompt = build_prompt()
    return f"""{base_prompt}

**特别说明：本次只需提取题号为 {numbers_str} 的题目**
- 忽略其他题号的题目
- 只输出指定题号的题目
- 仍然遵循上述所有规则（完整性检查、逐字转录等）
"""


def retry_extract_questions(
    image_paths: list[str],
    question_numbers: list[str],
    settings: RuntimeSettings,
    default_topic: str | None = None,
    default_chapter: str | None = None,
    default_section: str | None = None,
) -> list[dict[str, Any]]:
    """重新提取指定题号的题目

    Args:
        image_paths: 原始图片路径列表
        question_numbers: 需要重新提取的题号列表
        settings: 运行时设置
        default_topic: 默认专题
        default_chapter: 默认章
        default_section: 默认节

    Returns:
        重新提取的题目列表
    """
    logger.info("🔄 重新提取题号：%s", "、".join(question_numbers))

    result, _, _, _ = extract(
        image_paths,
        settings,
        default_topic,
        prompt_fn=lambda: build_retry_prompt(question_numbers),
        schema_fn=build_extraction_schema,
        default_chapter=default_chapter,
        default_section=default_section,
    )

    questions = result.get("questions", [])
    logger.info("✅ 重新提取完成，获得 %d 道题目", len(questions))
    return questions


def build_consensus_judge_prompt(
    question_number: str,
    topic: str = "",
    chapter: str = "",
    section: str = "",
) -> str:
    """构建批次内共识裁决的prompt"""
    identity = f"题号{question_number}"
    if topic:
        identity += f"（{topic}"
        if chapter:
            identity += f" / {chapter}"
        if section:
            identity += f" / {section}"
        identity += "）"

    return f"""你是裁决器。{identity}的两次提取结果不同，以图片为准判断正确版本。

【版面与跨页规则】
- 双栏排版：左侧题目（题干+选项），右侧解析，底部页码。
- 解析经常跨页：右侧栏到底部→翻页继续读，直到下一题号或自然结束。
- 页面底部=翻页点，不是截断点。无下一页才算截断。

【专题归属判断（优先）】
- 一批图片可能跨越多个专题/章节，同一题号可能在不同专题重复出现。
- 先确认图片中该题号所属的专题/章节，再对比内容。
- 如果版本1和版本2的 topic/chapter/section 不同，说明属于不同专题的不同题目，禁止混合裁决。
- 裁决时只修正内容字段（title/options/correct_answer/analysis/type），禁止修改 topic/chapter/section。

【禁令】
- 禁止推测、补全、改写。图片有什么选什么，绝不脑补。
- 禁止修改 number/topic/chapter/section，必须沿用输入版本原值。

【决策流程】
1. 按页码排序图片，定位题号{question_number}。
2. 确认该题所属专题/章节（看图片中该题上方最近的专题/章/节标题）。
3. 读取左侧题干+选项（跨页拼接），读取右侧解析（跨页拼接）。
4. 对比版本1、版本2与图片原文：
   - 版本1正确→选版本1
   - 版本2正确→选版本2
   - 都错→按图片生成正确版本
5. 符号规则：中文符号优先；半角/全角难区分时选中文符号；英文/网址/法条保持原样。

【输出JSON】
{{"correct_question": {{"number": "{question_number}",
"topic": "{topic or "沿用输入值"}", "chapter": "{chapter or "沿用输入值"}",
"section": "{section or "沿用输入值"}", "title": "正确题干",
"options": [{{"label": "A", "text": "正确A"}}, {{"label": "B", "text": "正确B"}},
{{"label": "C", "text": "正确C"}}, {{"label": "D", "text": "正确D"}}],
"correct_answer": "正确字母", "analysis": "正确解析（跨页拼接后）",
"type": "single/multiple"}},
"judgment": {{"version1_errors": "版本1错误描述或无",
"version2_errors": "版本2错误描述或无",
"decision": "选择版本1/选择版本2/生成新版本",
"confidence": "high/medium/low", "reason": "判断理由"}}}}
"""


def parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()

    def repair_common_json_issues(snippet: str) -> str:
        pattern = re.compile(r'(\{\s*"label"\s*:\s*"[^"]+"\s*,\s*)(?!"text"\s*:)"([^"\\]*(?:\\.[^"\\]*)*)"\s*\}')
        return pattern.sub(r'\1"text": "\2"}', snippet)

    def pick_better(best_obj: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
        if best_obj is None:
            return candidate
        if len(candidate.get("questions", [])) > len(best_obj.get("questions", [])):
            return candidate
        return best_obj

    def try_parse_candidate(snippet: str) -> tuple[dict[str, Any] | None, tuple[str, json.JSONDecodeError, str] | None]:
        snippet = snippet.strip()
        if not snippet:
            return None, None
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict) and "questions" in obj:
                return obj, None
            return None, None
        except json.JSONDecodeError as err:
            repaired = repair_common_json_issues(snippet)
            if repaired != snippet:
                try:
                    obj = json.loads(repaired)
                    if isinstance(obj, dict) and "questions" in obj:
                        return obj, None
                except json.JSONDecodeError as repaired_err:
                    return None, ("repaired", repaired_err, repaired)
            return None, ("raw", err, snippet)

    def extract_fenced_blocks(source: str) -> list[str]:
        blocks: list[str] = []
        for pattern in [r"```json\s*(.*?)\s*```", r"```JSON\s*(.*?)\s*```", r"```\s*(\{.*?\})\s*```"]:
            for match in re.finditer(pattern, source, flags=re.DOTALL):
                blocks.append(match.group(1).strip())
        return blocks

    def extract_json_objects(source: str) -> list[str]:
        objects: list[str] = []
        for i, char in enumerate(source):
            if char != "{":
                continue
            depth = 0
            in_string = False
            escaped = False
            search_limit = min(i + 30000, len(source))
            for j in range(i, search_limit):
                current = source[j]
                if in_string:
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        in_string = False
                    continue
                if current == '"':
                    in_string = True
                elif current == "{":
                    depth += 1
                elif current == "}":
                    depth -= 1
                    if depth == 0:
                        objects.append(source[i : j + 1])
                        break
        return objects

    best: dict[str, Any] | None = None
    best_error = None
    candidates = [text]
    candidates.extend(extract_fenced_blocks(text))
    candidates.extend(extract_json_objects(text))
    for snippet in candidates:
        obj, error = try_parse_candidate(snippet)
        if obj is not None:
            best = pick_better(best, obj)
            continue
        if error and best_error is None:
            best_error = error
    if best is not None:
        return best
    if best_error:
        kind, err, snippet = best_error
        logger.error(
            "模型 JSON 解析失败（%s）: %s at line %d column %d (char %d)",
            kind,
            err.msg,
            err.lineno,
            err.colno,
            err.pos,
        )
    else:
        logger.error("模型未返回合法 JSON")
    raise JsonParseError("模型未返回合法 JSON")


def extract_response_text(resp: Any) -> str:
    choices = getattr(resp, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def extract(
    image_paths: list[str],
    settings: RuntimeSettings,
    default_topic: str | None = None,
    include_raw: bool = False,
    prompt_fn: Callable[[], str] = build_prompt,
    schema_fn: Callable[[], dict[str, Any]] = build_extraction_schema,
    default_chapter: str | None = None,
    default_section: str | None = None,
    batch_no: int | None = None,
    artifact_paths: Any = None,
    consensus_attempt: int | None = None,
) -> tuple[dict[str, Any], str | None, str | None, str | None]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt_fn()}]
    for p in image_paths:
        fmt = image_format(p)
        b64 = encode_image(p)
        content.append({"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{b64}"}})

    client = OpenAI(api_key=settings.api_key, base_url=settings.api_url, timeout=settings.request_timeout)
    kwargs: dict[str, Any] = {
        "model": settings.model_name,
        "messages": [{"role": "user", "content": content}],
        "temperature": settings.temperature,
        "max_tokens": settings.max_output_tokens,
        "seed": settings.seed,
        "extra_body": {"enable_thinking": settings.enable_thinking},
    }
    format_candidates: list[dict[str, Any] | None] = build_response_format_candidates(settings, schema_fn)
    last_error: Exception | None = None
    validated_result: dict[str, Any] | None = None
    validated_raw_content = ""
    result_topic: str | None = None
    result_chapter: str | None = None
    result_section: str | None = None

    for response_fmt in format_candidates:
        ensure_not_stopped()
        current_kwargs = dict(kwargs)
        if response_fmt is not None:
            current_kwargs["response_format"] = response_fmt
            logger.info("🧩 响应格式：%s", response_fmt["type"])
        else:
            logger.info("🧩 响应格式：text/未指定")

        try:
            ensure_not_stopped()
            wait_for_api_interval(settings.api_call_interval)
            started_at = time.time()
            logger.info("📡 已发送请求，等待模型响应…")
            stream = client.chat.completions.create(**current_kwargs, stream=True)
            chunks: list[str] = []
            thinking_chunks: list[str] = []
            first_token_logged = False
            thinking_logged = False
            thinking_output_pos = 0
            content_started = False

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    # 兼容多平台思考内容字段名 (reasoning_content / reasoning / model_extra)
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning is None:
                        reasoning = getattr(delta, "reasoning", None)
                    if reasoning is None and hasattr(delta, "model_extra"):
                        reasoning = delta.model_extra.get("reasoning_content") or delta.model_extra.get("reasoning")

                    if reasoning:
                        thinking_chunks.append(reasoning)
                        if not thinking_logged:
                            logger.info("🧠 模型思考中…")
                            if settings.debug_log_thinking:
                                print("\n" + "=" * 80 + "\n", end="", flush=True)
                            thinking_logged = True
                        if settings.debug_log_thinking:
                            full_thinking = "".join(thinking_chunks)
                            new_content = full_thinking[thinking_output_pos:]
                            if new_content:
                                print(new_content, end="", flush=True)
                                thinking_output_pos = len(full_thinking)
                    if delta.content:
                        text = delta.content
                        chunks.append(text)
                        now = time.time()
                        if not first_token_logged:
                            if thinking_chunks and settings.debug_log_thinking:
                                print("\n" + "=" * 80 + "\n", flush=True)
                            logger.info("📥 收到首个正式内容 token，耗时 %.1f 秒", now - started_at)
                            first_token_logged = True
                        if not content_started:
                            content_started = True

            if thinking_chunks:
                if settings.debug_log_thinking:
                    print("\n" + "=" * 80 + "\n", flush=True)
                logger.info("🧠 思考完成（共 %d 字符）", len("".join(thinking_chunks)))

            raw_text = "".join(chunks)
            elapsed = time.time() - started_at
            logger.info("📥 响应完成，用时 %.1f 秒，共 %d 字符", elapsed, len(raw_text))
            save_raw_response(
                raw_text,
                image_paths,
                batch_no=batch_no,
                attempt=consensus_attempt if consensus_attempt is not None else 1,
                artifact_paths=artifact_paths,
            )
            parsed_result = parse_json_response(raw_text)
            validated_result, result_topic, result_chapter, result_section = finalize_extract_result(
                parsed_result,
                default_topic=default_topic,
                default_chapter=default_chapter,
                default_section=default_section,
            )

            def _q_summary(q: dict[str, Any]) -> str:
                topic = q.get("topic") or "空"
                chapter = q.get("chapter") or "空"
                section = q.get("section") or "空"
                number = str(q.get("number", "")).strip() or "空"
                return f"{topic}/{chapter}/{section}#{number}"

            question_summaries = [_q_summary(q) for q in validated_result.get("questions", [])]
            if question_summaries:
                first_q = question_summaries[0]
                last_q = question_summaries[-1]
                if len(question_summaries) == 1:
                    summary_text = first_q
                else:
                    summary_text = f"{first_q} ~ {last_q}"
                logger.info(
                    "📚 本次提取结果：题目数=%d | 范围=%s",
                    len(question_summaries),
                    summary_text,
                )
            else:
                logger.info("📚 本次提取结果：题目数=0 | 范围=无")
            validated_raw_content = raw_text
            break

        except BadRequestError as e:
            last_error = e
            message = str(e)
            unsupported_format = (
                "response_format.type" in message or "json_object" in message or "json_schema" in message
            )
            if response_fmt is not None and unsupported_format:
                logger.warning("当前后端不支持响应格式 %s，回退后重试", response_fmt["type"])
                continue
            raise
        except (JsonParseError, ExtractionValidationError) as e:
            last_error = e
            logger.error("模型返回内容解析或校验失败：%s", e)
            raise
        except Exception as e:
            last_error = e
            logger.error("API调用失败：%s", e)
            raise

    if validated_result is None:
        raise last_error or RuntimeError("模型请求失败")
    result = validated_result or {}
    final_topic = result_topic if validated_result else None
    final_chapter = result_chapter if validated_result else None
    final_section = result_section if validated_result else None
    if include_raw:
        result["_raw_response"] = validated_raw_content
    return result, final_topic, final_chapter, final_section
