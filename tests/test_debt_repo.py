from __future__ import annotations

import sqlite3
import pytest

from app.db.schema import create_schema
from app.db.people_repo import PeopleRepo
from app.db.debt_repo import DebtRepo


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def test_add_debt_success() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1500,
        description="kebab",
    )

    assert d.id > 0
    assert d.person_id == p.id
    assert d.original_amount_eur == 1500
    assert d.description == "kebab"
    assert d.status == "OPEN"
    assert d.effective_at is None


def test_add_debt_rejects_non_positive_amount() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    with pytest.raises(ValueError):
        debts.add_debt(
            person_id=p.id,
            amount_eur_cents=0,
            description="invalid",
        )


def test_add_debt_person_not_found_or_deleted() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")

    # no existe
    with pytest.raises(KeyError):
        debts.add_debt(
            person_id=999,
            amount_eur_cents=1000,
            description="test",
        )

    # existe pero borrada
    p = people.add_person("María López", "maria")
    people.delete_soft_person(p.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        debts.add_debt(
            person_id=p.id,
            amount_eur_cents=1000,
            description="test",
        )


def test_add_debt_without_description() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=2000,
        description=None,
    )

    assert d.description is None


def test_get_debt_existing() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T10:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1500,
        description="kebab",
    )

    got = debts.get_debt(d.id)
    assert got.id == d.id
    assert got.person_id == p.id


def test_get_debt_missing_raises_keyerror() -> None:
    conn = make_conn()
    debts = DebtRepo(conn)

    with pytest.raises(KeyError):
        debts.get_debt(9999)


def test_list_debts_empty() -> None:
    conn = make_conn()
    debts = DebtRepo(conn)

    assert debts.list_debts() == []


def test_list_debts_filters_by_person_and_orders_fifo() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p1 = people.add_person("Juan Pérez", "juan")
    p2 = people.add_person("María López", "maria")

    # Juan: deuda A (más antigua)
    d1 = debts.add_debt(
        person_id=p1.id,
        amount_eur_cents=1000,
        description="A",
        effective_at="2025-12-20T10:00:00+00:00",
    )
    # Juan: deuda B (más nueva)
    d2 = debts.add_debt(
        person_id=p1.id,
        amount_eur_cents=2000,
        description="B",
        effective_at="2025-12-21T10:00:00+00:00",
    )
    # María: otra
    debts.add_debt(
        person_id=p2.id,
        amount_eur_cents=3000,
        description="C",
    )

    juan_debts = debts.list_debts(person_id=p1.id)
    assert [d.id for d in juan_debts] == [d1.id, d2.id]


def test_list_debts_excludes_voided_by_default() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description="A",
    )

    conn.execute("UPDATE debts SET status='VOIDED' WHERE id=?", (d.id,))

    assert debts.list_debts() == []
    assert debts.list_debts(include_voided=True) != []


def test_void_debt_success() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description="A",
    )

    vd = debts.void_debt(d.id, "2025-12-29T11:00:00+00:00")

    assert vd.status == "VOIDED"


def test_void_debt_missing_raises_keyerror() -> None:
    conn = make_conn()
    debts = DebtRepo(conn)

    with pytest.raises(KeyError):
        debts.void_debt(9999, "2025-12-29T11:00:00+00:00")


def test_void_debt_already_voided_raises_keyerror() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description="A",
    )

    debts.void_debt(d.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        debts.void_debt(d.id, "2025-12-29T12:00:00+00:00")


# UPDATES

def test_update_debt_updates_description_only() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description=None,
    )

    updated = debts.update_debt(d.id, description="kebab")
    assert updated.description == "kebab"
    assert updated.effective_at == d.effective_at


def test_update_debt_updates_effective_at_only() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description="A",
    )

    updated = debts.update_debt(d.id, effective_at="2025-12-20T10:00:00+00:00")
    assert updated.description == "A"
    assert updated.effective_at == "2025-12-20T10:00:00+00:00"


def test_update_debt_missing_raises_keyerror() -> None:
    conn = make_conn()
    debts = DebtRepo(conn)

    with pytest.raises(KeyError):
        debts.update_debt(9999, description="x")


def test_update_debt_voided_raises_keyerror() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    debts = DebtRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    d = debts.add_debt(
        person_id=p.id,
        amount_eur_cents=1000,
        description="A",
    )

    debts.void_debt(d.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        debts.update_debt(d.id, description="should fail")
