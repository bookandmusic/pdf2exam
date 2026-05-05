from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from eq_normalize import normalize_text

API_KEY = ""
API_URL = "https://api.openai.com/v1"
MODEL_NAME = "gpt-4o"
TEMPERATURE = 0.0
SEED = 42
ENABLE_THINKING = True
MAX_OUTPUT_TOKENS = 8192
DEFAULT_CONTEXT_PAGES = 1
DEFAULT_CONTEXT_PAGES_BEFORE = 1
DEFAULT_CONTEXT_PAGES_AFTER = 0
RESPONSE_FORMAT = "auto"
REQUEST_TIMEOUT = 180.0
DEBUG_LOG_THINKING = False


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file_encoding="utf-8")

    api_key: str = Field(default="", validation_alias="API_KEY")
    api_url: str = Field(default="https://api.openai.com/v1", validation_alias="API_URL")
    model_name: str = Field(default="gpt-4o", validation_alias="MODEL_NAME")
    temperature: float = Field(default=0.0, ge=0, le=2, validation_alias="TEMPERATURE")
    seed: int = Field(default=42, ge=0, validation_alias="SEED")
    enable_thinking: bool = Field(default=True, validation_alias="ENABLE_THINKING")
    max_output_tokens: int = Field(default=8192, ge=1, validation_alias="MAX_OUTPUT_TOKENS")
    context_pages_before: int = Field(default=1, ge=0, validation_alias="CONTEXT_PAGES_BEFORE")
    context_pages_after: int = Field(default=0, ge=0, validation_alias="CONTEXT_PAGES_AFTER")
    response_format: str = Field(default="auto", validation_alias="RESPONSE_FORMAT")
    request_timeout: float = Field(default=180.0, gt=0, validation_alias="REQUEST_TIMEOUT")
    api_call_interval: float = Field(default=3.0, ge=0, validation_alias="API_CALL_INTERVAL")
    debug_log_thinking: bool = Field(default=False, validation_alias="DEBUG_LOG_THINKING")
    test_image: str | None = Field(default=None, validation_alias="TEST_IMAGE")
    input_dir: str | None = Field(default=None, validation_alias="INPUT_DIR")
    default_topic: str | None = Field(default=None, validation_alias="DEFAULT_TOPIC")
    default_chapter: str | None = Field(default=None, validation_alias="DEFAULT_CHAPTER")
    default_section: str | None = Field(default=None, validation_alias="DEFAULT_SECTION")
    step: int | None = Field(default=None, ge=1, validation_alias="STEP")
    start_from: int | None = Field(default=None, ge=0, validation_alias="START_FROM")
    end_at: int | None = Field(default=None, ge=0, validation_alias="END_AT")
    artifact_dir: str | None = Field(default=None, validation_alias="ARTIFACT_DIR")
    artifact_name: str | None = Field(default=None, validation_alias="ARTIFACT_NAME")
    subject_id: str | None = Field(default=None, validation_alias="SUBJECT_ID")
    subject_name: str | None = Field(default=None, validation_alias="SUBJECT_NAME")
    consensus: bool = Field(default=True, validation_alias="CONSENSUS")
    image_max_size: int = Field(default=2048, ge=512, le=4096, validation_alias="IMAGE_MAX_SIZE")
    image_jpeg_quality: int = Field(default=85, ge=50, le=100, validation_alias="IMAGE_JPEG_QUALITY")

    @field_validator("response_format", mode="before")
    @classmethod
    def normalize_response_format(cls, value: Any) -> str:
        return normalize_text(value).lower() or "auto"

    @field_validator(
        "start_from",
        "end_at",
        "step",
        mode="before",
    )
    @classmethod
    def normalize_optional_ints(cls, value: Any) -> int | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "test_image",
        "input_dir",
        "default_topic",
        "default_chapter",
        "default_section",
        "artifact_dir",
        "artifact_name",
        "subject_id",
        "subject_name",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        normalized = normalize_text(value)
        return normalized or None


class CliOptions(BaseModel):
    test_image: str | None = None
    input_dir: str | None = None
    images: list[str] = Field(default_factory=list)
    default_topic: str | None = None
    default_chapter: str | None = None
    default_section: str | None = None
    step: int | None = Field(default=None, ge=1)
    context: int | None = Field(default=None, ge=0)
    context_before: int | None = Field(default=None, ge=0)
    context_after: int | None = Field(default=None, ge=0)
    start_from: int | None = Field(default=None, ge=0)
    end_at: int | None = Field(default=None, ge=0)
    artifact_dir: str | None = None
    artifact_name: str | None = None
    env_file: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    consensus: bool | None = None
    verify_existing: bool = False

    @field_validator(
        "test_image",
        "input_dir",
        "default_topic",
        "default_chapter",
        "default_section",
        "artifact_dir",
        "artifact_name",
        "env_file",
        "subject_id",
        "subject_name",
        mode="before",
    )
    @classmethod
    def normalize_cli_strings(cls, value: Any) -> str | None:
        normalized = normalize_text(value)
        return normalized or None

    def enabled_mode_count(self) -> int:
        return sum([bool(self.test_image), bool(self.input_dir), bool(self.images)])


def load_runtime_settings(env_file: str | None = None) -> tuple[RuntimeSettings, Path | None]:
    global API_KEY, API_URL, MODEL_NAME, TEMPERATURE, SEED, ENABLE_THINKING, MAX_OUTPUT_TOKENS
    global DEFAULT_CONTEXT_PAGES, DEFAULT_CONTEXT_PAGES_BEFORE, DEFAULT_CONTEXT_PAGES_AFTER
    global RESPONSE_FORMAT, REQUEST_TIMEOUT
    global DEBUG_LOG_THINKING

    env_path = Path(env_file).expanduser() if env_file else Path.cwd() / ".env"
    env_loaded_path = env_path.resolve() if env_path.exists() else None
    if env_loaded_path:
        env_vars: dict[str, str] = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            # 移除行内注释（# 后面的内容）
            if "#" in value:
                value = value.split("#", 1)[0]
            env_vars[key.strip()] = value.strip().strip("\"'")
        settings = RuntimeSettings.model_validate(env_vars)
    else:
        settings = RuntimeSettings()

    API_KEY = settings.api_key
    API_URL = settings.api_url
    MODEL_NAME = settings.model_name
    TEMPERATURE = settings.temperature
    SEED = settings.seed
    ENABLE_THINKING = settings.enable_thinking
    MAX_OUTPUT_TOKENS = settings.max_output_tokens
    DEFAULT_CONTEXT_PAGES = 1  # 保持向后兼容
    DEFAULT_CONTEXT_PAGES_BEFORE = settings.context_pages_before
    DEFAULT_CONTEXT_PAGES_AFTER = settings.context_pages_after
    RESPONSE_FORMAT = settings.response_format
    REQUEST_TIMEOUT = settings.request_timeout
    DEBUG_LOG_THINKING = settings.debug_log_thinking
    return settings, env_loaded_path


def validate_runtime_mode(options: CliOptions) -> CliOptions:
    enabled_modes = options.enabled_mode_count()
    if enabled_modes != 1:
        raise ValueError("必须且只能选择一种模式：`--test`、`--dir` 或直接传入图片路径")
    return options
