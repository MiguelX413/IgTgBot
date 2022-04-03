#!/usr/bin/env python3
import logging
import os
from typing import List, Union, Set
from uuid import uuid4

from instaloader import Instaloader
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
    InlineQueryResult,
    InputTextMessageContent,
    Update,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, CallbackContext

from structures import PatchedPost, Pairs

if __name__ == "__main__":
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Runs TG bot")
    if "TG_TOKEN" not in os.environ:
        parser.add_argument(
            "token",
            action="store",
            type=str,
            help="Telegram Token for the bot",
        )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--uid",
        action="append",
        dest="uid",
        metavar="Telegram User ID",
        type=int,
        help="Telegram User IDs authorized to use this bot",
    )
    group.add_argument(
        "--no-whitelist",
        action="store_false",
        dest="whitelisttoggle",
        help="Allow all Telegram Users to use this bot (This could cause rate limiting by Meta)",
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
        help="Runs without an Instagram account (Not recommended, quickly limited)",
    )
    parser.add_argument(
        "--user",
        action="store",
        dest="iguser",
        metavar="Instagram User",
        type=str,
        help="Username through which Instaloader is ran",
    )
    parser.add_argument(
        "--log-file",
        action="store_true",
        dest="logfile",
        help="Output to log file",
    )
    args = parser.parse_args()

    do_rich = True
    if args.rich:
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

    if args.logfile:
        logging_handlers.append(logging.FileHandler("IgTgBot.log"))

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=logging_handlers,
    )

    logging.info(str(args))
    logging.info("do_rich: " + str(do_rich))

    whitelist: Set[int] = set()
    if args.uid is None:
        logging.info("No authorized users specified")
    else:
        whitelist.update(args.uid)
        logging.info(f"Authorized users: {str(whitelist)}")

    L = Instaloader()
    if args.login is not False:
        IG_user: str = (
            args.iguser
            if args.iguser is not None
            else input("Please type your Instagram username: ")
        )
        try:
            L.load_session_from_file(username=IG_user)
        except FileNotFoundError:
            L.interactive_login(IG_user)
        L.save_session_to_file()


# def parse_for_shortcodes(text: str) -> list:
#    return


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao", quote=True)


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Produces results for Inline Queries"""
    logging.info(update.inline_query)
    if (update.inline_query.from_user.id in whitelist) or (
        args.whitelisttoggle is False
    ):
        results: List[InlineQueryResult] = []
        shortcode: str = update.inline_query.query
        post: PatchedPost = PatchedPost.from_shortcode(L.context, shortcode)
        logging.info(post.typename)
        logging.info(post.mediacount)
        if post.typename == "GraphSidecar":
            counter: int = 0
            pairs = Pairs(post)
            for node in post.get_sidecar_nodes():
                short = pairs.short(counter)
                if node.is_video is not True:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=node.display_url,
                            thumb_url=node.display_url,
                            title="Photo",
                            caption=short.caption,
                            caption_entities=short.entities,
                        )
                    )

                else:
                    results.append(
                        InlineQueryResultVideo(
                            id=str(uuid4()),
                            video_url=node.video_url,
                            mime_type="video/mp4",
                            thumb_url=node.display_url,
                            title="Video",
                            caption=short.caption,
                            caption_entities=short.entities,
                        )
                    )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="URL",
                        input_message_content=InputTextMessageContent(
                            short.caption,
                            entities=short.entities,
                        ),
                        thumb_url=node.display_url,
                    )
                )
                counter += 1

        elif post.typename in ("GraphImage", "GraphVideo"):
            pairs = Pairs(post)
            short = pairs.short()
            if post.typename == "GraphImage":
                results.append(
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        title="Photo",
                        photo_url=post.url,
                        thumb_url=post.url,
                        caption=short.caption,
                        caption_entities=short.entities,
                    )
                )

            elif post.typename == "GraphVideo":
                results.append(
                    InlineQueryResultVideo(
                        id=str(uuid4()),
                        title="Video",
                        video_url=post.video_url,
                        thumb_url=post.url,
                        mime_type="video/mp4",
                        caption=short.caption,
                        caption_entities=short.entities,
                    )
                )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    input_message_content=InputTextMessageContent(
                        short.caption,
                        entities=short.entities,
                    ),
                    thumb_url=post.url,
                )
            )
        update.inline_query.answer(results, cache_time=21600, is_personal=False)

    else:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Unauthorized user",
                input_message_content=InputTextMessageContent("Unauthorized user"),
            )
        ]
        update.inline_query.answer(results, cache_time=300)


def posts(update: Update, context: CallbackContext) -> None:
    """Replies to messages in DMs."""
    logging.info(str(update.message))
    ig_post: bool = True
    if (update.message.from_user.id in whitelist) or (args.whitelisttoggle is False):
        if len(context.args) >= 1:
            shortcode: str = context.args[0]
            if ig_post:
                post: PatchedPost = PatchedPost.from_shortcode(L.context, shortcode)
                logging.info(str(post))

                if post.typename == "GraphSidecar":
                    pairs = Pairs(post)
                    counter: int = 0
                    media_group: List[Union[InputMediaPhoto, InputMediaVideo]] = []
                    for node in post.get_sidecar_nodes():
                        short = pairs.short(counter)
                        if node.is_video is not True:
                            media_group.append(
                                InputMediaPhoto(
                                    media=node.display_url,
                                    caption=short.caption,
                                    caption_entities=short.entities,
                                )
                            )
                        else:
                            media_group.append(
                                InputMediaVideo(
                                    media=node.video_url,
                                    caption=short.caption,
                                    caption_entities=short.entities,
                                )
                            )
                        counter += 1
                    for input_medium in media_group:
                        logging.info(input_medium)
                    first_reply = update.message.reply_media_group(
                        media=media_group,
                        quote=True,
                    )

                    if len(pairs.long(0).caption) > 1024:
                        long = pairs.long()
                        first_reply[post.mediacount - 1].reply_text(
                            long.caption, entities=long.entities, quote=True
                        )

                elif post.typename in ("GraphImage", "GraphVideo"):
                    pairs = Pairs(post)
                    short = pairs.short()
                    if post.typename == "GraphImage":
                        first_reply = update.message.reply_photo(
                            photo=post.url,
                            quote=True,
                            caption=short.caption,
                            caption_entities=short.entities,
                        )

                    elif post.typename == "GraphVideo":
                        first_reply = update.message.reply_video(
                            video=post.video_url,
                            quote=True,
                            caption=short.caption,
                            caption_entities=short.entities,
                        )
                    long = pairs.long()
                    if len(long.caption) > 1024:
                        first_reply.reply_text(
                            long.caption, entities=long.entities, quote=True
                        )
            else:
                update.message.reply_text("Not an Instagram post", quote=True)
    else:
        update.message.reply_text("Unauthorized user", quote=True)


def main(token: str) -> None:
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("p", posts))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main(args.token)
