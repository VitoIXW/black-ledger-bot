from __future__ import annotations

import sqlite3

from app.bot.flow import handle_action, handle_text, start_view
from app.db.people_repo import PeopleRepo
from app.db.schema import create_schema
from app.services.ledger_service import LedgerService


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def button_labels(view: object) -> list[str]:
    return [button.label for row in view.buttons for button in row]  # type: ignore[attr-defined]


def test_home_renders_button_driven_entry_points() -> None:
    conn = make_conn()
    state: dict[str, object] = {}

    view = start_view(conn, state)

    assert "Luigi esta listo" in view.text
    assert button_labels(view) == ["Nueva deuda", "Registrar pago", "Personas", "Saldos", "Deudas"]


def test_people_entry_opens_menu_instead_of_creating_person() -> None:
    conn = make_conn()
    state: dict[str, object] = {}
    start_view(conn, state)

    view = handle_action(conn, state, "people")

    assert view.text == "Personas"
    assert button_labels(view) == ["Listar personas", "Anadir persona", "Volver"]


def test_people_list_opens_person_detail_actions() -> None:
    conn = make_conn()
    person = PeopleRepo(conn).add_person("Juan Perez", "juan")
    LedgerService(conn).debts.add_debt(person.id, 1250, "kebab")
    state: dict[str, object] = {}
    start_view(conn, state)

    handle_action(conn, state, "people")
    handle_action(conn, state, "people_list")
    view = handle_action(conn, state, f"person:{person.id}")

    assert "Juan Perez @juan" in view.text
    assert "Deudas abiertas: 1" in view.text
    assert button_labels(view) == ["Ver deudas", "Editar nombre", "Editar alias", "Borrar persona", "Volver"]


def test_person_detail_can_update_name_and_clear_alias() -> None:
    conn = make_conn()
    person = PeopleRepo(conn).add_person("Juan Perez", "juan")
    state: dict[str, object] = {}
    start_view(conn, state)
    handle_action(conn, state, "people")
    handle_action(conn, state, "people_list")
    handle_action(conn, state, f"person:{person.id}")

    handle_action(conn, state, "person_edit_name")
    view = handle_text(conn, state, "Juan P. Perez")
    assert "Nombre actualizado" in view.text
    assert "Juan P. Perez @juan" in view.text

    handle_action(conn, state, "person_edit_alias")
    view = handle_action(conn, state, "person_alias_clear")
    assert "Alias actualizado" in view.text
    assert "Juan P. Perez\n" in view.text


def test_person_detail_can_soft_delete_person() -> None:
    conn = make_conn()
    person = PeopleRepo(conn).add_person("Juan Perez", "juan")
    state: dict[str, object] = {}
    start_view(conn, state)
    handle_action(conn, state, "people")
    handle_action(conn, state, "people_list")
    handle_action(conn, state, f"person:{person.id}")

    handle_action(conn, state, "person_delete")
    view = handle_action(conn, state, "person_delete_confirm")

    assert "Persona borrada" in view.text
    assert PeopleRepo(conn).list_person() == []


def test_unexpected_text_resends_current_buttons() -> None:
    conn = make_conn()
    state: dict[str, object] = {}
    start_view(conn, state)

    view = handle_text(conn, state, "hola")

    assert "No esperaba eso ahora" in view.text
    assert "Nueva deuda" in button_labels(view)


def test_payment_flow_can_pay_a_concrete_debt_without_amount() -> None:
    conn = make_conn()
    people = PeopleRepo(conn)
    person = people.add_person("Juan Perez", "juan")
    ledger = LedgerService(conn)
    debt = ledger.debts.add_debt(person.id, 1250, "kebab")
    ledger.record_payment_and_allocate(person.id, 500)

    state: dict[str, object] = {}
    start_view(conn, state)
    handle_action(conn, state, "payment_new")
    handle_action(conn, state, f"person:{person.id}")
    view = handle_action(conn, state, "pay_debt")

    assert "Que deuda ha pagado" in view.text
    assert f"#{debt.id} - 7.50 EUR - kebab" in button_labels(view)

    handle_action(conn, state, f"paydebt:{debt.id}")
    handle_action(conn, state, "method:Bizum")
    view = handle_action(conn, state, "pay_confirm_debt")

    assert "Deuda pagada con 7.50 EUR" in view.text
    assert ledger.debts.get_debt(debt.id).status == "PAID"


def test_debts_menu_lists_open_debts_with_person_and_description() -> None:
    conn = make_conn()
    people = PeopleRepo(conn)
    person = people.add_person("Juan Perez", "juan")
    LedgerService(conn).debts.add_debt(person.id, 1250, "kebab")

    state: dict[str, object] = {}
    start_view(conn, state)
    handle_action(conn, state, "debts")
    view = handle_action(conn, state, "debts_all_open")

    assert "#1 Juan Perez @juan - 12.50 EUR - kebab" in view.text
    assert "Ver #1" in button_labels(view)


def test_person_debt_list_shows_status_remaining_and_description() -> None:
    conn = make_conn()
    people = PeopleRepo(conn)
    person = people.add_person("Juan Perez", "juan")
    ledger = LedgerService(conn)
    ledger.debts.add_debt(person.id, 1250, "kebab")
    ledger.debts.add_debt(person.id, 700, "cine")
    ledger.record_payment_and_allocate(person.id, 1250)

    state: dict[str, object] = {}
    start_view(conn, state)
    handle_action(conn, state, "debts")
    handle_action(conn, state, "debts_by_person")
    view = handle_action(conn, state, f"person:{person.id}")

    assert "Deudas de Juan Perez @juan" in view.text
    assert "#1 - PAID - 0.00 EUR pendiente - kebab" in view.text
    assert "#2 - OPEN - 7.00 EUR pendiente - cine" in view.text
