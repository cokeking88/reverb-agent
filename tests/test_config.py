"""Tests for configuration module."""

import pytest
import tempfile
import os
from pathlib import Path

from reverb_agent.config import AppConfig, load_config, save_config


def test_default_config():
    """Test default configuration values."""
    config = AppConfig()
    assert config.llm.provider == "ollama"
    assert config.llm.model == "llama3"
    assert config.observers.enabled is True


def test_save_and_load_config(tmp_path, monkeypatch):
    """Test saving and loading configuration."""
    test_config_path = tmp_path / "config.json"
    monkeypatch.setattr("reverb_agent.config.get_config_path", lambda: test_config_path)
    
    config = AppConfig()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4"
    
    save_config(config)
    loaded = load_config()
    
    assert loaded.llm.provider == "openai"
    assert loaded.llm.model == "gpt-4"