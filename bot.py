#!/usr/bin/env python3
import logging
import os

from typing import Callable

from telegram import (
    InlineQueryResultArticle,
    ParseMode,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackContext,
)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Runs TG bot")
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Enabled Debugging mode",
    )
    if (sys.version_info[0] >= 3) and (sys.version_info[1] >= 9):
        parser.add_argument(
            "-r",
            "--rich",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Enables rich output",
        )
    else:
        parser.add_argument(
            "-r",
            "--rich",
            action="store_true",
            default=True,
            help="Enables rich output",
        )
        parser.add_argument(
            "--no-rich",
            action="store_false",
            dest="rich",
            help="Disables rich output",
        )
    do_rich = parser.parse_args().rich
    debug = parser.parse_args().debug

if do_rich:
    try:
        import rich
        from rich.progress import track, Progress
        from rich.logging import RichHandler
    except ModuleNotFoundError:
        do_rich = False

logging_args = {
    "level": logging.DEBUG if debug else logging.INFO,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}
if do_rich:
    logging_args["handlers"] = [RichHandler(rich_tracebacks=True)]
logging.basicConfig(**logging_args)


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao")


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id=1,
            #            title="",
            description="description",
            input_message_content="content",
        ),
    ]

    update.inline_query.answer(results, cache_time=30)


def main() -> None:
    token = os.environ["TG_TOKEN"]
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
