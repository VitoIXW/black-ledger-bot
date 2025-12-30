from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Person:
    id: int
    full_name: str
    alias: Optional[str]
    is_deleted: bool
    deleted_at: Optional[str]
    created_at: str


@dataclass(frozen=True)
class Debt:
    id: int
    person_id: int
    original_amount_eur: int  # cents
    description: Optional[str]
    status: str  # OPEN / PAID / VOIDED
    created_at: str
    effective_at: Optional[str]
    voided_at: Optional[str]


@dataclass(frozen=True)
class Payment:
    id: int
    person_id: int
    amount_eur: int  # cents
    method: Optional[str]
    description: Optional[str]
    status: str  # POSTED / VOIDED
    created_at: str
    effective_at: Optional[str]