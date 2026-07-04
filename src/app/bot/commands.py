from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable, List

from app.db.people_repo import PeopleRepo
from app.domain.models import Person
from app.domain.time import now_utc_iso
from app.services.ledger_service import LedgerService


def parse_eur_cents(value: str) -> int:
    normalized = value.strip().replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("amount must be a valid EUR number") from exc

    cents = int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise ValueError("amount must be > 0")
    return cents


def format_eur_cents(amount_eur_cents: int) -> str:
    return f"{amount_eur_cents / 100:.2f} EUR"


@dataclass(frozen=True)
class LedgerCommandHandler:
    conn: sqlite3.Connection
    now_fn: Callable[[], str] = now_utc_iso

    def handle(self, message: str) -> str:
        parts = message.strip().split()
        if not parts:
            return self._help()

        command = parts[0].lower()
        try:
            if command in {"help", "/help", "start", "/start"}:
                return self._help()
            if command in {"person", "/person"}:
                return self._add_person(parts[1:])
            if command in {"debt", "/debt"}:
                return self._add_debt(parts[1:])
            if command in {"pay", "payment", "/pay", "/payment"}:
                return self._record_payment(parts[1:])
            if command in {"balance", "/balance"}:
                return self._balance(parts[1:])
        except (KeyError, ValueError) as exc:
            return f"No puedo hacer eso: {exc}"

        return self._help()

    def _help(self) -> str:
        return (
            "Comandos: person <nombre> [alias], debt <person_id> <eur> [descripcion], "
            "pay <person_id> <eur> [metodo], balance <person_id>."
        )

    def _add_person(self, args: List[str]) -> str:
        if not args:
            raise ValueError("person needs at least a name")

        alias = None
        name_parts = args
        if len(args) > 1 and args[-1].startswith("@"):
            alias = args[-1][1:]
            name_parts = args[:-1]

        full_name = " ".join(name_parts).strip()
        if not full_name:
            raise ValueError("person needs a name")

        person = PeopleRepo(self.conn, now_fn=self.now_fn).add_person(full_name, alias)
        return f"Persona creada: #{person.id} {self._person_label(person)}"

    def _add_debt(self, args: List[str]) -> str:
        if len(args) < 2:
            raise ValueError("debt needs person_id and amount")

        person_id = int(args[0])
        amount = parse_eur_cents(args[1])
        description = " ".join(args[2:]).strip() if len(args) > 2 else None

        debt = LedgerService(self.conn, now_fn=self.now_fn).debts.add_debt(
            person_id=person_id,
            amount_eur_cents=amount,
            description=description,
        )
        return f"Deuda creada: #{debt.id} por {format_eur_cents(debt.original_amount_eur)}"

    def _record_payment(self, args: List[str]) -> str:
        if len(args) < 2:
            raise ValueError("pay needs person_id and amount")

        person_id = int(args[0])
        amount = parse_eur_cents(args[1])
        method = args[2] if len(args) > 2 else None

        result = LedgerService(self.conn, now_fn=self.now_fn).record_payment_and_allocate(
            person_id=person_id,
            amount_eur_cents=amount,
            method=method,
        )

        applied = amount - result.unapplied_amount_eur
        return (
            f"Pago registrado: #{result.payment.id}. "
            f"Aplicado {format_eur_cents(applied)}; "
            f"sobrante {format_eur_cents(result.unapplied_amount_eur)}."
        )

    def _balance(self, args: List[str]) -> str:
        if len(args) != 1:
            raise ValueError("balance needs person_id")

        person_id = int(args[0])
        balance = LedgerService(self.conn, now_fn=self.now_fn).get_person_balance(person_id)
        return (
            f"Saldo #{person_id}: debe {format_eur_cents(balance.balance_eur)} "
            f"({format_eur_cents(balance.paid_total_eur)} pagado de "
            f"{format_eur_cents(balance.debt_total_eur)})."
        )

    def _person_label(self, person: Person) -> str:
        if person.alias is None:
            return person.full_name
        return f"{person.full_name} @{person.alias}"
