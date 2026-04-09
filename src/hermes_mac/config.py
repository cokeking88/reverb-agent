"""Configuration management for hermes-mac."""

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from hermes_mac.constants import DEFAULT_DATA_DIR, DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL


class LLMConfig(BaseModel):
    provider: str = DEFAULT_LLM_PROVIDER
    model: str = DEFAULT_LLM_MODEL
    endpoint: Optional[str] = None
    api_key: Optional[str] = None


class ObserverConfig(BaseModel):
    enabled: bool = True
    interval: int = 5
    observers: list[str] = []  # List of observer names to enable


class GatewayConfig(BaseModel):
    name: str
    enabled: bool = False
    config: dict = {}


class AppConfig(BaseModel):
    data_dir: Path = DEFAULT_DATA_DIR
    llm: LLMConfig = LLMConfig()
    observers: ObserverConfig = ObserverConfig()
    gateways: dict[str, GatewayConfig] = {}


def get_config_dir() -> Path:
    """Get the config directory path."""
    return Path.home() / ".hermes-mac"


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


def load_config() -> AppConfig:
    """Load configuration from file."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
                return AppConfig(**data)
        except (json.JSONDecodeError, IOError):
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to file."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = get_config_path()
    try:
        with open(config_path, "w") as f:
            json.dump(config.model_dump(), f, indent=2, default=str)
    except IOError:
        pass


def ensure_data_dir(config: AppConfig) -> Path:
    """Ensure data directory exists."""
    data_dir = config.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir