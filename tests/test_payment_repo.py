from __future__ import annotations

import sqlite3
import pytest

from app.db.schema import create_schema
from app.db.people_repo import PeopleRepo
from app.db.payment_repo import PaymentRepo


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def test_record_payment_success_defaults_effective_at() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=5000,
        method=None,
        description=None,
        effective_at=None,
    )

    assert pay.id > 0
    assert pay.person_id == p.id
    assert pay.amount_eur == 5000
    assert pay.status == "POSTED"
    assert pay.created_at == "2025-12-29T09:00:00+00:00"
    assert pay.effective_at == "2025-12-29T09:00:00+00:00"
    assert pay.effective_at == pay.created_at
    assert pay.voided_at is None


def test_record_payment_success_with_explicit_effective_at() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=2000,
        effective_at="2025-12-20T10:00:00+00:00",
    )

    assert pay.effective_at == "2025-12-20T10:00:00+00:00"
    assert pay.effective_at != pay.created_at


def test_record_payment_rejects_non_positive_amount() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")

    with pytest.raises(ValueError):
        payments.record_payment(
            person_id=p.id,
            amount_eur_cents=0,
        )


def test_record_payment_person_not_found_or_deleted() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    with pytest.raises(KeyError):
        payments.record_payment(
            person_id=999,
            amount_eur_cents=1000,
        )

    p = people.add_person("María López", "maria")
    people.delete_soft_person(p.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        payments.record_payment(
            person_id=p.id,
            amount_eur_cents=1000,
        )

def test_get_payment_existing() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=3000,
    )

    got = payments.get_payment(pay.id)
    assert got.id == pay.id
    assert got.person_id == p.id
    assert got.person_id == pay.person_id
    assert got.amount_eur == 3000
    assert got.amount_eur == pay.amount_eur


def test_get_payment_missing_raises_keyerror() -> None:
    conn = make_conn()
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    with pytest.raises(KeyError):
        payments.get_payment(9999)

def test_list_payments_empty() -> None:
    conn = make_conn()
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    assert payments.list_payments() == []


def test_list_payments_filters_by_person_and_orders() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p1 = people.add_person("Juan Pérez", "juan")
    p2 = people.add_person("María López", "maria")

    pay1 = payments.record_payment(
        person_id=p1.id,
        amount_eur_cents=1000,
        effective_at="2025-12-20T10:00:00+00:00",
    )
    pay2 = payments.record_payment(
        person_id=p1.id,
        amount_eur_cents=2000,
        effective_at="2025-12-21T10:00:00+00:00",
    )
    payments.record_payment(
        person_id=p2.id,
        amount_eur_cents=3000,
    )

    juan_payments = payments.list_payments(person_id=p1.id)
    assert [p.id for p in juan_payments] == [pay1.id, pay2.id]

def test_list_all_payments() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p1 = people.add_person("Juan Pérez", "juan")
    p2 = people.add_person("María López", "maria")

    pay1 = payments.record_payment(
        person_id=p1.id,
        amount_eur_cents=1000,
    )
    pay2 = payments.record_payment(
        person_id=p1.id,
        amount_eur_cents=2000,
    )
    pay3 = payments.record_payment(
        person_id=p2.id,
        amount_eur_cents=3000,
    )

    all_payments = payments.list_payments()
    assert [p.id for p in all_payments] == [pay1.id, pay2.id, pay3.id]

def test_void_payment_success() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
    )

    voided = payments.void_payment(pay.id, "2025-12-29T11:00:00+00:00")
    assert voided.status == "VOIDED"
    assert voided.voided_at == "2025-12-29T11:00:00+00:00"


def test_void_payment_missing_raises_keyerror() -> None:
    conn = make_conn()
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    with pytest.raises(KeyError):
        payments.void_payment(9999, "2025-12-29T11:00:00+00:00")


def test_get_payment_excludes_voided_by_default() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
    )
    payments.void_payment(pay.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        payments.get_payment(pay.id)

    got = payments.get_payment(pay.id, include_voided=True)
    assert got.status == "VOIDED"


def test_list_payments_excludes_voided_by_default() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay1 = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
        effective_at="2025-12-20T10:00:00+00:00",
    )
    pay2 = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=2000,
        effective_at="2025-12-21T10:00:00+00:00",
    )

    payments.void_payment(pay1.id, "2025-12-29T11:00:00+00:00")

    listed = payments.list_payments(person_id=p.id)
    assert [p.id for p in listed] == [pay2.id]

    listed_all = payments.list_payments(person_id=p.id, include_voided=True)
    assert [p.id for p in listed_all] == [pay1.id, pay2.id]

def test_update_payment_updates_method_only() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
        method=None,
        description=None,
    )

    updated = payments.update_payment(pay.id, method="CASH")
    assert updated.method == "CASH"
    assert updated.description is None
    assert updated.effective_at == pay.effective_at


def test_update_payment_updates_description_and_effective_at() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
        description="old",
    )

    updated = payments.update_payment(
        pay.id,
        description="new",
        effective_at="2025-12-20T10:00:00+00:00",
    )
    assert updated.description == "new"
    assert updated.effective_at == "2025-12-20T10:00:00+00:00"


def test_update_payment_missing_raises_keyerror() -> None:
    conn = make_conn()
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    with pytest.raises(KeyError):
        payments.update_payment(9999, method="CASH")


def test_update_payment_voided_raises_keyerror() -> None:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")
    payments = PaymentRepo(conn, now_fn=lambda: "2025-12-29T09:00:00+00:00")

    p = people.add_person("Juan Pérez", "juan")
    pay = payments.record_payment(
        person_id=p.id,
        amount_eur_cents=1000,
    )
    payments.void_payment(pay.id, "2025-12-29T11:00:00+00:00")

    with pytest.raises(KeyError):
        payments.update_payment(pay.id, method="BIZUM")
