from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EurCents:
    value: int

    @staticmethod
    def from_eur(amount: float) -> "EurCents":
        return EurCents(int(round(amount * 100)))

    def to_eur_str(self) -> str:
        return f"{self.value/100:.2f} €"
