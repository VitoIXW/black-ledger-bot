from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable, Final, List, Optional

from app.domain.models import Allocation
from app.domain.time import now_utc_iso

ALLOCATION_NOT_FOUND: Final[str] = "Allocation not found"


def _row_to_allocation(row: sqlite3.Row) -> Allocation:
    return Allocation(
        id=int(row["id"]),
        payment_id=int(row["payment_id"]),
        debt_id=int(row["debt_id"]),
        allocated_amount_eur=int(row["allocated_amount_eur"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
    )


@dataclass(frozen=True)
class AllocationRepo:
    conn: sqlite3.Connection
    now_fn: Callable[[], str] = now_utc_iso

    def add_allocation(self, payment_id: int, debt_id: int, amount_eur_cents: int) -> Allocation:
        if amount_eur_cents <= 0:
            raise ValueError("amount_eur_cents must be > 0")

        payment = self.conn.execute(
            "SELECT id FROM payments WHERE id=? AND status='POSTED'",
            (payment_id,),
        ).fetchone()
        if payment is None:
            raise KeyError(f"Payment not found: {payment_id}")

        debt = self.conn.execute(
            "SELECT id FROM debts WHERE id=? AND status!='VOIDED'",
            (debt_id,),
        ).fetchone()
        if debt is None:
            raise KeyError(f"Debt not found: {debt_id}")

        cur = self.conn.execute(
            """
            INSERT INTO allocations(payment_id, debt_id, allocated_amount_eur, status, created_at)
            VALUES (?, ?, ?, 'APPLIED', ?)
            """,
            (payment_id, debt_id, amount_eur_cents, self.now_fn()),
        )
        allocation_id = int(cur.lastrowid)

        row = self.conn.execute(
            "SELECT * FROM allocations WHERE id=?",
            (allocation_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Insert allocation succeeded but row not found (unexpected).")

        return _row_to_allocation(row)

    def get_allocation(self, allocation_id: int, include_voided: bool = False) -> Allocation:
        if include_voided:
            row = self.conn.execute(
                "SELECT * FROM allocations WHERE id=?",
                (allocation_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM allocations WHERE id=? AND status='APPLIED'",
                (allocation_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"{ALLOCATION_NOT_FOUND}: {allocation_id}")

        return _row_to_allocation(row)

    def list_allocations(
        self,
        payment_id: Optional[int] = None,
        debt_id: Optional[int] = None,
        include_voided: bool = False,
    ) -> List[Allocation]:
        conditions: List[str] = []
        params: List[object] = []

        if payment_id is not None:
            conditions.append("payment_id=?")
            params.append(payment_id)

        if debt_id is not None:
            conditions.append("debt_id=?")
            params.append(debt_id)

        if not include_voided:
            conditions.append("status='APPLIED'")

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        rows = self.conn.execute(
            f"""
            SELECT * FROM allocations
            {where_sql}
            ORDER BY created_at ASC, id ASC
            """,
            tuple(params),
        ).fetchall()

        return [_row_to_allocation(row) for row in rows]

    def applied_amount_for_debt(self, debt_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(allocated_amount_eur), 0) AS amount
            FROM allocations
            WHERE debt_id=? AND status='APPLIED'
            """,
            (debt_id,),
        ).fetchone()
        return int(row["amount"])

    def applied_amount_for_payment(self, payment_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(allocated_amount_eur), 0) AS amount
            FROM allocations
            WHERE payment_id=? AND status='APPLIED'
            """,
            (payment_id,),
        ).fetchone()
        return int(row["amount"])

    def void_for_payment(self, payment_id: int) -> List[Allocation]:
        allocations = self.list_allocations(payment_id=payment_id)
        self.conn.execute(
            """
            UPDATE allocations
            SET status='VOIDED'
            WHERE payment_id=? AND status='APPLIED'
            """,
            (payment_id,),
        )
        return allocations

    def void_for_debt(self, debt_id: int) -> List[Allocation]:
        allocations = self.list_allocations(debt_id=debt_id)
        self.conn.execute(
            """
            UPDATE allocations
            SET status='VOIDED'
            WHERE debt_id=? AND status='APPLIED'
            """,
            (debt_id,),
        )
        return allocations
