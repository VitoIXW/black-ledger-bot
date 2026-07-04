from __future__ import annotations

import sqlite3

import pytest

from app.db.people_repo import PeopleRepo
from app.db.schema import create_schema
from app.services.ledger_service import LedgerService

FIXED_NOW = "2025-12-29T09:00:00+00:00"


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def make_service() -> tuple[sqlite3.Connection, PeopleRepo, LedgerService]:
    conn = make_conn()
    people = PeopleRepo(conn, now_fn=lambda: FIXED_NOW)
    ledger = LedgerService(conn, now_fn=lambda: FIXED_NOW)
    return conn, people, ledger


def test_record_payment_allocates_fifo_and_marks_paid() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")

    d1 = ledger.debts.add_debt(
        person_id=person.id,
        amount_eur_cents=1000,
        description="old",
        effective_at="2025-12-20T10:00:00+00:00",
    )
    d2 = ledger.debts.add_debt(
        person_id=person.id,
        amount_eur_cents=2000,
        description="new",
        effective_at="2025-12-21T10:00:00+00:00",
    )

    result = ledger.record_payment_and_allocate(
        person_id=person.id,
        amount_eur_cents=2500,
        method="BIZUM",
    )

    assert result.unapplied_amount_eur == 0
    assert [a.debt_id for a in result.allocations] == [d1.id, d2.id]
    assert [a.allocated_amount_eur for a in result.allocations] == [1000, 1500]

    assert ledger.debts.get_debt(d1.id).status == "PAID"
    assert ledger.debts.get_debt(d2.id).status == "OPEN"
    assert ledger.remaining_amount_for_debt(d2.id) == 500


def test_record_payment_keeps_unapplied_surplus() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    ledger.debts.add_debt(person_id=person.id, amount_eur_cents=1000, description="kebab")

    result = ledger.record_payment_and_allocate(person_id=person.id, amount_eur_cents=1500)

    assert result.unapplied_amount_eur == 500
    assert ledger.get_person_balance(person.id).balance_eur == 0

    unapplied = ledger.get_unapplied_payments(person.id)
    assert len(unapplied) == 1
    assert unapplied[0].remaining_amount_eur == 500


def test_record_payment_for_debt_pays_exact_remaining_amount() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    debt = ledger.debts.add_debt(person_id=person.id, amount_eur_cents=1250, description="kebab")

    ledger.record_payment_and_allocate(person_id=person.id, amount_eur_cents=500)
    result = ledger.record_payment_for_debt(debt.id, method="Bizum")

    assert result.payment.amount_eur == 750
    assert result.payment.method == "Bizum"
    assert result.unapplied_amount_eur == 0
    assert result.allocations[0].allocated_amount_eur == 750
    assert ledger.debts.get_debt(debt.id).status == "PAID"


def test_pending_debts_and_balance_ignore_fully_paid_debts() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    ledger.debts.add_debt(person_id=person.id, amount_eur_cents=1000, description="A")
    ledger.debts.add_debt(person_id=person.id, amount_eur_cents=2000, description="B")

    ledger.record_payment_and_allocate(person_id=person.id, amount_eur_cents=1200)

    pending = ledger.get_pending_debts(person.id)
    assert len(pending) == 1
    assert pending[0].debt.description == "B"
    assert pending[0].remaining_amount_eur == 1800

    balance = ledger.get_person_balance(person.id)
    assert balance.debt_total_eur == 3000
    assert balance.paid_total_eur == 1200
    assert balance.balance_eur == 1800


def test_void_payment_reopens_debt_and_voids_allocations() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    debt = ledger.debts.add_debt(person_id=person.id, amount_eur_cents=1000, description="A")
    result = ledger.record_payment_and_allocate(person_id=person.id, amount_eur_cents=1000)

    assert ledger.debts.get_debt(debt.id).status == "PAID"

    ledger.void_payment(result.payment.id, voided_at="2025-12-29T10:00:00+00:00")

    assert ledger.debts.get_debt(debt.id).status == "OPEN"
    assert ledger.remaining_amount_for_debt(debt.id) == 1000
    assert ledger.allocations.list_allocations(payment_id=result.payment.id) == []
    assert len(ledger.allocations.list_allocations(payment_id=result.payment.id, include_voided=True)) == 1


def test_void_debt_voids_allocations_and_removes_balance() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    debt = ledger.debts.add_debt(person_id=person.id, amount_eur_cents=1000, description="A")
    result = ledger.record_payment_and_allocate(person_id=person.id, amount_eur_cents=1000)

    ledger.void_debt(debt.id, voided_at="2025-12-29T10:00:00+00:00")

    with pytest.raises(KeyError):
        ledger.debts.get_debt(debt.id)

    assert ledger.get_person_balance(person.id).balance_eur == 0
    assert ledger.get_unapplied_payments(person.id)[0].payment.id == result.payment.id
    assert ledger.get_unapplied_payments(person.id)[0].remaining_amount_eur == 1000


def test_history_includes_debts_and_payments() -> None:
    _, people, ledger = make_service()
    person = people.add_person("Juan Pérez", "juan")
    ledger.debts.add_debt(
        person_id=person.id,
        amount_eur_cents=1000,
        description="A",
        effective_at="2025-12-20T10:00:00+00:00",
    )
    ledger.record_payment_and_allocate(
        person_id=person.id,
        amount_eur_cents=500,
        description="partial",
        effective_at="2025-12-21T10:00:00+00:00",
    )

    history = ledger.get_person_history(person.id)

    assert [event.kind for event in history] == ["DEBT", "PAYMENT"]
    assert [event.amount_eur for event in history] == [1000, 500]
