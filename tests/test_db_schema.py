from __future__ import annotations

import sqlite3

from app.db.schema import create_schema


def test_schema_creates_tables() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    create_schema(conn)

    # comprueba que existen tablas clave
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "people" in tables
    assert "debts" in tables
    assert "payments" in tables
    assert "allocations" in tables


def test_can_insert_person_and_debt() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    create_schema(conn)

    conn.execute(
        "INSERT INTO people(full_name, alias, created_at) VALUES (?, ?, ?)",
        ("Juan Pérez", "juan", "2025-12-29T10:00:00+00:00"),
    )
    person_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    conn.execute(
        """
        INSERT INTO debts(person_id, original_amount_eur, description, status, created_at, effective_at)
        VALUES (?, ?, ?, 'OPEN', ?, ?)
        """,
        (person_id, 1500, "kebab", "2025-12-29T10:00:01+00:00", None),
    )
    debt_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    row = conn.execute(
        "SELECT person_id, original_amount_eur, status FROM debts WHERE id=?",
        (debt_id,),
    ).fetchone()
    assert row is not None
    assert int(row["person_id"]) == person_id
    assert int(row["original_amount_eur"]) == 1500
    assert row["status"] == "OPEN"