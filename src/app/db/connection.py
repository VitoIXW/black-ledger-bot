from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class DbConfig:
    path: str


def connect(cfg: DbConfig) -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def session(cfg: DbConfig) -> Iterator[sqlite3.Connection]:
    conn = connect(cfg)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()