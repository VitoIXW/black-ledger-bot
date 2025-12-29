from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Final

from app.domain.models import Person

PERSON_NOT_FOUND: Final[str] = "Person not found"

def _row_to_person(row: sqlite3.Row) -> Person:
    return Person(
        id=int(row["id"]),
        full_name=str(row["full_name"]),
        alias=str(row["alias"]) if row["alias"] is not None else None,
        is_deleted=bool(int(row["is_deleted"])),
        deleted_at=str(row["deleted_at"]) if row["deleted_at"] is not None else None,
        created_at=str(row["created_at"]),
    )


@dataclass(frozen=True)
class PeopleRepo:
    conn: sqlite3.Connection

    def add_person(self, full_name: str, alias: Optional[str], created_at: str) -> Person:
        cur = self.conn.execute(
            """
            INSERT INTO people(full_name, alias, created_at)
            VALUES (?, ?, ?)
            """,
            (full_name, alias, created_at),
        )
        person_id = int(cur.lastrowid)

        row = self.conn.execute(
            "SELECT * FROM people WHERE id=?",
            (person_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Insert succeeded but row not found (unexpected).")

        return _row_to_person(row)
    

    def get_person(self, person_id: int, include_deleted: bool = False) -> Person:
        if include_deleted:
            row = self.conn.execute(
                "SELECT * FROM people WHERE id=?",
                (person_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM people WHERE id=? AND is_deleted=0",
                (person_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"{PERSON_NOT_FOUND}: {person_id}")

        return _row_to_person(row)