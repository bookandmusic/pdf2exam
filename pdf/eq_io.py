import base64
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from eq_common import SUPPORTED_EXTENSIONS, logger, sort_images
from eq_models import ExtractionValidationError, normalize_question_payload
from eq_normalize import question_key


class ArtifactPaths:
    """产物目录结构管理"""

    def __init__(self, artifact_dir: str, artifact_name: str):
        self.root = Path(artifact_dir) / artifact_name
        self.run_log = self.root / "run.log"
        self.final_output = self.root / f"{artifact_name}.json"

    def create_dirs(self) -> None:
        """创建根目录"""
        self.root.mkdir(parents=True, exist_ok=True)

    def batch_dir(self, batch_no: int, image_paths: list[str]) -> Path:
        """生成批次文件夹路径：batch{N}_{首图}-{末图}"""
        first_name = Path(image_paths[0]).stem
        last_name = Path(image_paths[-1]).stem
        if first_name == last_name:
            folder_name = f"batch{batch_no}_{first_name}"
        else:
            folder_name = f"batch{batch_no}_{first_name}-{last_name}"
        return self.root / folder_name

    def response_file(self, batch_no: int, image_paths: list[str], attempt: int) -> Path:
        """生成响应文件路径：batch{N}_{首图}-{末图}/{attempt}.json"""
        batch_folder = self.batch_dir(batch_no, image_paths)
        return batch_folder / f"{attempt}.json"

    def consensus_diff_file(self, batch_no: int, image_paths: list[str], attempt1: int, attempt2: int) -> Path:
        """生成diff文件路径：batch{N}_{首图}-{末图}/{attempt1}-{attempt2}-diff.txt"""
        batch_folder = self.batch_dir(batch_no, image_paths)
        return batch_folder / f"{attempt1}-{attempt2}-diff.txt"

    def consensus_llm_file(self, batch_no: int, image_paths: list[str], attempt1: int, attempt2: int) -> Path:
        """生成LLM决策文件路径：batch{N}_{首图}-{末图}/{attempt1}-{attempt2}-llm.json"""
        batch_folder = self.batch_dir(batch_no, image_paths)
        return batch_folder / f"{attempt1}-{attempt2}-llm.json"

    def overlapping_diff_file(self, batch_no: int, image_paths: list[str]) -> Path:
        """生成批次间重复页面差异汇总文件路径：batch{N}_{首图}-{末图}/overlapping_diff.txt"""
        batch_folder = self.batch_dir(batch_no, image_paths)
        return batch_folder / "overlapping_diff.txt"

    def overlapping_llm_file(self, batch_no: int, image_paths: list[str]) -> Path:
        """生成批次间重复页面LLM决策汇总文件路径：batch{N}_{首图}-{末图}/overlapping_llm.json"""
        batch_folder = self.batch_dir(batch_no, image_paths)
        return batch_folder / "overlapping_llm.json"


def append_run_log(log_file: Path, message: str, level: str = "INFO") -> None:
    """追加简要运行日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"{timestamp} [{level}] {message}\n")


def save_consensus_diff(
    artifact_paths: "ArtifactPaths",
    batch_no: int,
    image_paths: list[str],
    attempt1: int,
    attempt2: int,
    diff_text: str,
) -> None:
    """保存共识对比的 diff 文本"""
    out_path = artifact_paths.consensus_diff_file(batch_no, image_paths, attempt1, attempt2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(diff_text, encoding="utf-8")


def save_consensus_llm(
    artifact_paths: "ArtifactPaths",
    batch_no: int,
    image_paths: list[str],
    attempt1: int,
    attempt2: int,
    llm_result: dict[str, Any],
) -> None:
    """追加保存批次内共识的 LLM 判断结果"""
    out_path = artifact_paths.consensus_llm_file(batch_no, image_paths, attempt1, attempt2)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        existing_data = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(existing_data, dict) and isinstance(existing_data.get("decisions"), list):
            data = existing_data
        else:
            data = {"decisions": [existing_data]}
    else:
        data = {"decisions": []}

    data["decisions"].append(llm_result)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_overlapping_diff(
    artifact_paths: "ArtifactPaths",
    batch_no: int,
    image_paths: list[str],
    question_number: str,
    diff_text: str,
) -> None:
    """追加保存批次间重复页面的 diff 文本"""
    out_path = artifact_paths.overlapping_diff_file(batch_no, image_paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 追加模式写入，添加题目标题
    with out_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 80}\n")
        f.write(f"题目 {question_number}\n")
        f.write(f"{'=' * 80}\n")
        f.write(diff_text)
        f.write("\n")


def save_overlapping_llm(
    artifact_paths: "ArtifactPaths",
    batch_no: int,
    image_paths: list[str],
    question_number: str,
    llm_result: dict[str, Any],
) -> None:
    """追加保存批次间重复页面的 LLM 判断结果"""
    out_path = artifact_paths.overlapping_llm_file(batch_no, image_paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有数据
    if out_path.exists():
        existing_data = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        existing_data = {"decisions": []}

    # 追加新决策
    existing_data["decisions"].append(llm_result)

    # 保存回文件
    out_path.write_text(json.dumps(existing_data, ensure_ascii=False, indent=2), encoding="utf-8")


def setup_logging(log_path: str | None = None) -> None:
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.flush = lambda: sys.stderr.flush()  # 强制立即刷新
    handlers: list[logging.Handler] = [stream_handler]
    if log_path:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    for lib in ("httpx", "httpcore", "openai._base_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def image_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".png": "png",
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".bmp": "bmp",
        ".tiff": "tiff",
        ".tif": "tiff",
        ".webp": "webp",
    }.get(ext, "png")


def encode_image(path: str, max_size: int = 2048, jpeg_quality: int = 85) -> str:
    """编码图片为 base64，自动缩放并压缩图片以减少 token 消耗

    Args:
        path: 图片路径
        max_size: 最大边长限制（默认 2048，可通过 IMAGE_MAX_SIZE 环境变量配置）
        jpeg_quality: JPEG 压缩质量 0-100（默认 85，可通过 IMAGE_JPEG_QUALITY 环境变量配置）
    """
    import io

    from PIL import Image

    with Image.open(path) as img:
        original_size = (img.width, img.height)
        needs_resize = img.width > max_size or img.height > max_size

        # 转换为 RGB（JPEG 不支持透明通道）
        if img.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = rgb_img
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 缩放图片
        if needs_resize:
            ratio = min(max_size / img.width, max_size / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(
                "📐 图片已缩放: %s (%dx%d → %dx%d)",
                Path(path).name,
                original_size[0],
                original_size[1],
                new_size[0],
                new_size[1],
            )

        # 压缩为 JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
        compressed_size = buffer.tell()

        # 估算压缩率
        if needs_resize or Path(path).suffix.lower() in (".png", ".bmp", ".tiff"):
            original_file_size = Path(path).stat().st_size
            ratio_percent = (compressed_size / original_file_size) * 100
            logger.info(
                "🗜️  图片已压缩: %s (%.1f KB → %.1f KB, %.1f%%)",
                Path(path).name,
                original_file_size / 1024,
                compressed_size / 1024,
                ratio_percent,
            )

        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def save_raw_response(
    raw: str,
    image_paths: list[str],
    batch_no: int | None = None,
    attempt: int = 1,
    artifact_paths: "ArtifactPaths | None" = None,
) -> None:
    """保存原始响应到 artifact_paths"""
    if artifact_paths and batch_no is not None:
        out_path = artifact_paths.response_file(batch_no, image_paths, attempt)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(raw, encoding="utf-8")
        logger.info("📝 已保存响应: %s", out_path.relative_to(artifact_paths.root))


def resolve_test_images(image_path: str, context_before: int = 1, context_after: int = 0) -> list[Path]:
    target = Path(image_path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"文件不存在: {image_path}")
    siblings = [f for f in target.parent.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    images = sort_images(siblings)
    try:
        index = images.index(target)
    except ValueError:
        return [target]
    left = max(0, index - max(0, context_before))
    right = min(len(images), index + max(0, context_after) + 1)
    return images[left:right]


def collect_images(dir_path: str) -> list[Path]:
    p = Path(dir_path)
    if not p.is_dir():
        raise FileNotFoundError(f"目录不存在: {dir_path}")
    images = sort_images([f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS])
    if not images:
        raise FileNotFoundError(f"目录中无支持的图片: {dir_path}")
    return images


def build_question_index(questions: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for q in questions:
        if not isinstance(q, dict):
            continue
        key = question_key(q)
        if not key[3]:
            continue
        index.setdefault(key, q)
    return index


def load_existing(
    output_path: str | None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    if not output_path:
        return [], {}
    p = Path(output_path)
    if not p.exists():
        logger.info("输出文件不存在，将从零开始")
        return [], {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        qs = data.get("questions", []) if isinstance(data, dict) else []
        normalized_qs = []
        for idx, q in enumerate(qs, start=1):
            if not isinstance(q, dict):
                continue
            normalized = normalize_question_payload(q, f"已有题目 #{idx}")
            normalized["id"] = q.get("id")
            normalized_qs.append(normalized)
        index = build_question_index(normalized_qs)
        logger.info("读取已有文件: %s（%d 道题目）", output_path, len(normalized_qs))
        return normalized_qs, index
    except (json.JSONDecodeError, KeyError, ExtractionValidationError) as e:
        logger.warning("读取已有文件失败，将从零开始: %s", e)
        return [], {}


def dump(data: dict[str, Any], output_path: str | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        logger.info("💾 已写入: %s", output_path)
    else:
        print(text)


def resolve_sidecar_json_path(
    output_path: str | None,
    explicit_path: str | None,
    suffix: str,
) -> str | None:
    if explicit_path:
        return explicit_path
    if output_path:
        output = Path(output_path)
        return str(output.with_name(f"{output.stem}.{suffix}.json"))
    return None


def ensure_files_exist(paths: list[str]) -> None:
    for path in paths:
        if not Path(path).exists():
            raise FileNotFoundError(f"文件不存在: {path}")
