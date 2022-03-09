#!/usr/bin/env python3
import logging
import os
import instaloader
from uuid import uuid4

from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
    ParseMode,
    InputTextMessageContent,
    Update,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import (
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
)

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Runs TG bot")
    parser.add_argument(
        "-t",
        "--token",
        action="store",
        default=os.environ["TG_TOKEN"] if "TG_TOKEN" in os.environ else None,
        type=str,
        dest="token",
        help="Telegram Token for the bot",
    )
    parser.add_argument(
        "--uid",
        action="append",
        dest="uid",
        type=int,
        help="Telegram User IDs authorized to use this bot",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enabled Debugging mode",
    )
    parser.add_argument(
        "--no-rich",
        action="store_false",
        dest="rich",
        help="Disables rich output",
    )
    parser.add_argument(
        "--no-login",
        action="store_false",
        dest="login",
        help="Runs without an Instagram account",
    )
    parser.add_argument(
        "--log-file",
        action="store_true",
        dest="logfile",
        help="Output to log file",
    )

    do_rich = True
    if parser.parse_args().rich:
        try:
            import rich
            from rich.progress import track, Progress
            from rich.logging import RichHandler
        except ModuleNotFoundError:
            do_rich = False
    else:
        do_rich = False

    if do_rich:
        logging_handlers = [RichHandler(rich_tracebacks=True)]
    else:
        logging_handlers = [logging.StreamHandler()]

    if parser.parse_args().logfile:
        logging_handlers.append(logging.FileHandler("IgTgBot.log"))

    logging.basicConfig(
        level=logging.DEBUG if parser.parse_args().debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=logging_handlers,
    )

    if parser.parse_args().uid is None:
        authorized_users = set()
        logging.info("No authorized users specified")
    else:
        authorized_users = set(int(uid) for uid in parser.parse_args().uid)
        logging.info("Authorized users: " + str(authorized_users))

    L = instaloader.Instaloader()
    if parser.parse_args().login is not False:
        IG_user = input("Please type your Instagram username: ")
        try:
            L.load_session_from_file(username=IG_user)
        except FileNotFoundError:
            L.interactive_login(IG_user)
        L.save_session_to_file()

# def parse_for_shortcodes(text: str) -> list:
#    return


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao")


def inlinequery(update: Update, context: CallbackContext) -> None:
    logging.info(update.inline_query)
    if update.inline_query.from_user.id in authorized_users:
        results = []
        shortcode = update.inline_query.query
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        logging.info(post.typename)
        logging.info(post.mediacount)
        if post.typename == "GraphSidecar":
            counter = 0
            for x in post.get_sidecar_nodes():
                counter += 1
                if x.is_video is not True:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            title="",
                            description="description",
                            photo_url=x.display_url,
                            thumb_url=x.display_url,
                            caption="https://instagram.com/p/"
                            + shortcode
                            + " "
                            + str(counter)
                            + "/"
                            + str(post.mediacount)
                            + ("\n" + post.caption)
                            if post.caption
                            else "",
                        )
                    )
                    results.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title="URL",
                            description="URL",
                            photo_url=x.display_url,
                            thumb_url=x.display_url,
                            caption=x.display_url + ("\n" + post.caption)
                            if post.caption
                            else "",
                            input_message_content=InputTextMessageContent(
                                str(x.display_url)
                            ),
                        )
                    )
                else:
                    results.append(
                        InlineQueryResultVideo(
                            id=str(uuid4()),
                            title="",
                            description="description",
                            video_url=x.video_url,
                            thumb_url=x.video_url,
                            mime_type="video/mp4",
                            caption="https://instagram.com/p/"
                            + shortcode
                            + " "
                            + str(counter)
                            + "/"
                            + str(post.mediacount)
                            + ("\n" + post.caption)
                            if post.caption
                            else "",
                        )
                    )
                    results.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title="URL",
                            description="URL",
                            photo_url=x.video_url,
                            thumb_url=x.video_url,
                            caption=x.video_url + ("\n" + post.caption)
                            if post.caption
                            else "",
                            input_message_content=InputTextMessageContent(
                                str(x.video_url)
                            ),
                        )
                    )
        elif post.typename == "GraphImage":
            results.append(
                InlineQueryResultPhoto(
                    id=str(uuid4()),
                    title="",
                    description="description",
                    photo_url=post.url,
                    thumb_url=post.url,
                    caption="https://instagram.com/p/"
                    + shortcode
                    + (("\n" + post.caption) if post.caption else (""),)[0],
                )
            )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    description="URL",
                    photo_url=post.url,
                    thumb_url=post.url,
                    caption=post.url + ("\n" + post.caption) if post.caption else "",
                    input_message_content=InputTextMessageContent(str(post.url)),
                )
            )
        elif post.typename == "GraphVideo":
            logging.info(post.video_url)
            results.append(
                InlineQueryResultVideo(
                    id=str(uuid4()),
                    title="Video",
                    description="description",
                    video_url=post.video_url,
                    thumb_url=post.video_url,
                    mime_type="video/mp4",
                    caption="https://instagram.com/p/"
                    + shortcode
                    + ("\n" + post.caption)
                    if post.caption
                    else "",
                )
            )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    description="URL",
                    video_url=post.video_url,
                    thumb_url=post.video_url,
                    caption=post.video_url + ("\n" + post.caption)
                    if post.caption
                    else "",
                    input_message_content=InputTextMessageContent(str(post.video_url)),
                )
            )
    else:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Unauthorized user",
                description="Unauthorized user",
                input_message_content=InputTextMessageContent("Unauthorized user"),
            )
        ]

    update.inline_query.answer(results, cache_time=30)


def echo(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    logging.info(str(update.message))
    ig_post = True
    if update.message.from_user.id in authorized_users:
        shortcode = update.message.text
        if ig_post:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            logging.info(str(post))
            arguments = {
                "caption": "https://instagram.com/p/"
                + shortcode
                + "/"
                + (("\n" + post.caption) if post.caption else (""),)[0],
                "quote": True,
            }
            if post.typename == "GraphImage":
                update.message.reply_photo(photo=post.url, **arguments)
            elif post.typename == "GraphVideo":
                update.message.reply_video(video=post.video_url, **arguments)
            elif post.typename == "GraphSidecar":
                counter = 0
                media_group = []
                for x in post.get_sidecar_nodes():
                    counter += 1
                    caption = (
                        "https://instagram.com/p/"
                        + shortcode
                        + "/"
                        + " "
                        + str(counter)
                        + "/"
                        + str(post.mediacount)
                        + ("\n" + post.caption)
                        if post.caption
                        else ""
                    )
                    if x.is_video is not True:
                        media_group.append(
                            InputMediaPhoto(
                                media=x.display_url,
                                caption=caption,
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=x.video_url,
                                caption=caption,
                            )
                        )
                for y in media_group:
                    logging.info(y)
                update.message.reply_media_group(
                    media=media_group,
                    quote=True,
                )
        else:
            update.message.reply_text("Not an Instagram post", quote=True)
    else:
        update.message.reply_text("Unauthorized user", quote=True)


def main(token: str) -> None:
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":

    main(parser.parse_args().token)
