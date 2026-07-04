from __future__ import annotations

import sqlite3

from app.bot.commands import LedgerCommandHandler, parse_eur_cents
from app.db.schema import create_schema

FIXED_NOW = "2025-12-29T09:00:00+00:00"


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)
    return conn


def test_parse_eur_cents_accepts_comma_and_dot() -> None:
    assert parse_eur_cents("12.34") == 1234
    assert parse_eur_cents("12,34") == 1234


def test_command_handler_creates_person_debt_payment_and_balance() -> None:
    conn = make_conn()
    handler = LedgerCommandHandler(conn, now_fn=lambda: FIXED_NOW)

    assert handler.handle("person Juan Pérez @juan") == "Persona creada: #1 Juan Pérez @juan"
    assert handler.handle("debt 1 10.00 kebab") == "Deuda creada: #1 por 10.00 EUR"
    assert handler.handle("pay 1 4.50 BIZUM") == (
        "Pago registrado: #1. Aplicado 4.50 EUR; sobrante 0.00 EUR."
    )
    assert handler.handle("balance 1") == "Saldo #1: debe 5.50 EUR (4.50 EUR pagado de 10.00 EUR)."


def test_command_handler_reports_invalid_input() -> None:
    conn = make_conn()
    handler = LedgerCommandHandler(conn, now_fn=lambda: FIXED_NOW)

    assert handler.handle("pay 999 1.00").startswith("No puedo hacer eso:")
