import signal
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

import eq_common
from eq_common import handle_sigint, logger
from eq_extract import build_extraction_schema, build_prompt, extract
from eq_io import (
    dump,
    ensure_files_exist,
    load_existing,
    resolve_test_images,
    setup_logging,
)
from eq_models import RetryLimitExceededError
from eq_output import serialize_subject
from eq_process import process_directory, verify_existing_directory
from eq_settings import CliOptions, RuntimeSettings, load_runtime_settings, validate_runtime_mode

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def resolve_cli_options(raw_options: dict[str, object]) -> CliOptions:
    return CliOptions.model_validate(raw_options)


def merge_cli_with_settings(options: CliOptions, settings: RuntimeSettings) -> CliOptions:
    merged = options.model_dump()
    merged["test_image"] = options.test_image or settings.test_image
    merged["input_dir"] = options.input_dir or settings.input_dir
    merged["default_topic"] = options.default_topic or settings.default_topic
    merged["step"] = options.step if options.step is not None else settings.step
    # context 参数可以同时设置前后页数
    if options.context is not None:
        merged["context_before"] = options.context
        merged["context_after"] = options.context
    # context_before/after 优先级更高
    if options.context_before is not None:
        merged["context_before"] = options.context_before
    else:
        merged["context_before"] = merged.get("context_before") or settings.context_pages_before
    if options.context_after is not None:
        merged["context_after"] = options.context_after
    else:
        merged["context_after"] = merged.get("context_after") or settings.context_pages_after
    merged["start_from"] = options.start_from if options.start_from is not None else settings.start_from
    merged["end_at"] = options.end_at if options.end_at is not None else settings.end_at
    merged["artifact_dir"] = options.artifact_dir or settings.artifact_dir
    merged["artifact_name"] = options.artifact_name or settings.artifact_name
    merged["subject_id"] = options.subject_id or settings.subject_id
    merged["subject_name"] = options.subject_name or settings.subject_name
    merged["consensus"] = options.consensus if options.consensus is not None else settings.consensus
    merged["default_chapter"] = options.default_chapter or settings.default_chapter
    merged["default_section"] = options.default_section or settings.default_section
    return validate_runtime_mode(CliOptions.model_validate(merged))


def log_env_source(env_file: str | None, env_loaded_path: Path | None) -> None:
    if env_file and env_loaded_path is None:
        logger.warning("指定的 .env 文件不存在: %s，将仅使用当前进程环境变量", env_file)
    elif env_loaded_path is not None:
        logger.info("🧪 已加载 .env: %s", env_loaded_path)
    else:
        logger.info("🧪 当前运行目录下未找到 .env，将仅使用当前进程环境变量")


def run_test_mode(options: CliOptions, settings: RuntimeSettings) -> None:
    assert options.test_image is not None
    ensure_files_exist([options.test_image])
    cb = options.context_before if options.context_before is not None else 1
    test_images = resolve_test_images(options.test_image, context_before=cb)
    image_names = ", ".join(image.name for image in test_images)
    logger.info(
        "🧪 测试模式：目标页 %s，实际发送 %d 张图片: %s",
        Path(options.test_image).name,
        len(test_images),
        image_names,
    )
    result, _, _, _ = extract(
        [str(image) for image in test_images],
        settings,
        default_topic=options.default_topic,
        include_raw=True,
        prompt_fn=build_prompt,
        schema_fn=build_extraction_schema,
    )
    raw_response = result.pop("_raw_response", "")
    logger.info("📄 模型原始响应如下：\n%s", raw_response)
    serialized = serialize_subject(
        result.get("questions", []),
        None,
        options.subject_id,
        options.subject_name,
    )
    dump(serialized, None)


def run_directory_mode(
    options: CliOptions,
    settings: RuntimeSettings,
) -> None:
    assert options.input_dir is not None
    settings = settings.model_copy(update={"consensus": bool(options.consensus)})
    # 构建输出路径以加载已有文件
    output_path = None
    if options.artifact_dir and options.artifact_name:
        from pathlib import Path

        output_path = str(Path(options.artifact_dir) / options.artifact_name / f"{options.artifact_name}.json")
    existing_qs, existing_index = load_existing(output_path)
    if existing_qs:
        logger.info("↩️  续跑模式：已有 %d 道题目，将追加新题", len(existing_qs))
    if options.verify_existing:
        all_questions, stats = verify_existing_directory(
            options.input_dir,
            settings,
            options.default_topic,
            default_chapter=options.default_chapter,
            default_section=options.default_section,
            step=options.step,
            context=options.context,
            context_before=options.context_before,
            context_after=options.context_after,
            start_from=options.start_from,
            end_at=options.end_at,
            existing_qs=existing_qs,
            existing_index=existing_index,
            artifact_dir=options.artifact_dir,
            artifact_name=options.artifact_name,
            subject_id=options.subject_id,
            subject_name=options.subject_name,
            serialize_subject=serialize_subject,
            stop_requested_fn=lambda: eq_common.STOP_REQUESTED,
            prompt_fn=build_prompt,
            schema_fn=build_extraction_schema,
        )
        logger.info(
            "🔎 校验完成：总计 %d 道 | 提取 %d | 匹配 %d | 新增 %d | 更新 %d | 修正 %d | 保留 %d | 不完整 %d",
            len(all_questions),
            stats["extracted"],
            stats["matched"],
            stats["added"],
            stats["updated"],
            stats["corrected"],
            stats["kept"],
            stats["incomplete"],
        )
        return
    all_questions, conflicts, all_chapters = process_directory(
        options.input_dir,
        settings,
        options.default_topic,
        default_chapter=options.default_chapter,
        default_section=options.default_section,
        step=options.step,
        context=options.context,
        context_before=options.context_before,
        context_after=options.context_after,
        start_from=options.start_from,
        end_at=options.end_at,
        existing_qs=existing_qs,
        existing_index=existing_index,
        artifact_dir=options.artifact_dir,
        artifact_name=options.artifact_name,
        subject_id=options.subject_id,
        subject_name=options.subject_name,
        serialize_subject=serialize_subject,
        stop_requested_fn=lambda: eq_common.STOP_REQUESTED,
        prompt_fn=build_prompt,
        schema_fn=build_extraction_schema,
    )
    new_count = max(0, len(all_questions) - len(existing_qs))
    logger.info("📊 共 %d 道题目（原有 %d，新增 %d）", len(all_questions), len(existing_qs), new_count)
    logger.info("🧭 冲突题 %d 道", len(conflicts))
    logger.info("📚 章节：%s", "、".join(all_chapters))


def run_image_mode(options: CliOptions, settings: RuntimeSettings) -> None:
    ensure_files_exist(options.images)
    logger.info("📸 处理 %d 张图片", len(options.images))
    result, _, _, _ = extract(
        options.images,
        settings,
        default_topic=options.default_topic,
        prompt_fn=build_prompt,
        schema_fn=build_extraction_schema,
    )
    serialized = serialize_subject(
        result.get("questions", []),
        None,
        options.subject_id,
        options.subject_name,
    )
    dump(serialized, None)


@app.command()
def main(
    images: Annotated[list[str] | None, typer.Argument(help="直接处理的一张或多张图片")] = None,
    test_image: Annotated[str | None, typer.Option("--test", help="测试模式：指定一张图片")] = None,
    input_dir: Annotated[str | None, typer.Option("--dir", help="目录模式：处理整个图片目录")] = None,
    default_topic: Annotated[
        str | None, typer.Option("--default-topic", help="默认专题名称（从中间继续解析时使用）")
    ] = None,
    step: Annotated[int | None, typer.Option(help="目录模式：每批主处理页数")] = None,
    context: Annotated[int | None, typer.Option(help="目录模式：前后各附带几页上下文")] = None,
    context_before: Annotated[int | None, typer.Option("--context-before", help="目录模式：前附带几页上下文")] = None,
    context_after: Annotated[int | None, typer.Option("--context-after", help="目录模式：后附带几页上下文")] = None,
    start_from: Annotated[
        int | None, typer.Option("--start-from", help="从文件名数字序号大于等于该值的图片开始")
    ] = None,
    end_at: Annotated[int | None, typer.Option("--end-at", help="处理到文件名数字序号小于等于该值的图片结束")] = None,
    artifact_dir: Annotated[str | None, typer.Option("--artifact-dir", help="产物根目录")] = None,
    artifact_name: Annotated[str | None, typer.Option("--artifact-name", help="产物名称")] = None,
    env_file: Annotated[str | None, typer.Option("--env-file", help="指定 .env 文件路径")] = None,
    subject_id: Annotated[str | None, typer.Option("--subject-id", help="输出题库 ID")] = None,
    subject_name: Annotated[str | None, typer.Option("--subject-name", help="输出题库名称")] = None,
    consensus: Annotated[
        bool | None, typer.Option("--consensus/--no-consensus", help="启用共识机制（多次 API 调用确认）")
    ] = None,
    verify_existing: Annotated[
        bool, typer.Option("--verify-existing", help="校验并修复现有最终 JSON：图片提取一次，差异经 AI 裁决后写回")
    ] = False,
    default_chapter: Annotated[
        str | None, typer.Option("--default-chapter", help="默认章名称（从中间继续解析时使用）")
    ] = None,
    default_section: Annotated[
        str | None, typer.Option("--default-section", help="默认节名称（从中间继续解析时使用）")
    ] = None,
) -> None:
    signal.signal(signal.SIGINT, handle_sigint)
    raw_options = resolve_cli_options(
        {
            "images": images or [],
            "test_image": test_image,
            "input_dir": input_dir,
            "default_topic": default_topic,
            "step": step,
            "context": context,
            "context_before": context_before,
            "context_after": context_after,
            "start_from": start_from,
            "end_at": end_at,
            "artifact_dir": artifact_dir,
            "artifact_name": artifact_name,
            "env_file": env_file,
            "subject_id": subject_id,
            "subject_name": subject_name,
            "consensus": consensus,
            "verify_existing": verify_existing,
            "default_chapter": default_chapter,
            "default_section": default_section,
        }
    )
    runtime_settings, env_loaded_path = load_runtime_settings(raw_options.env_file)
    options = merge_cli_with_settings(raw_options, runtime_settings)
    setup_logging(None)
    log_env_source(options.env_file, env_loaded_path)
    if options.test_image:
        run_test_mode(options, runtime_settings)
        return
    if options.input_dir:
        run_directory_mode(options, runtime_settings)
        return
    run_image_mode(options, runtime_settings)


def run() -> None:
    try:
        app()
    except ValidationError as e:
        logger.error("参数或配置校验失败：%s", e)
        sys.exit(1)
    except typer.BadParameter as e:
        logger.error("参数错误：%s", e)
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("程序已按用户请求停止")
        sys.exit(0)
    except RetryLimitExceededError as e:
        logger.error("处理失败：%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("处理失败：%s", e)
        sys.exit(1)
