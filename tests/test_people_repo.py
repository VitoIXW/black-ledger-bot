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

def test_search_person_empty_query_returns_empty() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)
    repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")

    assert repo.search_person("") == []
    assert repo.search_person("   ") == []


def test_search_person_matches_alias_and_name() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)
    repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    repo.add_person("María López", "maria", "2025-12-29T10:01:00+00:00")

    by_alias = repo.search_person("juan")
    assert len(by_alias) == 1
    assert by_alias[0].full_name == "Juan Pérez"

    by_name = repo.search_person("María")
    assert len(by_name) == 1
    assert by_name[0].alias == "maria"


def test_search_person_excludes_soft_deleted() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)
    p1 = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    repo.add_person("María López", "maria", "2025-12-29T10:01:00+00:00")

    repo.delete_soft_person(p1.id, "2025-12-29T11:00:00+00:00")

    results = repo.search_person("juan")
    assert results == []


def test_search_person_multiple_matches() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)
    repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    repo.add_person("Juan López", "juanlo", "2025-12-29T10:01:00+00:00")
    repo.add_person("María López", "maria", "2025-12-29T10:02:00+00:00")

    results = repo.search_person("Juan")
    assert len(results) == 2
    assert any(person.full_name == "Juan Pérez" for person in results)
    assert any(person.full_name == "Juan López" for person in results)

def test_search_person_only_alias_match() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)
    repo.add_person("Carlos Sánchez", "carlitos", "2025-12-29T10:00:00+00:00")
    repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    repo.add_person("Juan López", "juanlo", "2025-12-29T10:01:00+00:00")
    repo.add_person("María López", "maria", "2025-12-29T10:02:00+00:00")

    results = repo.search_person("carlitos")
    assert len(results) == 1
    assert results[0].full_name == "Carlos Sánchez"

    results = repo.search_person("juanl")
    assert len(results) == 1
    assert results[0].full_name == "Juan López"

    results = repo.search_person("López")
    assert len(results) == 2

    result_names = {person.full_name for person in results}
    expected_names = {"María López", "Juan López"}
    assert result_names == expected_names



def test_update_person_updates_only_alias() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    assert p.alias == "juan"

    updated = repo.update_person(p.id, alias="juanito")
    assert updated.full_name == "Juan Pérez"
    assert updated.alias == "juanito"


def test_update_person_updates_only_full_name() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    assert p.full_name == "Juan Pérez"

    updated = repo.update_person(p.id, full_name="Juan P. Pérez")
    assert updated.full_name == "Juan P. Pérez"
    assert updated.alias == "juan"


def test_update_person_missing_raises_keyerror() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    with pytest.raises(KeyError):
        repo.update_person(9999, alias="x")


def test_update_person_deleted_raises_keyerror() -> None:
    conn = make_conn()
    repo = PeopleRepo(conn)

    p = repo.add_person("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00")
    deleted = repo.delete_soft_person(p.id, "2025-12-29T11:00:00+00:00")
    assert deleted.is_deleted is True

    with pytest.raises(KeyError):
        repo.update_person(p.id, alias="juanito")