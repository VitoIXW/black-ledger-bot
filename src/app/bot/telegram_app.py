from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import FrozenSet, Iterator, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.auth import authorization_message
from app.bot.flow import ChatState, View, handle_action, handle_text, start_view
from app.db.connection import DbConfig, connect
from app.db.schema import create_schema


def build_application(
    token: str,
    db_path: str,
    allowed_user_ids: FrozenSet[int],
    discover_user_id: bool = False,
) -> Application:
    application = ApplicationBuilder().token(token).build()
    application.bot_data["db_path"] = db_path
    application.bot_data["allowed_user_ids"] = allowed_user_ids
    application.bot_data["discover_user_id"] = discover_user_id

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    auth_message = _authorization_message(update, context)
    if auth_message is not None:
        if update.message is not None:
            await update.message.reply_text(auth_message, reply_markup=ReplyKeyboardRemove())
        return

    with _db(context) as conn:
        view = start_view(conn, _chat_state(context))

    if update.message is not None:
        await update.message.reply_text("Limpio el teclado antiguo.", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(view.text, reply_markup=_markup(view))


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    auth_message = _authorization_message(update, context)
    if auth_message is not None:
        if query.message is not None:
            await query.message.edit_text(auth_message)
        return

    action = query.data or "home"

    with _db(context) as conn:
        view = handle_action(conn, _chat_state(context), action)

    if query.message is not None:
        await query.message.edit_text(view.text, reply_markup=_markup(view))


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return

    auth_message = _authorization_message(update, context)
    if auth_message is not None:
        await update.message.reply_text(auth_message, reply_markup=ReplyKeyboardRemove())
        return

    with _db(context) as conn:
        view = handle_text(conn, _chat_state(context), update.message.text)

    await update.message.reply_text(view.text, reply_markup=_markup(view))


def init_database(db_path: str) -> None:
    with connect(DbConfig(db_path)) as conn:
        create_schema(conn)
        conn.commit()


def _authorization_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    allowed_user_ids = context.application.bot_data.get("allowed_user_ids", frozenset())
    discover_user_id = bool(context.application.bot_data.get("discover_user_id", False))
    return authorization_message(_telegram_user_id(update), allowed_user_ids, discover_user_id)


def _markup(view: View) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(button.label, callback_data=button.action) for button in row]
            for row in view.buttons
        ]
    )


def _chat_state(context: ContextTypes.DEFAULT_TYPE) -> ChatState:
    state = context.user_data.setdefault("ledger_state", {})
    return state


def _telegram_user_id(update: Update) -> Optional[int]:
    if update.effective_user is None:
        return None
    return update.effective_user.id


@contextmanager
def _db(context: ContextTypes.DEFAULT_TYPE) -> Iterator[sqlite3.Connection]:
    db_path = str(context.application.bot_data["db_path"])
    conn = connect(DbConfig(db_path))
    create_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
