#!/usr/bin/env python3
from types import TracebackType
from typing import Optional, Set, Type
from uuid import uuid4

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import CallbackContext


class ErrorHandler:
    whitelist: Optional[Set[int]]

    def __init__(self, whitelist: Optional[Set[int]]) -> None:
        self.whitelist = whitelist

    def __enter__(self):
        return self

    def close(self) -> None:
        return

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        return self.close()

    async def error_handler(self, update: object, context: CallbackContext) -> None:
        """Handles errors for the bot"""
        if context.error is None:
            raise ValueError("Expected context.error to have value.")

        if isinstance(update, Update):
            exception_sting: str = (
                f"{type(context.error).__qualname__}: {context.error!s}"
            )

            if (update.message is not None) and (
                (self.whitelist is None)
                or (
                    (update.message.from_user is not None)
                    and (update.message.from_user.id in self.whitelist)
                )
            ):
                await update.message.reply_text(exception_sting, quote=True)

            if (update.inline_query is not None) and (
                (self.whitelist is None)
                or (update.inline_query.from_user.id in self.whitelist)
            ):
                await update.inline_query.answer(
                    [
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title="Exception",
                            description=exception_sting,
                            input_message_content=InputTextMessageContent(
                                exception_sting
                            ),
                        )
                    ],
                    cache_time=300,
                    is_personal=True,
                )

        raise context.error
