from __future__ import annotations

import os
import sqlite3

from app.db.schema import create_schema
from app.domain.time import now_utc_iso


def main() -> None:
    db_path = os.environ.get("DB_PATH", "/data/black_ledger.db")
    # conn = sqlite3.connect(db_path)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    create_schema(conn)

    # Insert person
    conn.execute(
        "INSERT INTO people(full_name, alias, created_at) VALUES (?, ?, ?)",
        ("Juan Pérez", "juan", now_utc_iso()),
    )
    person_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    assert person_id > 0

    # Insert debt: 15.00 EUR -> 1500 cents
    conn.execute(
        """
        INSERT INTO debts(person_id, original_amount_eur, description, status, created_at, effective_at)
        VALUES (?, ?, ?, 'OPEN', ?, ?)
        """,
        (person_id, 1500, "kebab", now_utc_iso(), None),
    )
    debt_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    assert debt_id > 0

    row = conn.execute(
        "SELECT status, original_amount_eur FROM debts WHERE id=?",
        (debt_id,),
    ).fetchone()
    assert row is not None
    assert row["status"] == "OPEN"
    assert int(row["original_amount_eur"]) == 1500

    conn.commit()
    conn.close()
    print("SMOKETEST OK")


if __name__ == "__main__":
    main()