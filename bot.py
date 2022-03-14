#!/usr/bin/env python3
import logging
import os
import instaloader
from uuid import uuid4

import telegram
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
from telegram.ext import (
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
)
from typing import NamedTuple, List, Union, Dict, Set


class Pair(NamedTuple):
    caption: str = ""
    entities: List[telegram.MessageEntity] = []


if __name__ == "__main__":
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Runs TG bot")
    parser.add_argument(
        "token",
        action="store",
        default=os.environ["TG_TOKEN"] if "TG_TOKEN" in os.environ else None,
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
        logging.info("Authorized users: " + str(whitelist))

    L = instaloader.Instaloader()
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


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


emojis: Dict[str, str] = {
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


def pair_gen(
    input_post: instaloader.Post,
    counter: int = None,
) -> Pair:

    # Initializing
    caption: str = ""
    entities: list[telegram.MessageEntity] = []

    # Media URL
    if counter is None:
        if input_post.typename == "GraphVideo":
            media_url = input_post.video_url
        else:
            media_url = input_post.url
    else:
        node = list(input_post.get_sidecar_nodes(counter, counter))[0]
        if node.is_video:
            media_url = node.video_url
        else:
            media_url = node.display_url
    entities.append(
        telegram.MessageEntity(
            type="text_link",
            offset=utf16len(caption),
            length=utf16len("Media"),
            url=media_url,
        )
    )
    caption += "Media\n"

    # Posting account and Counter
    entities.append(
        telegram.MessageEntity(
            type="text_link",
            offset=utf16len(caption),
            length=utf16len("@" + input_post.owner_username),
            url="https://instagram.com/" + input_post.owner_username + "/",
        )
    )
    caption += (
        "@"
        + input_post.owner_username
        + " ("
        + str(input_post.owner_id)
        + ")"
        + ": "
        + "https://instagram.com/p/"
        + input_post.shortcode
        + "/"
        + (
            (" " + str(counter + 1) + "/" + str(input_post.mediacount) + "\n")
            if counter is not None
            else "\n"
        )
    )

    # Sponsor(s)
    if input_post.is_sponsored:
        caption += "Sponsors: "
        for sponsor_user in input_post.sponsor_users:
            entities.append(
                telegram.MessageEntity(
                    type="text_link",
                    offset=utf16len(caption),
                    length=utf16len("@" + sponsor_user.username),
                    url="https://instagram.com/" + sponsor_user.username + "/",
                )
            )
            caption += (
                "@" + sponsor_user.username + " (" + str(sponsor_user.userid) + ") "
            )
        caption += "\n"

    # Location
    if input_post.location is not None:
        entities.append(
            telegram.MessageEntity(
                type="text_link",
                offset=utf16len(caption + emojis["location"]),
                length=utf16len(str(input_post.location.name)),
                url="https://www.instagram.com/explore/locations/"
                + str(input_post.location.id)
                + "/",
            )
        )
        caption += emojis["location"] + str(input_post.location.name) + "\n"

    # Views, Likes, and Comments
    if input_post.is_video:
        caption += (emojis["eyes"] + str(input_post.video_view_count) + " ")
    entities.append(
        telegram.MessageEntity(
            type="text_link",
            offset=utf16len(caption + emojis["heart"]),
            length=utf16len(str(input_post.likes)),
            url="https://www.instagram.com/p/" + input_post.shortcode + "/liked_by/",
        )
    )
    caption += (
        emojis["heart"]
        + str(input_post.likes)
        + " "
        + emojis["comments"]
        + str(input_post.comments)
        + "\n"
    )

    # Date
    caption += emojis["calendar"] + f"{input_post.date_utc:%Y-%m-%d %H:%M:%S}" + "\n"

    # Post Caption
    if input_post.caption is not None:
        caption += input_post.caption

    return Pair(caption, entities)


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao")


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Produces results for Inline Queries"""
    logging.info(update.inline_query)
    if (update.inline_query.from_user.id in whitelist) or (
        args.whitelisttoggle is False
    ):
        results: list[InlineQueryResult] = []
        shortcode: str = update.inline_query.query
        post: instaloader.Post = instaloader.Post.from_shortcode(L.context, shortcode)
        logging.info(post.typename)
        logging.info(post.mediacount)
        if post.typename == "GraphSidecar":
            counter: int = 0
            for node in post.get_sidecar_nodes():
                pair = pair_gen(post, counter)
                if node.is_video is not True:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=node.display_url,
                            thumb_url=node.display_url,
                            title="",
                            caption=pair.caption,
                            caption_entities=pair.entities,
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
                            caption=pair.caption,
                            caption_entities=pair.entities,
                        )
                    )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="URL",
                        input_message_content=InputTextMessageContent(
                            pair.caption,
                            entities=pair.entities,
                        ),
                        thumb_url=node.display_url,
                    )
                )
                counter += 1

        elif post.typename in ("GraphImage", "GraphVideo"):
            pair = pair_gen(post)
            if post.typename == "Graphimage":
                results.append(
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        title="",
                        photo_url=post.url,
                        thumb_url=post.url,
                        caption=pair.caption,
                        caption_entities=pair.entities,
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
                        caption=pair.caption,
                        caption_entities=pair.entities,
                    )
                )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    input_message_content=InputTextMessageContent(
                        pair.caption,
                        entities=pair.entities,
                    ),
                    thumb_url=post.url,
                )
            )

    else:
        results = [
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Unauthorized user",
                input_message_content=InputTextMessageContent("Unauthorized user"),
            )
        ]

    update.inline_query.answer(results, cache_time=30)


def reply(update: Update, context: CallbackContext) -> None:
    """Replies to messages in DMs."""
    logging.info(str(update.message))
    ig_post: bool = True
    if (update.message.from_user.id in whitelist) or (args.whitelisttoggle is False):
        shortcode = update.message.text
        if ig_post:
            post: instaloader.Post = instaloader.Post.from_shortcode(
                L.context, shortcode
            )
            logging.info(str(post))

            if post.typename == "GraphSidecar":
                counter: int = 0
                media_group: list[Union[InputMediaPhoto, InputMediaVideo]] = []
                for node in post.get_sidecar_nodes():
                    pair = pair_gen(post, counter)
                    if node.is_video is not True:
                        media_group.append(
                            InputMediaPhoto(
                                media=node.display_url,
                                caption=pair.caption,
                                caption_entities=pair.entities,
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=node.video_url,
                                caption=pair.caption,
                                caption_entities=pair.entities,
                            )
                        )
                    counter += 1
                for input_medium in media_group:
                    logging.info(input_medium)
                update.message.reply_media_group(
                    media=media_group,
                    quote=True,
                )

            elif post.typename in ("GraphImage", "GraphVideo"):
                pair = pair_gen(post)
                if post.typename == "GraphImage":
                    update.message.reply_photo(
                        photo=post.url,
                        quote=True,
                        caption=pair.caption,
                        caption_entities=pair.entities,
                    )

                elif post.typename == "GraphVideo":
                    update.message.reply_video(
                        video=post.video_url,
                        quote=True,
                        caption=pair.caption,
                        caption_entities=pair.entities,
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

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, reply))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":

    main(args.token)
