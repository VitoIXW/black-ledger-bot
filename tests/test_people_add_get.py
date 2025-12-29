from __future__ import annotations

import sqlite3

from app.db.schema import create_schema
from app.db.people_repo import PeopleRepo

import pytest


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


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def test_get_person_existing() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    got = repo.get_person(p.id)

    assert got.id == p.id
    assert got.full_name == "Juan Pérez"
    assert got.alias == "juan"
    assert got.is_deleted is False
    
def test_get_person_deleted_excluded() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")

    # Mark as deleted directly in DB for test
    conn.execute(
        "UPDATE people SET is_deleted=1, deleted_at=? WHERE id=?",
        ("2025-12-30T10:00:00+00:00", p.id),
    )

    with pytest.raises(KeyError):
        repo.get_person(p.id)


def test_get_person_missing_raises_keyerror() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    with pytest.raises(KeyError):
        repo.get_person(9999)