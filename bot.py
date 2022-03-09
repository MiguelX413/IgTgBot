#!/usr/bin/env python3
import logging
import os
import instaloader
from uuid import uuid4

from datetime import datetime

import telegram
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


def caption_gen(
    owner_username: str,
    shortcode: str,
    likes: int,
    comments: int,
    created_time: datetime,
    post_caption: str,
    owner_id: int = None,
    counter: int = None,
    media_count: int = None,
    media_url: str = None,
) -> str:
    output = ""

    if media_url is not None:
        output += media_url + "\n"

    output += (
        "@"
        + owner_username
        + ((" (" + str(owner_id) + ")") if owner_id is not None else "")
        + ": "
        + "https://instagram.com/p/"
        + shortcode
        + "/"
        + (
            (" " + str(counter) + "/" + str(media_count) + "\n")
            if counter is not None and media_count is not None
            else "\n"
        )
    )

    output += "❤️" + str(likes) + " 💬" + str(comments) + "\n"

    output += f"{created_time:%Y-%m-%d %H:%M:%S}" + "\n"

    output += post_caption

    return output


def owner_url_entity(offset: int, owner_username: str) -> telegram.MessageEntity:
    return telegram.MessageEntity(
        type="text_link",
        offset=offset,
        length=len("@" + owner_username),
        url="https://instagram.com/" + owner_username + "/",
    )


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao")


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Produces results for Inline Queries"""
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
                            photo_url=x.display_url,
                            thumb_url=x.display_url,
                            title="",
                            caption="Media\n"
                            + caption_gen(
                                post.owner_username,
                                shortcode,
                                post.likes,
                                post.comments,
                                post.date_utc,
                                post.caption,
                                post.owner_id,
                                counter=counter,
                                media_count=post.mediacount,
                            ),
                            caption_entities=[
                                telegram.MessageEntity(
                                    type="text_link",
                                    offset=0,
                                    length=5,
                                    url=x.display_url,
                                ),
                                owner_url_entity(6, post.owner_username),
                            ],
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
                            caption="Media\n"
                            + caption_gen(
                                post.owner_username,
                                shortcode,
                                post.likes,
                                post.comments,
                                post.date_utc,
                                post.caption,
                                post.owner_id,
                                counter=counter,
                                media_count=post.mediacount,
                            ),
                            caption_entities=[
                                telegram.MessageEntity(
                                    type="text_link",
                                    offset=0,
                                    length=5,
                                    url=x.video_url,
                                ),
                                owner_url_entity(6, post.owner_username),
                            ],
                        )
                    )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="URL",
                        input_message_content=InputTextMessageContent(
                            "Media\n"
                            + caption_gen(
                                post.owner_username,
                                shortcode,
                                post.likes,
                                post.comments,
                                post.date_utc,
                                post.caption,
                                post.owner_id,
                                counter=counter,
                                media_count=post.mediacount,
                                # mediaurl=x.video_url if x.is_video else x.display_url,
                            ),
                            entities=[
                                telegram.MessageEntity(
                                    type="text_link",
                                    offset=0,
                                    length=5,
                                    url=x.video_url if x.is_video else x.display_url,
                                ),
                                owner_url_entity(6, post.owner_username),
                            ],
                        ),
                        thumb_url=x.display_url,
                    )
                )
        elif post.typename == "GraphImage" or post.typename == "GraphVideo":
            if post.typename == "Graphimage":
                results.append(
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        title="",
                        photo_url=post.url,
                        thumb_url=post.url,
                        caption="Media\n"
                        + caption_gen(
                            post.owner_username,
                            shortcode,
                            post.likes,
                            post.comments,
                            post.date_utc,
                            post.caption,
                            owner_id=post.owner_id,
                        ),
                        caption_entities=[
                            telegram.MessageEntity(
                                type="text_link",
                                offset=0,
                                length=5,
                                url=post.url,
                            ),
                            owner_url_entity(6, post.owner_username),
                        ],
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
                        caption="Media\n"
                        + caption_gen(
                            post.owner_username,
                            shortcode,
                            post.likes,
                            post.comments,
                            post.date_utc,
                            post.caption,
                            owner_id=post.owner_id,
                        ),
                        caption_entities=[
                            telegram.MessageEntity(
                                type="text_link",
                                offset=0,
                                length=5,
                                url=post.video_url,
                            ),
                            owner_url_entity(6, post.owner_username),
                        ],
                    )
                )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    input_message_content=InputTextMessageContent(
                        "Media\n"
                        + caption_gen(
                            post.owner_username,
                            shortcode,
                            post.likes,
                            post.comments,
                            post.date_utc,
                            post.caption,
                            owner_id=post.owner_id,
                            # mediaurl=post.video_url if post.typename == "GraphVideo" else post.url,
                        ),
                        entities=[
                            telegram.MessageEntity(
                                type="text_link",
                                offset=0,
                                length=5,
                                url=post.video_url
                                if post.typename == "GraphVideo"
                                else post.url,
                            ),
                            owner_url_entity(6, post.owner_username),
                        ],
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
    ig_post = True
    if update.message.from_user.id in authorized_users:
        shortcode = update.message.text
        if ig_post:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            logging.info(str(post))
            if post.typename == "GraphImage":
                update.message.reply_photo(
                    photo=post.url,
                    quote=True,
                    caption="Media\n"
                    + caption_gen(
                        post.owner_username,
                        shortcode,
                        post.likes,
                        post.comments,
                        post.date_utc,
                        post.caption,
                        post.owner_id,
                    ),
                    caption_entities=[
                        telegram.MessageEntity(
                            type="text_link",
                            offset=0,
                            length=5,
                            url=post.url,
                        ),
                        owner_url_entity(6, post.owner_username),
                    ],
                )
            elif post.typename == "GraphVideo":
                update.message.reply_video(
                    video=post.video_url,
                    quote=True,
                    caption="Media\n"
                    + caption_gen(
                        post.owner_username,
                        shortcode,
                        post.likes,
                        post.comments,
                        post.date_utc,
                        post.caption,
                        post.owner_id,
                    ),
                    caption_entities=[
                        telegram.MessageEntity(
                            type="text_link",
                            offset=0,
                            length=5,
                            url=post.video_url,
                        ),
                        owner_url_entity(6, post.owner_username),
                    ],
                )
            elif post.typename == "GraphSidecar":
                counter = 0
                media_group = []
                for x in post.get_sidecar_nodes():
                    counter += 1
                    caption = "Media\n" + caption_gen(
                        post.owner_username,
                        shortcode,
                        post.likes,
                        post.comments,
                        post.date_utc,
                        post.caption,
                        owner_id=post.owner_id,
                        counter=counter,
                        media_count=post.mediacount,
                    )
                    if x.is_video is not True:
                        media_group.append(
                            InputMediaPhoto(
                                media=x.display_url,
                                caption=caption,
                                caption_entities=[
                                    telegram.MessageEntity(
                                        type="text_link",
                                        offset=0,
                                        length=5,
                                        url=x.display_url,
                                    ),
                                    owner_url_entity(6, post.owner_username),
                                ],
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=x.video_url,
                                caption=caption,
                                caption_entities=[
                                    telegram.MessageEntity(
                                        type="text_link",
                                        offset=0,
                                        length=5,
                                        url=x.video_url,
                                    ),
                                    owner_url_entity(6, post.owner_username),
                                ],
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

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, reply))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":

    main(parser.parse_args().token)
