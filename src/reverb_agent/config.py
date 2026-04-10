"""Configuration management for Reverb Agent."""

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from reverb_agent.constants import DEFAULT_DATA_DIR, DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL


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
    return Path.home() / ".reverb-agent"


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


def load_env() -> dict:
    """Load configuration from .env file."""
    # Check root and config dir
    possible_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]
    env_vars = {}
    for env_path in possible_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()
            break
    return env_vars


def load_config() -> AppConfig:
    """Load configuration from file."""
    # First try .env
    env_vars = load_env()
    
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
                # Override with env vars if present
                if "REVERB_LLM_PROVIDER" in env_vars:
                    data.setdefault("llm", {})["provider"] = env_vars["REVERB_LLM_PROVIDER"]
                if "REVERB_LLM_MODEL" in env_vars:
                    data.setdefault("llm", {})["model"] = env_vars["REVERB_LLM_MODEL"]
                if "REVERB_LLM_ENDPOINT" in env_vars:
                    data.setdefault("llm", {})["endpoint"] = env_vars["REVERB_LLM_ENDPOINT"]
                if "REVERB_LLM_API_KEY" in env_vars:
                    data.setdefault("llm", {})["api_key"] = env_vars["REVERB_LLM_API_KEY"]
                return AppConfig(**data)
        except (json.JSONDecodeError, IOError):
            pass
    
    # No config file, create from env
    if env_vars:
        llm_config = LLMConfig(
            provider=env_vars.get("REVERB_LLM_PROVIDER", "ollama"),
            model=env_vars.get("REVERB_LLM_MODEL", "llama3"),
            endpoint=env_vars.get("REVERB_LLM_ENDPOINT"),
            api_key=env_vars.get("REVERB_LLM_API_KEY")
        )
        return AppConfig(llm=llm_config)
    
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