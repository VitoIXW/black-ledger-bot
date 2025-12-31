from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Final, List, Callable

from app.domain.models import Payment
from app.domain.time import now_utc_iso

PAYMENT_NOT_FOUND: Final[str] = "Payment not found"


def _row_to_payment(row: sqlite3.Row) -> Payment:
    return Payment(
        id=int(row["id"]),
        person_id=int(row["person_id"]),
        amount_eur=int(row["amount_eur"]),
        method=str(row["method"]) if row["method"] is not None else None,
        description=str(row["description"]) if row["description"] is not None else None,
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        effective_at=str(row["effective_at"]),
        voided_at=str(row["voided_at"]) if row["voided_at"] is not None else None,
    )


@dataclass(frozen=True)
class PaymentRepo:
    conn: sqlite3.Connection
    now_fn: Callable[[], str] = now_utc_iso

    def record_payment(self, person_id: int, amount_eur_cents: int, method: Optional[str] = None, description: Optional[str] = None, effective_at: Optional[str] = None) -> Payment:
        if amount_eur_cents <= 0:
            raise ValueError("amount_eur_cents must be > 0")
        
        created_at = self.now_fn()

        effective_at_final = effective_at if effective_at is not None else created_at

        row = self.conn.execute(
            "SELECT id FROM people WHERE id=? AND is_deleted=0",
            (person_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Person not found: {person_id}")

        cur = self.conn.execute(
            """
            INSERT INTO payments(
                person_id,
                amount_eur,
                method,
                description,
                status,
                created_at,
                effective_at,
                voided_at
            )
            VALUES (?, ?, ?, ?, 'POSTED', ?, ?, NULL)
            """,
            (person_id, amount_eur_cents, method, description, created_at, effective_at_final),
        )
        payment_id = int(cur.lastrowid)

        row2 = self.conn.execute(
            "SELECT * FROM payments WHERE id=?",
            (payment_id,),
        ).fetchone()
        if row2 is None:
            raise RuntimeError("Insert payment succeeded but row not found (unexpected).")

        return _row_to_payment(row2)
    
    def get_payment(self, payment_id: int, include_voided: bool = False) -> Payment:
        if include_voided:
            row = self.conn.execute(
                "SELECT * FROM payments WHERE id=?",
                (payment_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM payments WHERE id=? AND status!='VOIDED'",
                (payment_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"{PAYMENT_NOT_FOUND}: {payment_id}")

        return _row_to_payment(row)
    
    def list_payments(self, person_id: Optional[int] = None, include_voided: bool = False) -> List[Payment]:
        conditions: List[str] = []
        params: List[object] = []

        if person_id is not None:
            conditions.append("person_id=?")
            params.append(person_id)

        if not include_voided:
            conditions.append("status!='VOIDED'")

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(
            f"""
            SELECT * FROM payments
            {where_sql}
            ORDER BY effective_at ASC, id ASC
            """,
            tuple(params),
        ).fetchall()

        return [_row_to_payment(r) for r in rows]
    
    def void_payment(self, payment_id: int, voided_at: str) -> Payment:
        cur = self.conn.execute(
            """
            UPDATE payments
            SET status='VOIDED', voided_at=?
            WHERE id=? AND status!='VOIDED'
            """,
            (voided_at, payment_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"{PAYMENT_NOT_FOUND}: {payment_id}")

        return self.get_payment(payment_id, include_voided=True)

    def update_payment(self, payment_id: int, method: Optional[str] = None, description: Optional[str] = None, effective_at: Optional[str] = None) -> Payment:
        current = self.get_payment(payment_id, include_voided=True)
        if current.status == "VOIDED":
            raise KeyError(f"{PAYMENT_NOT_FOUND}: {payment_id}")

        new_method = current.method if method is None else method
        new_description = current.description if description is None else description
        new_effective_at = current.effective_at if effective_at is None else effective_at

        self.conn.execute(
            """
            UPDATE payments
            SET method=?, description=?, effective_at=?
            WHERE id=? AND status!='VOIDED'
            """,
            (new_method, new_description, new_effective_at, payment_id),
        )

        return self.get_payment(payment_id, include_voided=True)
