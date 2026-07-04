from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import FrozenSet, Iterator, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
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
        await _delete_incoming_message(update)
        await _show_text_panel(update, context, auth_message)
        return

    with _db(context) as conn:
        view = start_view(conn, _chat_state(context))

    await _delete_incoming_message(update)
    await _show_panel(update, context, view)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await query.answer()
    if query.message is not None:
        context.user_data["ledger_panel_chat_id"] = query.message.chat_id
        context.user_data["ledger_panel_message_id"] = query.message.message_id

    auth_message = _authorization_message(update, context)
    if auth_message is not None:
        await _show_text_panel(update, context, auth_message)
        return

    action = query.data or "home"

    with _db(context) as conn:
        view = handle_action(conn, _chat_state(context), action)

    await _show_panel(update, context, view)


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return

    auth_message = _authorization_message(update, context)
    if auth_message is not None:
        await _delete_incoming_message(update)
        await _show_text_panel(update, context, auth_message)
        return

    with _db(context) as conn:
        view = handle_text(conn, _chat_state(context), update.message.text)

    await _delete_incoming_message(update)
    await _show_panel(update, context, view)


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


async def _show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, view: View) -> None:
    await _show_text_panel(update, context, view.text, _markup(view))


async def _show_text_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    chat_id = _chat_id(update)
    if chat_id is None:
        return

    panel_message_id = context.user_data.get("ledger_panel_message_id")
    if panel_message_id is not None:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(panel_message_id),
                text=text,
                reply_markup=reply_markup,
            )
            context.user_data["ledger_panel_chat_id"] = chat_id
            return
        except TelegramError:
            context.user_data.pop("ledger_panel_message_id", None)
            context.user_data.pop("ledger_panel_chat_id", None)

    message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    context.user_data["ledger_panel_chat_id"] = chat_id
    context.user_data["ledger_panel_message_id"] = message.message_id


async def _delete_incoming_message(update: Update) -> None:
    if update.message is None:
        return
    try:
        await update.message.delete()
    except TelegramError:
        return


def _chat_state(context: ContextTypes.DEFAULT_TYPE) -> ChatState:
    state = context.user_data.setdefault("ledger_state", {})
    return state


def _chat_id(update: Update) -> Optional[int]:
    if update.effective_chat is None:
        return None
    return update.effective_chat.id


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
