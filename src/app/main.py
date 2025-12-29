from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    tz: str

    @staticmethod
    def from_env() -> "AppConfig":
        db_path = os.environ.get("DB_PATH", "/data/black_ledger.db")
        tz = os.environ.get("TZ", "Europe/Madrid")
        return AppConfig(db_path=db_path, tz=tz)


def main() -> None:
    cfg = AppConfig.from_env()
    print("Black Ledger Bot running.")
    print(f"DB_PATH={cfg.db_path}")
    print(f"TZ={cfg.tz}")


if __name__ == "__main__":
    main()
