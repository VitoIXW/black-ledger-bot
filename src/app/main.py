from __future__ import annotations

import os
from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    tz: str
    telegram_bot_token: str
    allowed_telegram_user_ids: FrozenSet[int]
    discover_telegram_user_id: bool

    @staticmethod
    def from_env() -> "AppConfig":
        db_path = os.environ.get("DB_PATH", "/data/black_ledger.db")
        tz = os.environ.get("TZ", "Europe/Madrid")
        telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        allowed_ids = _parse_int_set(os.environ.get("ALLOWED_TELEGRAM_USER_IDS", ""))
        discover_user_id = os.environ.get("DISCOVER_TELEGRAM_USER_ID", "0") == "1"
        return AppConfig(
            db_path=db_path,
            tz=tz,
            telegram_bot_token=telegram_bot_token,
            allowed_telegram_user_ids=allowed_ids,
            discover_telegram_user_id=discover_user_id,
        )


def main() -> None:
    cfg = AppConfig.from_env()
    if not cfg.telegram_bot_token or cfg.telegram_bot_token == "put_your_token_here":
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot.")
    if not cfg.allowed_telegram_user_ids and not cfg.discover_telegram_user_id:
        raise RuntimeError(
            "ALLOWED_TELEGRAM_USER_IDS is required. "
            "Set DISCOVER_TELEGRAM_USER_ID=1 temporarily if you need Luigi to tell you your user id."
        )

    from app.bot.telegram_app import build_application, init_database

    init_database(cfg.db_path)
    print("Black Ledger Bot running with Telegram polling.")
    print(f"DB_PATH={cfg.db_path}")
    print(f"TZ={cfg.tz}")
    build_application(
        cfg.telegram_bot_token,
        cfg.db_path,
        allowed_user_ids=cfg.allowed_telegram_user_ids,
        discover_user_id=cfg.discover_telegram_user_id,
    ).run_polling()


def _parse_int_set(raw: str) -> FrozenSet[int]:
    ids = []
    for part in raw.split(","):
        value = part.strip()
        if value:
            ids.append(int(value))
    return frozenset(ids)


if __name__ == "__main__":
    main()
