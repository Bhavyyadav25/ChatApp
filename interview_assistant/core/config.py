"""Configuration management for Interview Assistant."""

from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel, SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Config directory
CONFIG_DIR = Path.home() / ".config" / "interview-assistant"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class StealthMode(str, Enum):
    """Screen-share avoidance modes."""
    NORMAL = "normal"
    OVERLAY = "overlay"
    SECONDARY_MONITOR = "secondary_monitor"
    HOTKEY_POPUP = "hotkey_popup"


class InterviewTypeEnum(str, Enum):
    """Interview types."""
    DSA = "dsa"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"


class AIBackend(str, Enum):
    """AI backend options."""
    CLAUDE = "claude"
    OLLAMA = "ollama"


class AudioSettings(BaseModel):
    """Audio capture settings."""
    device: str = "auto"
    sample_rate: int = 16000
    buffer_size: int = 1024
    channels: int = 1


class AISettings(BaseModel):
    """AI settings."""
    backend: AIBackend = AIBackend.OLLAMA  # Default to Ollama (free)

    # Claude settings
    api_key: SecretStr = SecretStr("")
    claude_model: str = "claude-sonnet-4-5-20250929"

    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Common settings
    max_tokens: int = 4096
    temperature: float = 0.7


class TranscriptionSettings(BaseModel):
    """Whisper transcription settings."""
    model_size: str = "base"  # tiny, base, small, medium, large
    language: str = "en"
    device: str = "auto"  # auto, cpu, cuda
    compute_type: str = "auto"  # auto, int8, float16, float32


class StealthSettings(BaseModel):
    """Screen-share avoidance settings."""
    mode: StealthMode = StealthMode.NORMAL
    auto_hide_timeout: int = 5000  # ms
    opacity: float = 0.95
    always_on_top: bool = True


class UISettings(BaseModel):
    """UI appearance settings."""
    theme: str = "dark"
    font_family: str = "JetBrains Mono, Fira Code, monospace"
    font_size: int = 13
    window_width: int = 900
    window_height: int = 700


class ShortcutSettings(BaseModel):
    """Keyboard shortcut settings."""
    toggle_recording: str = "<Control><Alt>r"
    toggle_window: str = "<Control><Alt>i"
    clear_history: str = "<Control><Alt>c"
    copy_answer: str = "<Control><Shift>c"


class AppConfig(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="INTERVIEW_ASSISTANT_",
        env_nested_delimiter="__",
    )

    audio: AudioSettings = Field(default_factory=AudioSettings)
    ai: AISettings = Field(default_factory=AISettings)
    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    stealth: StealthSettings = Field(default_factory=StealthSettings)
    ui: UISettings = Field(default_factory=UISettings)
    shortcuts: ShortcutSettings = Field(default_factory=ShortcutSettings)

    # Interview settings
    default_interview_type: InterviewTypeEnum = InterviewTypeEnum.DSA

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        """Load configuration from file."""
        path = path or CONFIG_FILE

        if path.exists():
            try:
                import tomli
                with open(path, "rb") as f:
                    data = tomli.load(f)
                return cls(**data)
            except Exception:
                pass

        return cls()

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)

        import tomli_w

        # Convert to dict, handling SecretStr
        data = self.model_dump()
        if "ai" in data and "api_key" in data["ai"]:
            data["ai"]["api_key"] = self.ai.api_key.get_secret_value()

        with open(path, "wb") as f:
            tomli_w.dump(data, f)


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
