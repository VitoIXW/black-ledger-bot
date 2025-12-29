from __future__ import annotations

import sqlite3

from app.db.schema import create_schema
from app.db.people_repo import PeopleRepo


def test_add_person() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)

    repo = PeopleRepo(conn)

    p = repo.add_person(
        full_name="Juan Pérez",
        alias="juan",
        created_at="2025-12-29T10:00:00+00:00",
    )

    assert p.id > 0
    assert p.full_name == "Juan Pérez"
    assert p.alias == "juan"
    assert p.is_deleted is False
    assert p.deleted_at is None