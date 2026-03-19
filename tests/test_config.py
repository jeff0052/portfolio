# tests/test_config.py
import os
import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OWNER_USER_ID", "12345")

    # Reload module to pick up new env
    import importlib
    import config
    importlib.reload(config)

    assert config.TELEGRAM_BOT_TOKEN == "test-token"
    assert config.ANTHROPIC_API_KEY == "test-key"
    assert config.OWNER_USER_ID == 12345


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("OWNER_USER_ID", "1")

    import importlib
    import config
    importlib.reload(config)

    assert config.COMPRESSION_TOKEN_THRESHOLD == 100000
    assert config.DOCKER_TIMEOUT == 30
    assert config.CONTAINER_IDLE_TIMEOUT == 300
