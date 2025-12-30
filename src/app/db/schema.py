from __future__ import annotations

import sqlite3


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            alias TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0, 1)),
            deleted_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            original_amount_eur INTEGER NOT NULL, -- store cents as integer
            description TEXT,
            status TEXT NOT NULL CHECK (status IN ('OPEN', 'PAID', 'VOIDED')),
            created_at TEXT NOT NULL,
            effective_at TEXT,
            voided_at TEXT,   
            FOREIGN KEY (person_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            amount_eur INTEGER NOT NULL, -- cents
            method TEXT, -- optional
            description TEXT, -- optional
            status TEXT NOT NULL CHECK (status IN ('POSTED', 'VOIDED')),
            created_at TEXT NOT NULL,
            effective_at TEXT NOT NULL, --will be created_at by default
            voided_at TEXT,
            FOREIGN KEY (person_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            debt_id INTEGER NOT NULL,
            allocated_amount_eur INTEGER NOT NULL, -- cents
            status TEXT NOT NULL CHECK (status IN ('APPLIED', 'VOIDED')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (payment_id) REFERENCES payments(id),
            FOREIGN KEY (debt_id) REFERENCES debts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_people_alias ON people(alias);
        CREATE INDEX IF NOT EXISTS idx_debts_person_status ON debts(person_id, status);
        CREATE INDEX IF NOT EXISTS idx_payments_person_status ON payments(person_id, status);
        CREATE INDEX IF NOT EXISTS idx_alloc_payment ON allocations(payment_id);
        CREATE INDEX IF NOT EXISTS idx_alloc_debt ON allocations(debt_id);
        """
    )
