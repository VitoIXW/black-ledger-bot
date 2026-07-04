from __future__ import annotations

import pytest

from app.bot.auth import authorization_message, is_authorized
from app.main import AppConfig


def test_is_authorized_requires_matching_user_id() -> None:
    assert is_authorized(123, frozenset({123})) is True
    assert is_authorized(999, frozenset({123})) is False
    assert is_authorized(None, frozenset({123})) is False


def test_authorization_message_allows_owner() -> None:
    assert authorization_message(123, frozenset({123}), False) is None


def test_authorization_message_can_discover_user_id() -> None:
    message = authorization_message(123, frozenset(), True)

    assert message is not None
    assert "123" in message
    assert "ALLOWED_TELEGRAM_USER_IDS" in message


def test_authorization_message_rejects_unknown_user() -> None:
    assert authorization_message(999, frozenset({123}), False) == "No estas autorizado para usar este bot."


def test_app_config_parses_allowed_user_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "123, 456")
    monkeypatch.setenv("DISCOVER_TELEGRAM_USER_ID", "0")

    cfg = AppConfig.from_env()

    assert cfg.allowed_telegram_user_ids == frozenset({123, 456})
    assert cfg.discover_telegram_user_id is False


def test_app_config_parses_discovery_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "")
    monkeypatch.setenv("DISCOVER_TELEGRAM_USER_ID", "1")

    cfg = AppConfig.from_env()

    assert cfg.allowed_telegram_user_ids == frozenset()
    assert cfg.discover_telegram_user_id is True
