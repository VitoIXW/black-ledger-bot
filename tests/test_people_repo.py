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


def test_list_person_empty() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    people = repo.list_person()
    assert people == []


def test_list_person_returns_all_non_deleted() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p1 = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    p2 = repo.add_person("María López", "maria", "2025-12-29T10:01:00+00:00")

    people = repo.list_person()

    assert len(people) == 2
    assert people[0].id == p1.id
    assert people[1].id == p2.id


def test_list_person_excludes_soft_deleted() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p1 = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    p2 = repo.add_person("María López", "maria", "2025-12-29T10:01:00+00:00")

    repo.delete_soft_person(p1.id, "2025-12-29T11:00:00+00:00")

    # repo.conn.execute("UPDATE people SET is_deleted=1, deleted_at=? WHERE id=?", ("2025-12-29T11:00:00+00:00", p1.id))

    people = repo.list_person()

    assert len(people) == 1
    assert people[0].id == p2.id
