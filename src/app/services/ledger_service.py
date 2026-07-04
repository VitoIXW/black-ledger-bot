from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.db.allocation_repo import AllocationRepo
from app.db.debt_repo import DebtRepo
from app.db.payment_repo import PaymentRepo
from app.domain.models import (
    Allocation,
    Debt,
    LedgerEvent,
    Payment,
    PendingDebt,
    PersonBalance,
    UnappliedPayment,
)
from app.domain.time import now_utc_iso


@dataclass(frozen=True)
class RecordPaymentResult:
    payment: Payment
    allocations: List[Allocation]
    unapplied_amount_eur: int


@dataclass(frozen=True)
class LedgerService:
    conn: sqlite3.Connection
    now_fn: Callable[[], str] = now_utc_iso
    debts: DebtRepo = field(init=False)
    payments: PaymentRepo = field(init=False)
    allocations: AllocationRepo = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "debts", DebtRepo(self.conn, now_fn=self.now_fn))
        object.__setattr__(self, "payments", PaymentRepo(self.conn, now_fn=self.now_fn))
        object.__setattr__(self, "allocations", AllocationRepo(self.conn, now_fn=self.now_fn))

    def record_payment_and_allocate(
        self,
        person_id: int,
        amount_eur_cents: int,
        method: Optional[str] = None,
        description: Optional[str] = None,
        effective_at: Optional[str] = None,
    ) -> RecordPaymentResult:
        payment = self.payments.record_payment(
            person_id=person_id,
            amount_eur_cents=amount_eur_cents,
            method=method,
            description=description,
            effective_at=effective_at,
        )

        remaining_payment = payment.amount_eur
        new_allocations: List[Allocation] = []

        for debt in self.debts.list_debts(person_id=person_id, status="OPEN"):
            if remaining_payment <= 0:
                break

            remaining_debt = self.remaining_amount_for_debt(debt.id)
            if remaining_debt <= 0:
                self._refresh_debt_status(debt.id)
                continue

            amount_to_allocate = min(remaining_payment, remaining_debt)
            allocation = self.allocations.add_allocation(
                payment_id=payment.id,
                debt_id=debt.id,
                amount_eur_cents=amount_to_allocate,
            )
            new_allocations.append(allocation)
            remaining_payment -= amount_to_allocate
            self._refresh_debt_status(debt.id)

        return RecordPaymentResult(
            payment=payment,
            allocations=new_allocations,
            unapplied_amount_eur=remaining_payment,
        )

    def remaining_amount_for_debt(self, debt_id: int) -> int:
        debt = self.debts.get_debt(debt_id)
        paid = self.allocations.applied_amount_for_debt(debt.id)
        return max(debt.original_amount_eur - paid, 0)

    def unapplied_amount_for_payment(self, payment_id: int) -> int:
        payment = self.payments.get_payment(payment_id)
        applied = self.allocations.applied_amount_for_payment(payment.id)
        return max(payment.amount_eur - applied, 0)

    def get_pending_debts(self, person_id: int) -> List[PendingDebt]:
        pending: List[PendingDebt] = []
        debts = self.debts.list_debts(person_id=person_id)
        for debt in debts:
            if debt.status == "VOIDED":
                continue

            paid = self.allocations.applied_amount_for_debt(debt.id)
            remaining = max(debt.original_amount_eur - paid, 0)
            if remaining > 0:
                pending.append(
                    PendingDebt(
                        debt=debt,
                        paid_amount_eur=paid,
                        remaining_amount_eur=remaining,
                    )
                )
        return pending

    def get_unapplied_payments(self, person_id: int) -> List[UnappliedPayment]:
        unapplied: List[UnappliedPayment] = []
        payments = self.payments.list_payments(person_id=person_id)
        for payment in payments:
            applied = self.allocations.applied_amount_for_payment(payment.id)
            remaining = max(payment.amount_eur - applied, 0)
            if remaining > 0:
                unapplied.append(
                    UnappliedPayment(
                        payment=payment,
                        applied_amount_eur=applied,
                        remaining_amount_eur=remaining,
                    )
                )
        return unapplied

    def get_person_balance(self, person_id: int) -> PersonBalance:
        debt_total = 0
        paid_total = 0

        for debt in self.debts.list_debts(person_id=person_id):
            if debt.status == "VOIDED":
                continue

            debt_total += debt.original_amount_eur
            paid_total += self.allocations.applied_amount_for_debt(debt.id)

        return PersonBalance(
            person_id=person_id,
            debt_total_eur=debt_total,
            paid_total_eur=paid_total,
            balance_eur=debt_total - paid_total,
        )

    def get_person_history(self, person_id: int) -> List[LedgerEvent]:
        events: List[LedgerEvent] = []

        for debt in self.debts.list_debts(person_id=person_id, include_voided=True):
            events.append(
                LedgerEvent(
                    kind="DEBT",
                    happened_at=debt.effective_at if debt.effective_at is not None else debt.created_at,
                    amount_eur=debt.original_amount_eur,
                    description=debt.description,
                    status=debt.status,
                )
            )

        for payment in self.payments.list_payments(person_id=person_id, include_voided=True):
            events.append(
                LedgerEvent(
                    kind="PAYMENT",
                    happened_at=payment.effective_at,
                    amount_eur=payment.amount_eur,
                    description=payment.description,
                    status=payment.status,
                )
            )

        return sorted(events, key=lambda event: (event.happened_at, event.kind, event.amount_eur))

    def void_payment(self, payment_id: int, voided_at: Optional[str] = None) -> Payment:
        self.payments.get_payment(payment_id)
        touched_allocations = self.allocations.void_for_payment(payment_id)
        payment = self.payments.void_payment(payment_id, voided_at or self.now_fn())
        for allocation in touched_allocations:
            self._refresh_debt_status(allocation.debt_id)
        return payment

    def void_debt(self, debt_id: int, voided_at: Optional[str] = None) -> Debt:
        self.debts.get_debt(debt_id)
        self.allocations.void_for_debt(debt_id)
        return self.debts.void_debt(debt_id, voided_at or self.now_fn())

    def _refresh_debt_status(self, debt_id: int) -> None:
        debt = self.debts.get_debt(debt_id, include_voided=True)
        if debt.status == "VOIDED":
            return

        paid = self.allocations.applied_amount_for_debt(debt.id)
        new_status = "PAID" if paid >= debt.original_amount_eur else "OPEN"
        self.conn.execute(
            """
            UPDATE debts
            SET status=?
            WHERE id=? AND status!='VOIDED'
            """,
            (new_status, debt.id),
        )
