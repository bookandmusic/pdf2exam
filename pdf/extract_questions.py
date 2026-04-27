#!/usr/bin/env python3
"""
试卷题目提取器 —— 邻页上下文模式
支持 OpenAI 标准 API 接口，断点续跑、日志记录

用法:
  # 测试模式：指定一张图片，默认带前后邻页；解析后可输出或保存 JSON
  python extract_questions.py --test page_1.png

  # 生产模式：处理目录下所有图片（当前页带前后邻页）
  python extract_questions.py --dir ./scanned_pages --chapter "第二章"

  # 自定义模式：指定图片
  python extract_questions.py page_1.png page_2.png --chapter "第二章"

  # 输出到文件（支持续跑：已有的 JSON 不会被覆盖，追加新题）
  python extract_questions.py --dir ./pages -o questions.json --log extract.log
"""

import argparse
import base64
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError, OpenAI, RateLimitError

# ==================== 环境变量配置 ====================
API_KEY = ""
API_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 8192
IMAGES_PER_REQUEST = 3
DEFAULT_CONTEXT_PAGES = 1
DEFAULT_CONTEXT_PAGES_BEFORE = 1
DEFAULT_CONTEXT_PAGES_AFTER = 1
ENABLE_JSON_MODE = True
RESPONSE_FORMAT = "auto"
REQUEST_TIMEOUT = 180.0
REQUEST_RETRY_LIMIT = 5
REQUEST_RETRY_BASE_DELAY = 10.0
BATCH_DELAY_SECONDS = 5.0
DEBUG_LOG_RAW_RESPONSE = False
RAW_RESPONSE_DIR = ""
# =====================================================

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

logger = logging.getLogger("extract")
STOP_REQUESTED = False


class JsonParseError(Exception):
    pass


class RetryLimitExceededError(Exception):
    pass


def _env_int(name: str) -> Optional[int]:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return int(value)


def _env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_runtime_env(env_file: Optional[str] = None) -> Optional[Path]:
    global API_KEY, API_URL, MODEL_NAME, TEMPERATURE, MAX_OUTPUT_TOKENS
    global IMAGES_PER_REQUEST, DEFAULT_CONTEXT_PAGES, DEFAULT_CONTEXT_PAGES_BEFORE, DEFAULT_CONTEXT_PAGES_AFTER, ENABLE_JSON_MODE
    global RESPONSE_FORMAT, REQUEST_TIMEOUT, REQUEST_RETRY_LIMIT
    global REQUEST_RETRY_BASE_DELAY, BATCH_DELAY_SECONDS
    global DEBUG_LOG_RAW_RESPONSE, RAW_RESPONSE_DIR

    env_path = Path(env_file).expanduser() if env_file else Path.cwd() / ".env"
    env_loaded_path: Optional[Path] = None
    if env_path.exists():
        load_dotenv(env_path, override=True)
        env_loaded_path = env_path.resolve()

    API_KEY = os.getenv("API_KEY", "")
    API_URL = os.getenv("API_URL", "https://api.openai.com/v1")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))
    IMAGES_PER_REQUEST = int(os.getenv("IMAGES_PER_REQUEST", "3"))
    DEFAULT_CONTEXT_PAGES = int(os.getenv("CONTEXT_PAGES", "1"))
    DEFAULT_CONTEXT_PAGES_BEFORE = int(os.getenv("CONTEXT_PAGES_BEFORE", str(DEFAULT_CONTEXT_PAGES)))
    DEFAULT_CONTEXT_PAGES_AFTER = int(os.getenv("CONTEXT_PAGES_AFTER", str(DEFAULT_CONTEXT_PAGES)))
    ENABLE_JSON_MODE = os.getenv("ENABLE_JSON_MODE", "true").lower() in ("1", "true", "yes")
    RESPONSE_FORMAT = os.getenv("RESPONSE_FORMAT", "auto").lower()
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "180"))
    REQUEST_RETRY_LIMIT = int(os.getenv("REQUEST_RETRY_LIMIT", "5"))
    REQUEST_RETRY_BASE_DELAY = float(os.getenv("REQUEST_RETRY_BASE_DELAY", "10"))
    BATCH_DELAY_SECONDS = float(os.getenv("BATCH_DELAY_SECONDS", "5"))
    DEBUG_LOG_RAW_RESPONSE = os.getenv("DEBUG_LOG_RAW_RESPONSE", "false").lower() in ("1", "true", "yes")
    RAW_RESPONSE_DIR = os.getenv("RAW_RESPONSE_DIR", "").strip()

    return env_loaded_path


def _handle_sigint(signum, frame):
    del signum, frame
    global STOP_REQUESTED
    STOP_REQUESTED = True
    logger.warning("🛑 收到 Ctrl+C，当前步骤结束后停止程序")


def _sleep_with_interrupt(seconds: float) -> bool:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if STOP_REQUESTED:
            return False
        time.sleep(min(0.2, deadline - time.time()))
    return not STOP_REQUESTED


def _ensure_not_stopped():
    if STOP_REQUESTED:
        raise KeyboardInterrupt


def _build_response_format_candidates() -> List[Optional[dict]]:
    if not ENABLE_JSON_MODE:
        return [None]
    if RESPONSE_FORMAT == "text":
        return [None]
    if RESPONSE_FORMAT == "json_object":
        return [{"type": "json_object"}]
    if RESPONSE_FORMAT == "json_schema":
        # 当前脚本主要依赖提示词和后置解析，未维护 schema，本模式先退化为 text。
        logger.warning("RESPONSE_FORMAT=json_schema 暂未实现具体 schema，已回退为 text 模式")
        return [None]
    # auto: 先试 json_object，不支持则回退 text
    return [{"type": "json_object"}, None]


def _save_raw_response(raw: str, image_paths: List[str]) -> None:
    if not RAW_RESPONSE_DIR:
        return
    out_dir = Path(RAW_RESPONSE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_paths[0]).stem if image_paths else "response"
    if len(image_paths) > 1:
        stem = f"{stem}__{Path(image_paths[-1]).stem}"
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{ts}__{stem}.txt"
    out_path.write_text(raw, encoding="utf-8")
    logger.info("📝 已保存原始响应: %s", out_path)


# ---- 日志 ----

def setup_logging(log_path: Optional[str] = None):
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_path:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    # 静默库日志
    for lib in ("httpx", "httpcore", "openai._base_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ---- 工具函数 ----

def _image_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
        ".bmp": "bmp", ".tiff": "tiff", ".tif": "tiff", ".webp": "webp",
    }.get(ext, "png")


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _image_sequence(path: Path) -> Optional[int]:
    """提取图片文件名中的最后一段数字作为序号。"""
    matches = re.findall(r"(\d+)", path.stem)
    if not matches:
        return None
    return int(matches[-1])


def _sort_images(images: List[Path]) -> List[Path]:
    return sorted(
        images,
        key=lambda f: [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", f.stem)],
    )


def _resolve_test_images(image_path: str, context_pages: int = 1) -> List[Path]:
    target = Path(image_path).resolve()
    if not target.exists():
        logger.error("文件不存在: %s", image_path)
        sys.exit(1)

    siblings = [
        f for f in target.parent.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    images = _sort_images(siblings)
    try:
        index = images.index(target)
    except ValueError:
        return [target]

    left = max(0, index - max(0, context_pages))
    right = min(len(images), index + max(0, context_pages) + 1)
    return images[left:right]


def _normalize_chapter_text(chapter: Optional[str]) -> Optional[str]:
    if chapter is None:
        return None
    normalized = re.sub(r"\s+", " ", str(chapter)).strip()
    if not normalized:
        return None
    if normalized in {"默认", "未知", "未识别", "无", "N/A", "n/a", "null", "None"}:
        return None
    return normalized


def _split_chapter_context(chapter: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    normalized = _normalize_chapter_text(chapter)
    if not normalized:
        return None, None

    topic_match = re.search(r"(专题[一二三四五六七八九十百千万0-9]+[^第]*)", normalized)
    chapter_match = re.search(r"(第[一二三四五六七八九十百千万0-9]+[章节编][^第]*)", normalized)

    topic = topic_match.group(1).strip() if topic_match else None
    section = chapter_match.group(1).strip() if chapter_match else None
    return topic, section


def _resolve_chapter_context(
    previous_topic: Optional[str],
    previous_section: Optional[str],
    candidate: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    prev_topic = _normalize_chapter_text(previous_topic)
    prev_section = _normalize_chapter_text(previous_section)
    cand_topic, cand_section = _split_chapter_context(candidate)

    resolved_topic = cand_topic or prev_topic
    resolved_section = cand_section or prev_section
    resolved = _compose_chapter_context(resolved_topic, resolved_section)
    return resolved_topic, resolved_section, resolved


def _compose_chapter_context(topic: Optional[str], section: Optional[str]) -> Optional[str]:
    topic = _normalize_chapter_text(topic)
    section = _normalize_chapter_text(section)
    if topic and section:
        return f"{topic} {section}".strip()
    return topic or section


def _slugify_subject_id(value: str) -> str:
    normalized = re.sub(r"\.json$", "", value.strip(), flags=re.IGNORECASE)
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or "subject"


def _derive_subject_meta(
    output_path: Optional[str],
    subject_id: Optional[str],
    subject_name: Optional[str],
) -> Tuple[str, str]:
    stem = Path(output_path).stem if output_path else "subject"
    resolved_name = (subject_name or stem).strip() or "题库"
    resolved_id = _slugify_subject_id(subject_id or stem)
    return resolved_id, resolved_name


def _to_builtin_subject(
    questions: list,
    subject_id: str,
    subject_name: str,
) -> dict:
    chapter_ids: dict[str, str] = {}
    chapters: list[dict] = []
    built_questions: list[dict] = []

    def ensure_chapter_id(chapter_name: str) -> str:
        normalized = _normalize_chapter_text(chapter_name) or "默认"
        if normalized not in chapter_ids:
            chapter_ids[normalized] = f"{subject_id}-ch{len(chapter_ids) + 1}"
            chapters.append({"id": chapter_ids[normalized], "name": normalized})
        return chapter_ids[normalized]

    for idx, q in enumerate(questions, start=1):
        chapter_name = _normalize_chapter_text(q.get("chapter")) or "默认"
        chapter_id = ensure_chapter_id(chapter_name)
        raw_options = q.get("options", [])
        if isinstance(raw_options, dict):
            options = {str(k): str(v) for k, v in raw_options.items()}
        else:
            options = {
                str(opt.get("label", "")): str(opt.get("text", ""))
                for opt in raw_options
                if isinstance(opt, dict) and opt.get("label")
            }
        answer = str(q.get("correct_answer") or q.get("answer") or "")
        explicit_type = str(q.get("type") or "").strip().lower()
        inferred_type = "multiple" if len(re.findall(r"[A-Z]", answer)) > 1 else "single"
        q_type = explicit_type if explicit_type in {"single", "multiple"} else inferred_type

        built = {
            "id": q.get("id") or f"{subject_id}-q{idx}",
            "number": str(q.get("number", idx)),
            "chapter": chapter_name,
            "question": q.get("question") or q.get("title") or "",
            "options": options,
            "answer": answer,
            "type": q_type,
            "knowledge": q.get("knowledge") or q.get("analysis") or "",
            "chapterId": chapter_id,
        }
        if q_type == "multiple":
            built["answers"] = re.findall(r"[A-Z]", answer)
        built_questions.append(built)

    return {
        "id": subject_id,
        "name": subject_name,
        "chapters": chapters,
        "questions": built_questions,
    }


def _serialize_subject(
    questions: list,
    output_path: Optional[str],
    subject_id: Optional[str],
    subject_name: Optional[str],
) -> dict:
    resolved_id, resolved_name = _derive_subject_meta(output_path, subject_id, subject_name)
    return _to_builtin_subject(questions, resolved_id, resolved_name)


def _update_context_state(
    current_topic: Optional[str],
    current_section: Optional[str],
    candidate: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    cand_topic, cand_section = _split_chapter_context(candidate)
    if cand_topic:
        current_topic = cand_topic
    if cand_section:
        current_section = cand_section
    return current_topic, current_section


def _merge_chapter_context(previous: Optional[str], candidate: Optional[str]) -> Optional[str]:
    previous_norm = _normalize_chapter_text(previous)
    candidate_norm = _normalize_chapter_text(candidate)

    if not candidate_norm:
        return previous_norm
    if not previous_norm:
        return candidate_norm
    if candidate_norm == previous_norm:
        return candidate_norm
    if candidate_norm in previous_norm:
        return previous_norm

    prev_topic, prev_section = _split_chapter_context(previous_norm)
    cand_topic, cand_section = _split_chapter_context(candidate_norm)

    if cand_topic and cand_section:
        return f"{cand_topic} {cand_section}".strip()
    if cand_section and prev_topic:
        return f"{prev_topic} {cand_section}".strip()
    if cand_topic and not cand_section:
        return cand_topic
    if not cand_topic and not cand_section:
        return previous_norm
    if cand_section:
        return cand_section
    if cand_topic:
        if prev_section and cand_topic != prev_topic:
            return cand_topic
        return f"{cand_topic} {prev_section}".strip() if prev_section else cand_topic

    return candidate_norm


def _build_prompt(chapter: Optional[str] = None) -> str:
    known = f"\n已知上一页延续下来的专题/章节：{chapter}" if chapter else ""
    fallback = f'则必须沿用已知的「{chapter}」' if chapter else '则填入「默认」'
    return f"""你是专业的中文试卷题目提取器。
现在给你几张连续的试卷页，提取其中所有**完整**的选择题。{known}

**专题/章节识别**：
- 从图片中识别每道题所属的专题、章、节标题（通常在页面顶部、页眉或边栏位置）。
- `chapter` 字段必须尽量填写完整路径，优先写成“专题X ... 第X章 ... 第X节 ...”这种完整形式，不要只写“第一章”这种残缺标题。
- 只要页面中存在“专题X ...”标题，就必须识别并写入；只要页面中存在“第X章 ...”标题，也必须识别并写入。
- 如果同时能识别到“专题X ...”和“第X章 ...”，返回时必须组合成完整路径，例如“专题一 民法典总则编 第三章 法人和非法人组织”。
- 如果当前页只有“第X章 ...”而没有新的“专题X ...”，则必须使用已知上一页的专题补全，禁止只返回“第X章 ...”。
- 如果当前页只有新的“专题X ...”而没有新的“第X章 ...”，则必须沿用已知上一页的“第X章 ...”补全，禁止只返回“专题X ...”。
- 除非图片中完全看不到专题和章节信息，且也没有任何已知上下文，否则禁止输出“默认”、空字符串、仅章名、仅专题名这类不完整值。
- 如果当前页只有题目，没有新的专题或章节标题，{fallback}，不要凭空新建章节，也不要把已有专题或章节丢掉。
- 如果当前页只出现了新的“第X章/第X节”，但没有新的“专题X”，则沿用上一页的专题，只更新章/节。
- 如果当前页出现了新的专题标题，则从该题开始切换到新专题；若同页又出现对应章节标题，则组合成完整标题。
- 不同题目可能属于不同章节（例如跨章节边界时），请为每道题单独填写 chapter 字段。
- 大多数情况下同批题目属于同一章节，顶层 chapter 作为整批默认值。

**跨页处理规则**：
- 如果一道题的题干或选项跨了多页，必须将它们拼接成一道完整的题目返回。
- 如果一道题在当前页末尾明显未结束（例如只有题干开头，选项缺失），则**不要**输出该题，留到下一批处理。

**输出格式**（严格的 JSON，不要包含任何其他内容）：
{{
  "chapter": "整批题目的默认章节名",
  "questions": [
    {{
      "number": "题目序号（如 1、2、3，从试卷上获取的数字）",
      "chapter": "该题所属章节（如果与顶层不同则必填，相同则留空或省略；如填写，必须是完整的专题+章路径）",
      "title": "完整题目标题（包含所有文字描述）",
      "options": [
        {{"label": "A", "text": "选项A内容"}},
        {{"label": "B", "text": "选项B内容"}}
      ],
      "correct_answer": "正确选项的字母，例如 B",
      "analysis": "答案解析文本，如果没有则留空字符串"
    }}
  ]
}}
如果这些页面中没有任何完整题目，返回 {{"chapter": "章节名", "questions": []}}"""


def _parse_json_response(raw: str) -> dict:
    """从模型响应中提取 JSON，兼容纯 JSON、markdown ```json 代码块和普通文本。"""
    text = raw.strip()

    def _repair_common_json_issues(snippet: str) -> str:
        # 修复模型偶发输出的选项对象缺少 "text" 键的问题：
        # {"label":"D","某段文字"} -> {"label":"D","text":"某段文字"}
        pattern = re.compile(
            r'(\{\s*"label"\s*:\s*"[^"]+"\s*,\s*)(?!"text"\s*:)"([^"\\]*(?:\\.[^"\\]*)*)"\s*\}'
        )
        return pattern.sub(r'\1"text": "\2"}', snippet)

    def _pick_better(best_obj: Optional[dict], candidate: dict) -> dict:
        candidate.setdefault("chapter", None)
        if best_obj is None:
            return candidate
        if len(candidate.get("questions", [])) > len(best_obj.get("questions", [])):
            return candidate
        return best_obj

    def _try_parse_candidate(snippet: str) -> Tuple[Optional[dict], Optional[Tuple[str, json.JSONDecodeError, str]]]:
        snippet = snippet.strip()
        if not snippet:
            return None, None
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict) and "questions" in obj:
                return obj, None
            return None, None
        except json.JSONDecodeError as err:
            repaired = _repair_common_json_issues(snippet)
            if repaired != snippet:
                try:
                    obj = json.loads(repaired)
                    if isinstance(obj, dict) and "questions" in obj:
                        return obj, None
                except json.JSONDecodeError as repaired_err:
                    return None, ("repaired", repaired_err, repaired)
            return None, ("raw", err, snippet)

    def _extract_fenced_blocks(source: str) -> List[str]:
        blocks: List[str] = []
        fenced_patterns = [
            r"```json\s*(.*?)\s*```",
            r"```JSON\s*(.*?)\s*```",
            r"```\s*(\{.*?\})\s*```",
        ]
        for pattern in fenced_patterns:
            for match in re.finditer(pattern, source, flags=re.DOTALL):
                blocks.append(match.group(1).strip())
        return blocks

    def _extract_json_objects(source: str) -> List[str]:
        objects: List[str] = []
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

    best: Optional[dict] = None
    best_error = None
    candidates = [text]
    candidates.extend(_extract_fenced_blocks(text))
    candidates.extend(_extract_json_objects(text))

    for snippet in candidates:
        obj, error = _try_parse_candidate(snippet)
        if obj is not None:
            best = _pick_better(best, obj)
            continue
        if error and best_error is None:
            best_error = error

    if best is not None:
        return best

    if best_error:
        kind, err, snippet = best_error
        logger.error(
            "模型 JSON 解析失败（%s）: %s at line %d column %d (char %d)\n片段:\n%s",
            kind,
            err.msg,
            err.lineno,
            err.colno,
            err.pos,
            snippet,
        )
    logger.error("模型未返回合法 JSON:\n%s", raw)
    raise JsonParseError("模型未返回合法 JSON")


def _extract_response_text(resp) -> str:
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
    image_paths: List[str],
    chapter: Optional[str] = None,
    include_raw: bool = False,
) -> dict:
    """调用远程 API 提取题目，返回 {"chapter": ..., "questions": [...]}。
    每道题目会被自动注入 chapter 字段，形成 (chapter, number) 唯一标识。
    """
    content: list = [{"type": "text", "text": _build_prompt(chapter)}]
    for p in image_paths:
        fmt = _image_format(p)
        b64 = _encode_image(p)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/{fmt};base64,{b64}"},
        })

    client = OpenAI(api_key=API_KEY, base_url=API_URL, timeout=REQUEST_TIMEOUT)
    kwargs = dict(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": content}],
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    format_candidates = _build_response_format_candidates()
    last_error = None
    resp = None
    for fmt in format_candidates:
        _ensure_not_stopped()
        current_kwargs = dict(kwargs)
        if fmt is not None:
            current_kwargs["response_format"] = fmt
            logger.info("🧩 响应格式：%s", fmt["type"])
        else:
            logger.info("🧩 响应格式：text/未指定")

        for attempt in range(1, REQUEST_RETRY_LIMIT + 1):
            try:
                _ensure_not_stopped()
                started_at = time.time()
                resp = client.chat.completions.create(**current_kwargs)
                elapsed = time.time() - started_at
                raw_text = _extract_response_text(resp)
                logger.info("📥 已收到模型响应，用时 %.1f 秒，长度 %d 字符", elapsed, len(raw_text))
                if DEBUG_LOG_RAW_RESPONSE:
                    preview = raw_text[:500].replace("\n", "\\n")
                    logger.info("📄 原始响应预览: %s", preview)
                _save_raw_response(raw_text, image_paths)
                _parse_json_response(raw_text)
                break
            except JsonParseError as e:
                last_error = e
                if attempt >= REQUEST_RETRY_LIMIT:
                    logger.error("模型返回内容连续 %d 次无法解析为 JSON，停止重试", REQUEST_RETRY_LIMIT)
                    raise RetryLimitExceededError(str(e)) from e
                delay = REQUEST_RETRY_BASE_DELAY * attempt
                logger.warning(
                    "模型 JSON 解析失败，第 %d/%d 次重试前等待 %.1f 秒",
                    attempt,
                    REQUEST_RETRY_LIMIT,
                    delay,
                )
                if not _sleep_with_interrupt(delay):
                    raise KeyboardInterrupt
            except BadRequestError as e:
                last_error = e
                message = str(e)
                unsupported_format = (
                    "response_format.type" in message
                    or "json_object" in message
                    or "json_schema" in message
                )
                if fmt is not None and unsupported_format:
                    logger.warning("当前后端不支持响应格式 %s，回退后重试", fmt["type"])
                    break
                raise
            except RateLimitError as e:
                last_error = e
                if attempt >= REQUEST_RETRY_LIMIT:
                    logger.error("请求限流（429）连续 %d 次，停止重试", REQUEST_RETRY_LIMIT)
                    raise RetryLimitExceededError("请求限流（429）重试耗尽") from e
                delay = REQUEST_RETRY_BASE_DELAY * attempt
                logger.warning("请求限流（429），第 %d/%d 次重试前等待 %.1f 秒", attempt, REQUEST_RETRY_LIMIT, delay)
                if not _sleep_with_interrupt(delay):
                    raise KeyboardInterrupt
            except (APITimeoutError, APIConnectionError) as e:
                last_error = e
                if attempt >= REQUEST_RETRY_LIMIT:
                    raise
                delay = min(60.0, REQUEST_RETRY_BASE_DELAY * attempt)
                logger.warning("请求超时或连接失败，第 %d/%d 次重试前等待 %.1f 秒：%s", attempt, REQUEST_RETRY_LIMIT, delay, e)
                if not _sleep_with_interrupt(delay):
                    raise KeyboardInterrupt
            except APIStatusError as e:
                last_error = e
                retryable = e.status_code >= 500 or e.status_code == 408
                if not retryable or attempt >= REQUEST_RETRY_LIMIT:
                    raise
                delay = min(60.0, REQUEST_RETRY_BASE_DELAY * attempt)
                logger.warning("接口临时错误（HTTP %s），第 %d/%d 次重试前等待 %.1f 秒", e.status_code, attempt, REQUEST_RETRY_LIMIT, delay)
                if not _sleep_with_interrupt(delay):
                    raise KeyboardInterrupt
        if resp is not None:
            break
    if resp is None:
        raise last_error or RuntimeError("模型请求失败")

    raw_content = _extract_response_text(resp)
    result = _parse_json_response(raw_content)

    # 逐题解析章节：优先用题目自己的 chapter，否则用顶层默认值。
    # 当当前页没有出现新的专题/章节时，持续沿用上一批上下文。
    current_topic, current_section = _split_chapter_context(chapter)
    current_topic, current_section, batch_default = _resolve_chapter_context(
        current_topic, current_section, result.get("chapter")
    )
    if not batch_default:
        batch_default = "默认"
    for q in result.get("questions", []):
        current_topic, current_section, q_chapter = _resolve_chapter_context(
            current_topic, current_section, q.get("chapter")
        )
        if not q_chapter:
            q_chapter = batch_default
        q["chapter"] = q_chapter
        if "number" in q and not isinstance(q["number"], str):
            q["number"] = str(q["number"])
    result["chapter"] = batch_default
    if include_raw:
        result["_raw_response"] = raw_content

    return result


def _collect_images(dir_path: str) -> List[Path]:
    p = Path(dir_path)
    if not p.is_dir():
        logger.error("目录不存在: %s", dir_path)
        sys.exit(1)
    images = _sort_images([f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS])
    if not images:
        logger.error("目录中无支持的图片: %s", dir_path)
        sys.exit(1)
    return images


def _load_existing(output_path: Optional[str]) -> Tuple[list, set]:
    """读取已有 JSON，返回 (questions, seen_set)。"""
    if not output_path:
        return [], set()
    p = Path(output_path)
    if not p.exists():
        logger.info("输出文件不存在，将从零开始")
        return [], set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        qs = data.get("questions", []) if isinstance(data, dict) else []
        normalized_qs = []
        for q in qs:
            if not isinstance(q, dict):
                continue
            if "title" in q or "correct_answer" in q:
                normalized_qs.append(q)
                continue
            normalized_qs.append({
                "id": q.get("id"),
                "number": str(q.get("number", "")),
                "chapter": q.get("chapter"),
                "title": q.get("title") or q.get("question") or "",
                "options": q.get("options", {}),
                "correct_answer": q.get("correct_answer") or q.get("answer") or "",
                "analysis": q.get("analysis") or q.get("knowledge") or "",
                "type": q.get("type"),
            })
        seen = {
            (_normalize_chapter_text(q.get("chapter")) or "", str(q.get("number", "")))
            for q in normalized_qs
            if q.get("number")
        }
        logger.info("读取已有文件: %s（%d 道题目）", output_path, len(normalized_qs))
        return normalized_qs, seen
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("读取已有文件失败，将从零开始: %s", e)
        return [], set()


def process_directory(
    dir_path: str,
    chapter: Optional[str] = None,
    window: Optional[int] = None,
    step: Optional[int] = None,
    context: Optional[int] = None,
    context_before: Optional[int] = None,
    context_after: Optional[int] = None,
    start_from: Optional[int] = None,
    existing_qs: Optional[list] = None,
    existing_seen: Optional[set] = None,
    output_path: Optional[str] = None,
    trace_log_path: Optional[str] = None,
    subject_id: Optional[str] = None,
    subject_name: Optional[str] = None,
) -> Tuple[list, str]:
    """
    生产模式：按主批次页数处理，并附带前后邻页上下文。

    step 表示每批主处理页数，context 表示主批次前后各带几页上下文。
    例如 step=5, context=1 时，35 起批次为 34+[35..39]+40，下一批为 39+[40..44]+45。

    利用 (chapter, number) 去重，避免邻页窗口重叠导致的重复提取。
    output_path 不为空时，每批处理完实时落盘。

    返回 (new_questions, resolved_chapter)。
    章节优先级：图片识别 > CLI 参数 > "默认"
    """
    images = _collect_images(dir_path)
    if step is None:
        step_size = 1
        legacy_window = max(3, window or IMAGES_PER_REQUEST)
        if legacy_window % 2 == 0:
            legacy_window += 1
        context_pages_before = legacy_window // 2
        context_pages_after = legacy_window // 2
    else:
        step_size = max(1, step)
        default_before = DEFAULT_CONTEXT_PAGES_BEFORE
        default_after = DEFAULT_CONTEXT_PAGES_AFTER
        if context is not None:
            default_before = max(0, context)
            default_after = max(0, context)
        context_pages_before = default_before if context_before is None else max(0, context_before)
        context_pages_after = default_after if context_after is None else max(0, context_after)
    n = len(images)

    start_index = 0
    if start_from is not None:
        for idx, image in enumerate(images):
            seq = _image_sequence(image)
            if seq is not None and seq >= start_from:
                start_index = idx
                logger.info("⏭️  从图片序号 %d 开始处理，保留前后邻页上下文", start_from)
                break
        else:
            logger.error("目录中没有序号大于等于 %d 的图片: %s", start_from, dir_path)
            sys.exit(1)

    logger.info(
        "📸 %d 张图片 | 主批次 %d 页 | 前文 %d 页 | 后文 %d 页",
        n, step_size, context_pages_before, context_pages_after
    )
    logger.info("⚙️  %s | %s", MODEL_NAME, API_URL)
    if trace_log_path:
        logger.info("🧾 题目追踪日志：%s", trace_log_path)

    all_qs: list = []
    seen: set = set(existing_seen or [])
    total_from_prev = len(existing_qs or [])
    batch_no = 0
    detected_chapter = chapter
    current_topic, current_section = _split_chapter_context(chapter)
    chapters_found: set = set()

    i = start_index
    while i < n:
        if STOP_REQUESTED:
            logger.warning("🛑 已停止后续批次，保留当前已提取结果")
            break
        core_end = min(n, i + step_size)
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
        batch_state_before = _compose_chapter_context(current_topic, current_section) or detected_chapter or "默认"

        result = extract(paths, detected_chapter)
        current_topic, current_section, result_chapter = _resolve_chapter_context(
            current_topic, current_section, result.get("chapter")
        )
        if result_chapter:
            detected_chapter = result_chapter
            chapters_found.add(result_chapter)
        batch_state_after = _compose_chapter_context(current_topic, current_section) or detected_chapter or "默认"

        qs = result.get("questions", [])
        new_qs = []
        trace_questions = []
        for q in qs:
            current_topic, current_section, q_chapter = _resolve_chapter_context(
                current_topic, current_section, q.get("chapter")
            )
            if q_chapter and q_chapter not in ("默认", ""):
                detected_chapter = q_chapter
                q["chapter"] = q_chapter
            chapters_found.add(q_chapter)
            key = (q_chapter, str(q.get("number", "")))
            is_new = key not in seen
            trace_questions.append({
                "number": str(q.get("number", "")),
                "chapter": q_chapter,
                "title": q.get("title", ""),
                "source_images": batch_image_names,
                "dedupe_key": [q_chapter, str(q.get("number", ""))],
                "is_new": is_new,
            })
            if key not in seen:
                seen.add(key)
                new_qs.append(q)

        _append_trace_log(trace_log_path, {
            "type": "batch",
            "batch_no": batch_no,
            "core_images": [images[i].name, images[core_end - 1].name],
            "source_images": batch_image_names,
            "state_before": batch_state_before,
            "model_batch_chapter": result.get("chapter"),
            "state_after": batch_state_after,
            "question_count": len(qs),
            "new_question_count": len(new_qs),
            "questions": trace_questions,
        })

        if new_qs:
            all_qs.extend(new_qs)
            logger.info("✅ 提取 %d 道（跳过 %d 道重复）", len(new_qs), len(qs) - len(new_qs))
        else:
            logger.info("⚠️  未提取到新题目")

        # 每个批次都实时落盘，避免中途停止或空批次时没有最新文件。
        if output_path:
            merged = (existing_qs or []) + all_qs
            _dump_inner(_serialize_subject(merged, output_path, subject_id, subject_name), output_path)
            logger.info("💾 已实时写入: %s（累计 %d 道）", output_path, len(merged))

        if BATCH_DELAY_SECONDS > 0 and core_end < n:
            logger.info("⏳ 批次节流，等待 %.1f 秒后继续", BATCH_DELAY_SECONDS)
            if not _sleep_with_interrupt(BATCH_DELAY_SECONDS):
                logger.warning("🛑 已在批次等待期间停止，保留当前已提取结果")
                break

        i += step_size

    resolved = detected_chapter or chapter or "默认"
    if chapters_found:
        chapters_found.add(resolved)
    return all_qs, sorted(chapters_found) if chapters_found else [resolved]


def _dump_inner(data: dict, output_path: str):
    """静默写入（不打印日志，避免刷屏）。"""
    Path(output_path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def _dump(data: dict, output_path: Optional[str] = None):
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        logger.info("💾 已写入: %s", output_path)
    else:
        print(text)


def _resolve_trace_log_path(output_path: Optional[str], trace_log_path: Optional[str]) -> Optional[str]:
    if trace_log_path:
        return trace_log_path
    if output_path:
        output = Path(output_path)
        return str(output.with_name(f"{output.stem}.trace.jsonl"))
    return None


def _append_trace_log(trace_log_path: Optional[str], payload: dict) -> None:
    if not trace_log_path:
        return
    path = Path(trace_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        f.flush()


def main():
    signal.signal(signal.SIGINT, _handle_sigint)
    parser = argparse.ArgumentParser(
        description="试卷题目提取器（OpenAI 标准 API）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "环境变量配置（.env 文件）：\n"
            "  API_KEY               API 密钥\n"
            "  API_URL               API 地址（默认 https://api.openai.com/v1）\n"
            "  MODEL_NAME            模型名（默认 gpt-4o）\n"
            "  --env-file            指定 .env 文件；未指定时读取当前运行目录下的 .env\n"
            "  IMAGES_PER_REQUEST    兼容旧参数：未指定 --step 时的总窗口页数（默认 3）\n"
            "  CONTEXT_PAGES         指定 --step 时，前后附带的上下文页数（默认 1）\n"
            "  CONTEXT_PAGES_BEFORE  指定 --step 时，主批次前附带页数（默认与 CONTEXT_PAGES 相同）\n"
            "  CONTEXT_PAGES_AFTER   指定 --step 时，主批次后附带页数（默认与 CONTEXT_PAGES 相同）\n"
            "  STEP                  生产模式默认主批次页数\n"
            "  START_FROM            生产模式默认起始图片序号\n"
            "  CHAPTER               默认章节名称\n"
            "  SUBJECT_ID            默认题库 ID\n"
            "  SUBJECT_NAME          默认题库名称\n"
            "  OUTPUT_PATH           默认输出文件路径\n"
            "  LOG_PATH              默认日志文件路径\n"
            "  TRACE_LOG_PATH        默认题目追踪日志文件路径\n"
            "  RESPONSE_FORMAT       auto/json_object/text（默认 auto）\n"
            "  REQUEST_TIMEOUT       单次请求超时秒数（默认 180）\n"
            "  REQUEST_RETRY_LIMIT   单次请求失败后的最大重试次数（默认 5）\n"
            "  REQUEST_RETRY_BASE_DELAY  重试基础等待秒数，按次数递增（默认 10）\n"
            "  BATCH_DELAY_SECONDS   批次之间固定等待秒数（默认 5）\n"
            "  DEBUG_LOG_RAW_RESPONSE  是否在日志中打印原始响应预览（默认 false）\n"
            "  RAW_RESPONSE_DIR      原始响应保存目录（默认不保存）\n"
            "  TEMPERATURE           温度参数（默认 0.1）\n"
            "  MAX_OUTPUT_TOKENS     最大输出 token（默认 8192）\n"
            "  ENABLE_JSON_MODE      响应格式 JSON 模式开关（默认 true，不支持可关闭）"
        ),
    )

    group = parser.add_argument_group("模式（三选一）")
    group.add_argument("--test", metavar="IMAGE", help="测试模式：指定一张图片，默认带前后邻页一起处理")
    group.add_argument("--dir", metavar="DIR", help="生产模式：处理目录下所有图片")
    parser.add_argument("images", nargs="*", metavar="image", help="待处理图片路径")
    parser.add_argument("--chapter", help="章节名称")
    parser.add_argument("--window", type=int, default=None, help=f"兼容旧模式：未指定 --step 时的总窗口大小，建议奇数（默认 {IMAGES_PER_REQUEST}）")
    parser.add_argument("--step", type=int, default=None, help="生产模式：每批主处理页数，例如 5 表示一次主处理 5 页")
    parser.add_argument("--context", type=int, default=None, help=f"生产模式：主批次前后各附带几页上下文（默认 {DEFAULT_CONTEXT_PAGES}）")
    parser.add_argument("--context-before", type=int, default=None, help=f"生产模式：主批次前附带几页上下文（默认 {DEFAULT_CONTEXT_PAGES_BEFORE}）")
    parser.add_argument("--context-after", type=int, default=None, help=f"生产模式：主批次后附带几页上下文（默认 {DEFAULT_CONTEXT_PAGES_AFTER}）")
    parser.add_argument("--start-from", type=int, help="生产模式：从文件名数字序号大于等于该值的主批次起始页开始处理，例如 35 配合 --step 5 表示主批次从 35-39 开始；仍会保留前后上下文")
    parser.add_argument("-o", "--output", help="输出 JSON 文件（默认 stdout；文件已存在时自动续跑，依 (chapter, number) 去重）")
    parser.add_argument("--log", help="日志文件路径（默认不记录日志文件）")
    parser.add_argument("--trace-log", help="题目追踪日志文件路径（默认：输出文件同目录下的 *.trace.jsonl）")
    parser.add_argument("--env-file", help="指定 .env 文件路径；未指定时默认读取当前运行目录下的 .env")
    parser.add_argument("--subject-id", help="输出为内置题库时使用的题库 ID；默认取输出文件名")
    parser.add_argument("--subject-name", help="输出为内置题库时使用的题库名称；默认取输出文件名")

    args = parser.parse_args()
    env_loaded_path = load_runtime_env(args.env_file)
    if args.chapter is None:
        args.chapter = _env_str("CHAPTER")
    if args.window is None:
        args.window = _env_int("WINDOW")
    if args.step is None:
        args.step = _env_int("STEP")
    if args.context is None:
        args.context = _env_int("CONTEXT")
        if args.context is None:
            args.context = _env_int("CONTEXT_PAGES")
    if args.context_before is None:
        args.context_before = _env_int("CONTEXT_BEFORE")
        if args.context_before is None:
            args.context_before = _env_int("CONTEXT_PAGES_BEFORE")
    if args.context_after is None:
        args.context_after = _env_int("CONTEXT_AFTER")
        if args.context_after is None:
            args.context_after = _env_int("CONTEXT_PAGES_AFTER")
    if args.start_from is None:
        args.start_from = _env_int("START_FROM")
    if args.output is None:
        args.output = _env_str("OUTPUT_PATH")
    if args.log is None:
        args.log = _env_str("LOG_PATH")
    if args.trace_log is None:
        args.trace_log = _env_str("TRACE_LOG_PATH")
    if args.subject_id is None:
        args.subject_id = _env_str("SUBJECT_ID")
    if args.subject_name is None:
        args.subject_name = _env_str("SUBJECT_NAME")

    setup_logging(args.log)
    trace_log_path = _resolve_trace_log_path(args.output, args.trace_log)
    if args.env_file and env_loaded_path is None:
        logger.warning("指定的 .env 文件不存在: %s，将仅使用当前进程环境变量", args.env_file)
    elif env_loaded_path is not None:
        logger.info("🧪 已加载 .env: %s", env_loaded_path)
    else:
        logger.info("🧪 当前运行目录下未找到 .env，将仅使用当前进程环境变量")

    # ---- 测试模式 ----
    if args.test:
        p = args.test
        if not Path(p).exists():
            logger.error("文件不存在: %s", p)
            sys.exit(1)
        test_images = _resolve_test_images(p, context_pages=1)
        logger.info(
            "🧪 测试模式：目标页 %s，实际发送 %d 张图片: %s",
            Path(p).name,
            len(test_images),
            ", ".join(image.name for image in test_images),
        )
        result = extract([str(image) for image in test_images], chapter=args.chapter, include_raw=True)
        raw_response = result.pop("_raw_response", "")
        _append_trace_log(trace_log_path, {
            "type": "test",
            "target_image": Path(p).name,
            "source_images": [image.name for image in test_images],
            "input_chapter": args.chapter,
            "result_chapter": result.get("chapter"),
            "questions": [
                {
                    "number": str(q.get("number", "")),
                    "chapter": q.get("chapter"),
                    "title": q.get("title", ""),
                    "source_images": [image.name for image in test_images],
                }
                for q in result.get("questions", [])
            ],
        })
        parsed = _serialize_subject(
            result.get("questions", []),
            args.output,
            args.subject_id,
            args.subject_name,
        )
        logger.info("📄 模型原始响应如下：\n%s", raw_response)
        _dump(parsed, args.output)
        return

    # ---- 生产模式 ----
    if args.dir:
        existing_qs, existing_seen = _load_existing(args.output)
        if existing_qs:
            logger.info("↩️  续跑模式：已有 %d 道题目，将追加新题", len(existing_qs))

        new_qs, all_chapters = process_directory(
            args.dir, args.chapter, args.window,
            step=args.step, context=args.context,
            context_before=args.context_before,
            context_after=args.context_after,
            start_from=args.start_from,
            existing_qs=existing_qs, existing_seen=existing_seen,
            output_path=args.output,
            trace_log_path=trace_log_path,
            subject_id=args.subject_id,
            subject_name=args.subject_name,
        )

        merged = existing_qs + new_qs
        chapters_str = "、".join(all_chapters)
        logger.info("📊 共 %d 道题目（原有 %d，新增 %d）", len(merged), len(existing_qs), len(new_qs))
        logger.info("📚 章节：%s", chapters_str)
        if args.output:
            _dump(_serialize_subject(merged, args.output, args.subject_id, args.subject_name), args.output)
        return

    # ---- 默认模式 ----
    if not args.images:
        parser.print_help()
        sys.exit(1)

    for p in args.images:
        if not Path(p).exists():
            logger.error("文件不存在: %s", p)
            sys.exit(1)

    logger.info("📸 处理 %d 张图片", len(args.images))
    result = extract(args.images, chapter=args.chapter)
    _append_trace_log(trace_log_path, {
        "type": "single",
        "source_images": [Path(p).name for p in args.images],
        "input_chapter": args.chapter,
        "result_chapter": result.get("chapter"),
        "questions": [
            {
                "number": str(q.get("number", "")),
                "chapter": q.get("chapter"),
                "title": q.get("title", ""),
                "source_images": [Path(p).name for p in args.images],
            }
            for q in result.get("questions", [])
        ],
    })
    _dump(
        _serialize_subject(
            result.get("questions", []),
            args.output,
            args.subject_id,
            args.subject_name,
        ),
        args.output,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("程序已按用户请求停止")
        sys.exit(0)
    except RetryLimitExceededError as e:
        logger.error("处理失败：%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("处理失败：%s", e)
        sys.exit(1)
