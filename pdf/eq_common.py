import logging
import re
import time
from pathlib import Path

from natsort import natsorted

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

logger = logging.getLogger("extract")
STOP_REQUESTED = False
LAST_API_CALL_TIME: float | None = None


def handle_sigint(signum, frame):
    del signum, frame
    global STOP_REQUESTED
    if STOP_REQUESTED:
        raise KeyboardInterrupt
    STOP_REQUESTED = True
    logger.warning("🛑 收到 Ctrl+C，当前步骤结束后停止程序（再按一次立即退出）")


def sleep_with_interrupt(seconds: float) -> bool:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        if STOP_REQUESTED:
            return False
        time.sleep(min(0.2, deadline - time.time()))
    return not STOP_REQUESTED


def wait_for_api_interval(interval_seconds: float) -> None:
    """等待API调用间隔时间"""
    global LAST_API_CALL_TIME
    if LAST_API_CALL_TIME is not None:
        elapsed = time.time() - LAST_API_CALL_TIME
        if elapsed < interval_seconds:
            wait_time = interval_seconds - elapsed
            logger.info("⏳ API调用间隔等待 %.1f 秒", wait_time)
            if not sleep_with_interrupt(wait_time):
                raise KeyboardInterrupt
    LAST_API_CALL_TIME = time.time()


def ensure_not_stopped() -> None:
    if STOP_REQUESTED:
        raise KeyboardInterrupt


def image_sequence(path: Path) -> int | None:
    matches = re.findall(r"(\d+)", path.stem)
    if not matches:
        return None
    return int(matches[-1])


def sort_images(images: list[Path]) -> list[Path]:
    return list(natsorted(images, key=lambda f: f.name))
