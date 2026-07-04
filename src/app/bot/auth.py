from __future__ import annotations

from typing import FrozenSet, Optional


def is_authorized(user_id: Optional[int], allowed_user_ids: FrozenSet[int]) -> bool:
    return user_id is not None and user_id in allowed_user_ids


def authorization_message(
    user_id: Optional[int],
    allowed_user_ids: FrozenSet[int],
    discover_user_id: bool,
) -> Optional[str]:
    if is_authorized(user_id, allowed_user_ids):
        return None

    if discover_user_id and user_id is not None:
        return (
            f"Tu Telegram user id es {user_id}.\n"
            "Ponlo en ALLOWED_TELEGRAM_USER_IDS y vuelve a arrancarme con DISCOVER_TELEGRAM_USER_ID=0."
        )

    return "No estas autorizado para usar este bot."
