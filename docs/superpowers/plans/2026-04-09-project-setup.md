# Project Setup & Core Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up the Python project structure, CLI framework, configuration management, and data directory foundation.

**Architecture:** Use Hermes Agent as the base, extending with observer subsystems. Project structure follows Python packaging best practices with a CLI entry point.

**Tech Stack:** Python 3.11+, Click/Argparse, SQLite, JSON for config

---

## File Structure

```
hermes-mac/
├── pyproject.toml           # Project metadata and dependencies
├── src/
│   └── hermes_mac/
│       ├── __init__.py
│       ├── cli.py           # CLI entry point
│       ├── config.py        # Configuration management
│       ├── __main__.py
│       └── constants.py     # Constants
├── data/                    # Data directory (created at runtime)
└── tests/
    └── test_config.py
```

### Task 1: Initialize Python project with pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `src/hermes_mac/__init__.py`
- Create: `src/hermes_mac/__main__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "hermes-mac"
version = "0.1.0"
description = "PC Personal Assistant with autonomous observation"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",
    "rich>=13.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "pyyaml>=6.0.0",
    "pydantic>=2.0.0",
]

[project.scripts]
hermes-mac = "hermes_mac.cli:main"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Create __init__.py**

```python
"""Hermes-mac: PC Personal Assistant with autonomous observation."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create __main__.py**

```python
"""Allow running as: python -m hermes_mac"""

from hermes_mac.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/hermes_mac/__init__.py src/hermes_mac/__main__.py
git commit -m "feat: initialize project structure with pyproject.toml"
```

### Task 2: Create constants and configuration module

**Files:**
- Create: `src/hermes_mac/constants.py`
- Create: `src/hermes_mac/config.py`

- [ ] **Step 1: Create constants.py**

```python
"""Constants for hermes-mac."""

from pathlib import Path

# Default data directory
DEFAULT_DATA_DIR = Path.home() / ".hermes-mac" / "data"

# Config file name
CONFIG_FILE_NAME = "config.json"

# Database file name
DB_FILE_NAME = "hermes.db"

# Observers configuration
DEFAULT_OBSERVER_INTERVAL = 5  # seconds

# LLM defaults
DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_LLM_MODEL = "llama3"

# Observer capability types
class Capability:
    WINDOW_FOCUS = "window_focus"
    FILE_CONTENT = "file_content"
    CURSOR_POSITION = "cursor_position"
    CODE_DIFF = "code_diff"
    DOM_CONTENT = "dom_content"
    USER_ACTION = "user_action"
    MESSAGE = "message"
    MEETING = "meeting"
    COMMAND = "command"
```

- [ ] **Step 2: Create config.py**

```python
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
        with open(config_path) as f:
            data = json.load(f)
            return AppConfig(**data)
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to file."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2, default=str)


def ensure_data_dir(config: AppConfig) -> Path:
    """Ensure data directory exists."""
    data_dir = config.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
```

- [ ] **Step 3: Run test to verify imports work**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && python -c "from hermes_mac.config import load_config; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/hermes_mac/constants.py src/hermes_mac/config.py
git commit -m "feat: add configuration management module"
```

### Task 3: Create CLI entry point

**Files:**
- Create: `src/hermes_mac/cli.py`

- [ ] **Step 1: Create cli.py**

```python
"""CLI entry point for hermes-mac."""

import click
from rich.console import Console
from rich.table import Table

from hermes_mac.config import load_config, save_config, AppConfig
from hermes_mac.constants import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Hermes-mac: PC Personal Assistant with autonomous observation."""
    pass


@main.command()
def status():
    """Show current status."""
    config = load_config()
    table = Table(title="Hermes-mac Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Data Directory", str(config.data_dir))
    table.add_row("LLM Provider", config.llm.provider)
    table.add_row("LLM Model", config.llm.model)
    table.add_row("Observers Enabled", str(len([o for o in config.observers.observers if config.observers.enabled])))
    
    console.print(table)


@main.command()
@click.option("--provider", default=DEFAULT_LLM_PROVIDER, help="LLM provider (ollama, openai, openrouter)")
@click.option("--model", default=DEFAULT_LLM_MODEL, help="LLM model name")
@click.option("--endpoint", default=None, help="API endpoint URL")
@click.option("--api-key", default=None, help="API key")
def config_llm(provider, model, endpoint, api_key):
    """Configure LLM settings."""
    config = load_config()
    config.llm.provider = provider
    config.llm.model = model
    if endpoint:
        config.llm.endpoint = endpoint
    if api_key:
        config.llm.api_key = api_key
    save_config(config)
    console.print(f"[green]LLM configured: {provider}/{model}[/green]")


@main.command()
def init():
    """Initialize hermes-mac data directory."""
    from hermes_mac.config import ensure_data_dir
    config = load_config()
    data_dir = ensure_data_dir(config)
    console.print(f"[green]Initialized data directory: {data_dir}[/green]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Install package in development mode**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && pip install -e .
```

- [ ] **Step 3: Test CLI**

```bash
hermes-mac --help
hermes-mac status
```

Expected: Help output and status command work

- [ ] **Step 4: Commit**

```bash
git add src/hermes_mac/cli.py
git commit -m "feat: add CLI entry point"
```

### Task 4: Add test for configuration module

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Create test_config.py**

```python
"""Tests for configuration module."""

import pytest
import tempfile
import os
from pathlib import Path

from hermes_mac.config import AppConfig, load_config, save_config


def test_default_config():
    """Test default configuration values."""
    config = AppConfig()
    assert config.llm.provider == "ollama"
    assert config.llm.model == "llama3"
    assert config.observers.enabled is True


def test_save_and_load_config(tmp_path, monkeypatch):
    """Test saving and loading configuration."""
    # Mock the config path
    test_config_path = tmp_path / "config.json"
    monkeypatch.setattr("hermes_mac.config.get_config_path", lambda: test_config_path)
    
    config = AppConfig()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4"
    
    save_config(config)
    loaded = load_config()
    
    assert loaded.llm.provider == "openai"
    assert loaded.llm.model == "gpt-4"
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/yangnanqing/projects/pc个人助手 && python -m pytest tests/test_config.py -v
```

Expected: Tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add configuration module tests"
```

---

## Summary

This plan sets up:
- Python project with pyproject.toml
- Configuration management (LLM, observers, gateways)
- CLI entry point with basic commands (status, config-llm, init)
- Tests for configuration module

**Next plan should cover:** Observer framework and SystemObserver implementation.