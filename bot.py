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
from typing import NamedTuple, List, Union, Dict


class Pair(NamedTuple):
    caption: str = ""
    entities: List[telegram.MessageEntity] = []


if __name__ == "__main__":
    import argparse

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Runs TG bot")
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
        authorized_users: set = set()
        logging.info("No authorized users specified")
    else:
        authorized_users: set = set(int(uid) for uid in parser.parse_args().uid)
        logging.info("Authorized users: " + str(authorized_users))

    L = instaloader.Instaloader()
    if parser.parse_args().login is not False:
        IG_user: str = input("Please type your Instagram username: ")
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
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


def pair_gen(
    input_post: instaloader.Post,
    media_url: str = None,
    counter: int = None,
) -> Pair:

    caption: str = ""
    entities: list[telegram.MessageEntity] = []

    # Media URL
    if media_url is not None:
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
            (" " + str(counter) + "/" + str(input_post.mediacount) + "\n")
            if counter is not None
            else "\n"
        )
    )

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

    # Likes and Comments
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
    if update.inline_query.from_user.id in authorized_users:
        results: list[InlineQueryResult] = []
        shortcode: str = update.inline_query.query
        post: instaloader.Post = instaloader.Post.from_shortcode(L.context, shortcode)
        logging.info(post.typename)
        logging.info(post.mediacount)
        if post.typename == "GraphSidecar":
            counter: int = 0
            for x in post.get_sidecar_nodes():
                counter += 1
                pair = pair_gen(
                    post, x.video_url if x.is_video else x.display_url, counter
                )
                if x.is_video is not True:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=x.display_url,
                            thumb_url=x.display_url,
                            title="",
                            caption=pair.caption,
                            caption_entities=pair.entities,
                        )
                    )

                else:
                    results.append(
                        InlineQueryResultVideo(
                            id=str(uuid4()),
                            video_url=x.video_url,
                            mime_type="video/mp4",
                            thumb_url=x.display_url,
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
                        thumb_url=x.display_url,
                    )
                )

        elif post.typename == "GraphImage" or post.typename == "GraphVideo":
            pair = pair_gen(
                post, post.video_url if post.typename == "GraphVideo" else post.url
            )
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
    if update.message.from_user.id in authorized_users:
        shortcode = update.message.text
        if ig_post:
            post: instaloader.Post = instaloader.Post.from_shortcode(
                L.context, shortcode
            )
            logging.info(str(post))

            if post.typename == "GraphSidecar":
                counter: int = 0
                media_group: list[Union[InputMediaPhoto, InputMediaVideo]] = []
                for x in post.get_sidecar_nodes():
                    counter += 1
                    pair = pair_gen(
                        post, x.video_url if x.is_video else x.display_url, counter
                    )
                    if x.is_video is not True:
                        media_group.append(
                            InputMediaPhoto(
                                media=x.display_url,
                                caption=pair.caption,
                                caption_entities=pair.entities,
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=x.video_url,
                                caption=pair.caption,
                                caption_entities=pair.entities,
                            )
                        )
                for y in media_group:
                    logging.info(y)
                update.message.reply_media_group(
                    media=media_group,
                    quote=True,
                )

            elif post.typename == "GraphImage" or post.typename == "GraphVideo":
                pair = pair_gen(
                    post, post.video_url if post.typename == "GraphVideo" else post.url
                )
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

    main(parser.parse_args().token)
