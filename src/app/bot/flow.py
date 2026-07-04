from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from app.db.people_repo import PeopleRepo
from app.domain.models import Debt, Person
from app.services.ledger_service import LedgerService

ChatState = Dict[str, Any]

HOME = "HOME"
PERSON_NAME = "PERSON_NAME"
PERSON_ALIAS_CHOICE = "PERSON_ALIAS_CHOICE"
PERSON_ALIAS_TEXT = "PERSON_ALIAS_TEXT"
PERSON_CONFIRM = "PERSON_CONFIRM"
DEBT_SELECT_PERSON = "DEBT_SELECT_PERSON"
DEBT_AMOUNT = "DEBT_AMOUNT"
DEBT_DESCRIPTION = "DEBT_DESCRIPTION"
DEBT_CONFIRM = "DEBT_CONFIRM"
PAY_SELECT_PERSON = "PAY_SELECT_PERSON"
PAY_MODE = "PAY_MODE"
PAY_AMOUNT = "PAY_AMOUNT"
PAY_SELECT_DEBT = "PAY_SELECT_DEBT"
PAY_METHOD_GENERAL = "PAY_METHOD_GENERAL"
PAY_METHOD_DEBT = "PAY_METHOD_DEBT"
PAY_CONFIRM_GENERAL = "PAY_CONFIRM_GENERAL"
PAY_CONFIRM_DEBT = "PAY_CONFIRM_DEBT"
BALANCE_SELECT_PERSON = "BALANCE_SELECT_PERSON"
DEBTS_MENU = "DEBTS_MENU"
DEBTS_SELECT_PERSON = "DEBTS_SELECT_PERSON"
DEBTS_PERSON = "DEBTS_PERSON"
DEBTS_ALL_OPEN = "DEBTS_ALL_OPEN"
DEBT_DETAIL = "DEBT_DETAIL"


@dataclass(frozen=True)
class Button:
    label: str
    action: str


@dataclass(frozen=True)
class View:
    text: str
    buttons: List[List[Button]]


def parse_eur_cents(value: str) -> int:
    normalized = value.strip().replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("importe no valido") from exc

    cents = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise ValueError("el importe debe ser mayor que cero")
    return cents


def format_eur_cents(amount_eur_cents: int) -> str:
    return f"{amount_eur_cents / 100:.2f} EUR"


def start_view(conn: sqlite3.Connection, state: ChatState) -> View:
    state.clear()
    state["screen"] = HOME
    return render_current(conn, state)


def handle_action(conn: sqlite3.Connection, state: ChatState, action: str) -> View:
    if action in {"home", "cancel"}:
        return start_view(conn, state)

    try:
        if action == "person_add":
            state.clear()
            state["screen"] = PERSON_NAME
            state["draft"] = {}
            return render_current(conn, state)

        if action == "person_alias_yes" and state.get("screen") == PERSON_ALIAS_CHOICE:
            state["screen"] = PERSON_ALIAS_TEXT
            return render_current(conn, state)

        if action == "person_alias_no" and state.get("screen") == PERSON_ALIAS_CHOICE:
            state["draft"]["alias"] = None
            state["screen"] = PERSON_CONFIRM
            return render_current(conn, state)

        if action == "person_confirm" and state.get("screen") == PERSON_CONFIRM:
            draft = state["draft"]
            person = PeopleRepo(conn).add_person(draft["full_name"], draft.get("alias"))
            state.clear()
            state["screen"] = HOME
            return _with_notice(render_current(conn, state), f"Persona creada: {person_label(person)}.")

        if action == "debt_new":
            state.clear()
            state["screen"] = DEBT_SELECT_PERSON
            state["draft"] = {}
            return render_current(conn, state)

        if action == "debt_desc_none" and state.get("screen") == DEBT_DESCRIPTION:
            state["draft"]["description"] = None
            state["screen"] = DEBT_CONFIRM
            return render_current(conn, state)

        if action == "debt_confirm" and state.get("screen") == DEBT_CONFIRM:
            draft = state["draft"]
            debt = LedgerService(conn).debts.add_debt(
                person_id=int(draft["person_id"]),
                amount_eur_cents=int(draft["amount_eur"]),
                description=draft.get("description"),
            )
            state.clear()
            state["screen"] = HOME
            return _with_notice(render_current(conn, state), f"Deuda #{debt.id} creada.")

        if action == "payment_new":
            state.clear()
            state["screen"] = PAY_SELECT_PERSON
            state["draft"] = {}
            return render_current(conn, state)

        if action == "pay_general" and state.get("screen") == PAY_MODE:
            state["draft"]["mode"] = "general"
            state["screen"] = PAY_AMOUNT
            return render_current(conn, state)

        if action == "pay_debt" and state.get("screen") == PAY_MODE:
            state["draft"]["mode"] = "debt"
            state["screen"] = PAY_SELECT_DEBT
            return render_current(conn, state)

        if action.startswith("method:"):
            method = action.split(":", 1)[1]
            state.setdefault("draft", {})["method"] = None if method == "none" else method
            if state.get("screen") == PAY_METHOD_GENERAL:
                state["screen"] = PAY_CONFIRM_GENERAL
                return render_current(conn, state)
            if state.get("screen") == PAY_METHOD_DEBT:
                state["screen"] = PAY_CONFIRM_DEBT
                return render_current(conn, state)

        if action == "pay_confirm_general" and state.get("screen") == PAY_CONFIRM_GENERAL:
            draft = state["draft"]
            result = LedgerService(conn).record_payment_and_allocate(
                person_id=int(draft["person_id"]),
                amount_eur_cents=int(draft["amount_eur"]),
                method=draft.get("method"),
            )
            applied = int(draft["amount_eur"]) - result.unapplied_amount_eur
            state.clear()
            state["screen"] = HOME
            message = (
                f"Pago registrado. Aplicado: {format_eur_cents(applied)}. "
                f"Sobrante: {format_eur_cents(result.unapplied_amount_eur)}."
            )
            return _with_notice(render_current(conn, state), message)

        if action == "pay_confirm_debt" and state.get("screen") == PAY_CONFIRM_DEBT:
            draft = state["draft"]
            result = LedgerService(conn).record_payment_for_debt(
                debt_id=int(draft["debt_id"]),
                method=draft.get("method"),
            )
            state.clear()
            state["screen"] = HOME
            message = f"Deuda pagada con {format_eur_cents(result.payment.amount_eur)}."
            return _with_notice(render_current(conn, state), message)

        if action == "balances":
            state.clear()
            state["screen"] = BALANCE_SELECT_PERSON
            return render_current(conn, state)

        if action == "debts":
            state.clear()
            state["screen"] = DEBTS_MENU
            return render_current(conn, state)

        if action == "debts_all_open":
            state.clear()
            state["screen"] = DEBTS_ALL_OPEN
            return render_current(conn, state)

        if action == "debts_by_person":
            state.clear()
            state["screen"] = DEBTS_SELECT_PERSON
            return render_current(conn, state)

        if action.startswith("person:"):
            person_id = int(action.split(":", 1)[1])
            return _handle_person_action(conn, state, person_id)

        if action.startswith("paydebt:") and state.get("screen") in {PAY_SELECT_DEBT, DEBT_DETAIL}:
            debt_id = int(action.split(":", 1)[1])
            state["draft"] = {"debt_id": debt_id}
            state["screen"] = PAY_METHOD_DEBT
            return render_current(conn, state)

        if action.startswith("debt:"):
            debt_id = int(action.split(":", 1)[1])
            state.clear()
            state["screen"] = DEBT_DETAIL
            state["debt_id"] = debt_id
            return render_current(conn, state)

        if action.startswith("debts_person:"):
            person_id = int(action.split(":", 1)[1])
            state.clear()
            state["screen"] = DEBTS_PERSON
            state["person_id"] = person_id
            return render_current(conn, state)

    except (KeyError, ValueError) as exc:
        return _with_notice(render_current(conn, state), f"No puedo hacer eso: {exc}")

    return _unexpected(conn, state)


def handle_text(conn: sqlite3.Connection, state: ChatState, text: str) -> View:
    screen = state.get("screen", HOME)
    clean = text.strip()

    try:
        if screen == PERSON_NAME:
            if not clean:
                raise ValueError("necesito un nombre")
            state["draft"]["full_name"] = clean
            state["screen"] = PERSON_ALIAS_CHOICE
            return render_current(conn, state)

        if screen == PERSON_ALIAS_TEXT:
            alias = clean.removeprefix("@").strip()
            if not alias:
                raise ValueError("necesito un alias o cancelar")
            state["draft"]["alias"] = alias
            state["screen"] = PERSON_CONFIRM
            return render_current(conn, state)

        if screen == DEBT_AMOUNT:
            state["draft"]["amount_eur"] = parse_eur_cents(clean)
            state["screen"] = DEBT_DESCRIPTION
            return render_current(conn, state)

        if screen == DEBT_DESCRIPTION:
            state["draft"]["description"] = clean if clean else None
            state["screen"] = DEBT_CONFIRM
            return render_current(conn, state)

        if screen == PAY_AMOUNT:
            state["draft"]["amount_eur"] = parse_eur_cents(clean)
            state["screen"] = PAY_METHOD_GENERAL
            return render_current(conn, state)

    except ValueError as exc:
        return _with_notice(render_current(conn, state), f"No me vale ese texto: {exc}")

    return _unexpected(conn, state)


def render_current(conn: sqlite3.Connection, state: ChatState) -> View:
    screen = state.get("screen", HOME)

    if screen == HOME:
        return View(
            text="Luigi esta listo. Que hacemos?",
            buttons=[
                [Button("Nueva deuda", "debt_new"), Button("Registrar pago", "payment_new")],
                [Button("Personas", "person_add"), Button("Saldos", "balances")],
                [Button("Deudas", "debts")],
            ],
        )

    if screen == PERSON_NAME:
        return View("Como se llama?", [[Button("Cancelar", "cancel")]])

    if screen == PERSON_ALIAS_CHOICE:
        name = state["draft"]["full_name"]
        return View(
            text=f"Quieres poner alias a {name}?",
            buttons=[[Button("Si", "person_alias_yes"), Button("No", "person_alias_no")], [Button("Cancelar", "cancel")]],
        )

    if screen == PERSON_ALIAS_TEXT:
        return View("Escribe el alias.", [[Button("Cancelar", "cancel")]])

    if screen == PERSON_CONFIRM:
        draft = state["draft"]
        alias = draft.get("alias")
        alias_text = f" @{alias}" if alias else ""
        return View(
            text=f"Crear persona:\n{draft['full_name']}{alias_text}",
            buttons=[[Button("Confirmar", "person_confirm")], [Button("Cancelar", "cancel")]],
        )

    if screen == DEBT_SELECT_PERSON:
        return _person_picker(conn, "A quien le apunto la deuda?")

    if screen == DEBT_AMOUNT:
        person = _person(conn, int(state["draft"]["person_id"]))
        return View(f"Cuanto debe {person_label(person)}?", [[Button("Cancelar", "cancel")]])

    if screen == DEBT_DESCRIPTION:
        return View(
            "Descripcion de la deuda?",
            [[Button("Sin descripcion", "debt_desc_none")], [Button("Cancelar", "cancel")]],
        )

    if screen == DEBT_CONFIRM:
        draft = state["draft"]
        person = _person(conn, int(draft["person_id"]))
        description = draft.get("description") or "Sin descripcion"
        return View(
            text=(
                "Nueva deuda:\n"
                f"{person_label(person)}\n"
                f"{format_eur_cents(int(draft['amount_eur']))}\n"
                f"{description}"
            ),
            buttons=[[Button("Confirmar", "debt_confirm")], [Button("Cancelar", "cancel")]],
        )

    if screen == PAY_SELECT_PERSON:
        return _person_picker(conn, "Quien ha pagado?")

    if screen == PAY_MODE:
        person = _person(conn, int(state["draft"]["person_id"]))
        return View(
            f"Que ha pagado {person_label(person)}?",
            [[Button("Una deuda concreta", "pay_debt")], [Button("Una cantidad general", "pay_general")], [Button("Cancelar", "cancel")]],
        )

    if screen == PAY_AMOUNT:
        person = _person(conn, int(state["draft"]["person_id"]))
        return View(f"Cuanto ha pagado {person_label(person)}?", [[Button("Cancelar", "cancel")]])

    if screen == PAY_SELECT_DEBT:
        return _debt_picker_for_payment(conn, int(state["draft"]["person_id"]))

    if screen in {PAY_METHOD_GENERAL, PAY_METHOD_DEBT}:
        return View(
            "Metodo de pago?",
            [
                [Button("Bizum", "method:Bizum"), Button("Efectivo", "method:Efectivo")],
                [Button("Transferencia", "method:Transferencia"), Button("Sin metodo", "method:none")],
                [Button("Cancelar", "cancel")],
            ],
        )

    if screen == PAY_CONFIRM_GENERAL:
        draft = state["draft"]
        person = _person(conn, int(draft["person_id"]))
        method = draft.get("method") or "Sin metodo"
        return View(
            text=f"Registrar pago general:\n{person_label(person)}\n{format_eur_cents(int(draft['amount_eur']))}\n{method}",
            buttons=[[Button("Confirmar", "pay_confirm_general")], [Button("Cancelar", "cancel")]],
        )

    if screen == PAY_CONFIRM_DEBT:
        debt = LedgerService(conn).debts.get_debt(int(state["draft"]["debt_id"]))
        person = _person(conn, debt.person_id)
        remaining = LedgerService(conn).remaining_amount_for_debt(debt.id)
        method = state["draft"].get("method") or "Sin metodo"
        return View(
            text=(
                "Pagar deuda concreta:\n"
                f"#{debt.id} - {person_label(person)}\n"
                f"{_debt_description(debt)}\n"
                f"Pendiente: {format_eur_cents(remaining)}\n"
                f"{method}"
            ),
            buttons=[[Button("Confirmar", "pay_confirm_debt")], [Button("Cancelar", "cancel")]],
        )

    if screen == BALANCE_SELECT_PERSON:
        return _balances_view(conn)

    if screen == DEBTS_MENU:
        return View(
            "Que deudas quieres ver?",
            [[Button("Todas abiertas", "debts_all_open")], [Button("Por persona", "debts_by_person")], [Button("Volver", "home")]],
        )

    if screen == DEBTS_SELECT_PERSON:
        return _person_picker(conn, "De quien quieres ver las deudas?")

    if screen == DEBTS_PERSON:
        return _person_debts_view(conn, int(state["person_id"]))

    if screen == DEBTS_ALL_OPEN:
        return _all_open_debts_view(conn)

    if screen == DEBT_DETAIL:
        return _debt_detail_view(conn, int(state["debt_id"]))

    state.clear()
    state["screen"] = HOME
    return render_current(conn, state)


def _handle_person_action(conn: sqlite3.Connection, state: ChatState, person_id: int) -> View:
    screen = state.get("screen")
    if screen == DEBT_SELECT_PERSON:
        state["draft"]["person_id"] = person_id
        state["screen"] = DEBT_AMOUNT
        return render_current(conn, state)
    if screen == PAY_SELECT_PERSON:
        state["draft"]["person_id"] = person_id
        state["screen"] = PAY_MODE
        return render_current(conn, state)
    if screen == DEBTS_SELECT_PERSON:
        state.clear()
        state["screen"] = DEBTS_PERSON
        state["person_id"] = person_id
        return render_current(conn, state)
    if screen == BALANCE_SELECT_PERSON:
        state.clear()
        state["screen"] = BALANCE_SELECT_PERSON
        return _person_balance_view(conn, person_id)
    return _unexpected(conn, state)


def _person_picker(conn: sqlite3.Connection, title: str) -> View:
    people = PeopleRepo(conn).list_person()
    if not people:
        return View(
            f"{title}\nNo hay personas todavia.",
            [[Button("Crear persona", "person_add")], [Button("Cancelar", "cancel")]],
        )

    buttons = [[Button(person_label(person), f"person:{person.id}")] for person in people[:8]]
    buttons.append([Button("Crear persona", "person_add"), Button("Cancelar", "cancel")])
    return View(title, buttons)


def _debt_picker_for_payment(conn: sqlite3.Connection, person_id: int) -> View:
    pending = LedgerService(conn).get_pending_debts(person_id)
    if not pending:
        return View(
            "Esa persona no tiene deudas pendientes.",
            [[Button("Cantidad general", "pay_general")], [Button("Cancelar", "cancel")]],
        )

    buttons = []
    for item in pending[:8]:
        debt = item.debt
        label = f"#{debt.id} - {format_eur_cents(item.remaining_amount_eur)} - {_debt_description(debt)}"
        buttons.append([Button(label, f"paydebt:{debt.id}")])
    buttons.append([Button("Cancelar", "cancel")])
    return View("Que deuda ha pagado?", buttons)


def _balances_view(conn: sqlite3.Connection) -> View:
    people = PeopleRepo(conn).list_person()
    if not people:
        return View("No hay personas todavia.", [[Button("Crear persona", "person_add")], [Button("Volver", "home")]])

    ledger = LedgerService(conn)
    lines = ["Saldos:"]
    buttons = []
    for person in people:
        balance = ledger.get_person_balance(person.id)
        lines.append(f"{person_label(person)}: {format_eur_cents(balance.balance_eur)}")
        buttons.append([Button(f"Ver {person_label(person)}", f"person:{person.id}")])
    buttons.append([Button("Volver", "home")])
    return View("\n".join(lines), buttons)


def _person_balance_view(conn: sqlite3.Connection, person_id: int) -> View:
    person = _person(conn, person_id)
    ledger = LedgerService(conn)
    balance = ledger.get_person_balance(person_id)
    pending = ledger.get_pending_debts(person_id)
    unapplied = ledger.get_unapplied_payments(person_id)
    text = (
        f"{person_label(person)}\n"
        f"Debe: {format_eur_cents(balance.balance_eur)}\n"
        f"Pagado: {format_eur_cents(balance.paid_total_eur)}\n"
        f"Deudas abiertas: {len(pending)}\n"
        f"Pagos con sobrante: {len(unapplied)}"
    )
    return View(
        text,
        [
            [Button("Nueva deuda", "debt_new"), Button("Registrar pago", "payment_new")],
            [Button("Ver deudas", f"debts_person:{person_id}")],
            [Button("Inicio", "home")],
        ],
    )


def _all_open_debts_view(conn: sqlite3.Connection) -> View:
    ledger = LedgerService(conn)
    pending_by_person = []
    for person in PeopleRepo(conn).list_person():
        pending_by_person.extend((person, item) for item in ledger.get_pending_debts(person.id))

    if not pending_by_person:
        return View("No hay deudas abiertas.", [[Button("Nueva deuda", "debt_new")], [Button("Volver", "debts")]])

    lines = ["Deudas abiertas:"]
    buttons = []
    for person, item in pending_by_person[:8]:
        debt = item.debt
        lines.append(
            f"#{debt.id} {person_label(person)} - {format_eur_cents(item.remaining_amount_eur)} - {_debt_description(debt)}"
        )
        buttons.append([Button(f"Ver #{debt.id}", f"debt:{debt.id}")])
    buttons.append([Button("Volver", "debts")])
    return View("\n".join(lines), buttons)


def _person_debts_view(conn: sqlite3.Connection, person_id: int) -> View:
    person = _person(conn, person_id)
    ledger = LedgerService(conn)
    debts = ledger.debts.list_debts(person_id=person_id)
    if not debts:
        return View(
            f"{person_label(person)} no tiene deudas.",
            [[Button("Nueva deuda", "debt_new")], [Button("Volver", "debts")]],
        )

    lines = [f"Deudas de {person_label(person)}:"]
    buttons = []
    for debt in debts[:8]:
        paid = ledger.allocations.applied_amount_for_debt(debt.id)
        remaining = max(debt.original_amount_eur - paid, 0)
        lines.append(
            f"#{debt.id} - {debt.status} - {format_eur_cents(remaining)} pendiente - {_debt_description(debt)}"
        )
        buttons.append([Button(f"Ver #{debt.id}", f"debt:{debt.id}")])
    buttons.append([Button("Nueva deuda", "debt_new"), Button("Registrar pago", "payment_new")])
    buttons.append([Button("Volver", "debts")])
    return View("\n".join(lines), buttons)


def _debt_detail_view(conn: sqlite3.Connection, debt_id: int) -> View:
    ledger = LedgerService(conn)
    debt = ledger.debts.get_debt(debt_id, include_voided=True)
    person = _person(conn, debt.person_id)
    paid = ledger.allocations.applied_amount_for_debt(debt.id)
    remaining = max(debt.original_amount_eur - paid, 0)
    text = (
        f"Deuda #{debt.id}\n"
        f"Persona: {person_label(person)}\n"
        f"Descripcion: {_debt_description(debt)}\n"
        f"Original: {format_eur_cents(debt.original_amount_eur)}\n"
        f"Pagado: {format_eur_cents(paid)}\n"
        f"Pendiente: {format_eur_cents(remaining)}\n"
        f"Estado: {debt.status}"
    )
    buttons = []
    if remaining > 0 and debt.status != "VOIDED":
        buttons.append([Button("Registrar pago de esta deuda", f"paydebt:{debt.id}")])
    buttons.append([Button("Volver a deudas", "debts"), Button("Inicio", "home")])
    return View(text, buttons)


def _person(conn: sqlite3.Connection, person_id: int) -> Person:
    return PeopleRepo(conn).get_person(person_id)


def person_label(person: Person) -> str:
    if person.alias is None:
        return person.full_name
    return f"{person.full_name} @{person.alias}"


def _debt_description(debt: Debt) -> str:
    return debt.description if debt.description else "Sin descripcion"


def _with_notice(view: View, notice: str) -> View:
    return View(f"{notice}\n\n{view.text}", view.buttons)


def _unexpected(conn: sqlite3.Connection, state: ChatState) -> View:
    return _with_notice(render_current(conn, state), "No esperaba eso ahora. Usa uno de estos botones.")
