from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Final, List

from app.domain.models import Debt


DEBT_NOT_FOUND: Final[str] = "Debt not found"


def _row_to_debt(row: sqlite3.Row) -> Debt:
    return Debt(
        id=int(row["id"]),
        person_id=int(row["person_id"]),
        original_amount_eur=int(row["original_amount_eur"]),  # cents
        description=str(row["description"]) if row["description"] is not None else None,
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        effective_at=str(row["effective_at"]) if row["effective_at"] is not None else None,
        voided_at=str(row["voided_at"]) if row["voided_at"] is not None else None
    )


@dataclass(frozen=True)
class DebtRepo:
    conn: sqlite3.Connection

    def add_debt(self, person_id: int, amount_eur_cents: int, created_at: str, description: Optional[str] = None, effective_at: Optional[str] = None) -> Debt:
        if amount_eur_cents <= 0:
            raise ValueError("amount_eur_cents must be > 0")

        row = self.conn.execute(
            "SELECT id FROM people WHERE id=? AND is_deleted=0",
            (person_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Person not found: {person_id}")

        cur = self.conn.execute(
            """
            INSERT INTO debts(
                person_id,
                original_amount_eur,
                description,
                status,
                created_at,
                effective_at
            )
            VALUES (?, ?, ?, 'OPEN', ?, ?)
            """,
            (person_id, amount_eur_cents, description, created_at, effective_at),
        )
        debt_id = int(cur.lastrowid)

        row2 = self.conn.execute(
            "SELECT * FROM debts WHERE id=?",
            (debt_id,),
        ).fetchone()
        if row2 is None:
            raise RuntimeError("Insert debt succeeded but row not found (unexpected).")

        return _row_to_debt(row2)
    

    def get_debt(self, debt_id: int, include_voided: bool = False) -> Debt:
        if include_voided:
            row = self.conn.execute(
                "SELECT * FROM debts WHERE id=?",
                (debt_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM debts WHERE id=? AND status != 'VOIDED'",
                (debt_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"{DEBT_NOT_FOUND}: {debt_id}")

        return _row_to_debt(row)
    
    def list_debts(self, person_id: Optional[int] = None, status: Optional[str] = None, include_voided: bool = False) -> List[Debt]:
        conditions: List[str] = []
        params: List[object] = []

        if person_id is not None:
            conditions.append("person_id=?")
            params.append(person_id)

        if status is not None:
            conditions.append("status=?")
            params.append(status)
        else:
            if not include_voided:
                conditions.append("status != 'VOIDED'")

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(
            f"""
            SELECT * FROM debts
            {where_sql}
            ORDER BY COALESCE(effective_at, created_at) ASC, id ASC
            """
            ,
            tuple(params),
        ).fetchall()

        return [_row_to_debt(r) for r in rows]
    
    def void_debt(self, debt_id: int, voided_at: str) -> Debt: #TODO todas las fechas como voided_at que no son opcionales deberian rellenarse aqui
        # Funcion para 'borrar' uan deuda pero sin eliminarla
        cur = self.conn.execute(
            """
            UPDATE debts
            SET status='VOIDED', voided_at=?
            WHERE id=? AND status!='VOIDED'
            """,
            (voided_at, debt_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"{DEBT_NOT_FOUND}: {debt_id}")

        return self.get_debt(debt_id, include_voided=True)
    
    def update_debt(self, debt_id: int, description: Optional[str] = None, effective_at: Optional[str] = None) -> Debt: #TODO el valor de la deuda podra cambiarse pero hay que ver quien recalcula las asignaciones y tal
        current = self.get_debt(debt_id, include_voided=True)
        if current.status == "VOIDED":
            raise KeyError(f"{DEBT_NOT_FOUND}: {debt_id}")

        new_description = current.description if description is None else description
        new_effective_at = current.effective_at if effective_at is None else effective_at

        self.conn.execute(
            """
            UPDATE debts
            SET description=?, effective_at=?
            WHERE id=? AND status!='VOIDED'
            """,
            (new_description, new_effective_at, debt_id),
        )

        return self.get_debt(debt_id, include_voided=True)
