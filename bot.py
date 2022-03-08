#!/usr/bin/env python3
import logging
import os
import instaloader
from uuid import uuid4

authorized_users = {}

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

    L = instaloader.Instaloader()
#    IG_user = input("Please type your Instagram username: ")
#    try:
#        L.load_session_from_file(username=IG_user)
#    except FileNotFoundError:
#        L.interactive_login(IG_user)
#    L.save_session_to_file()


# def parse_for_shortcodes(text: str) -> list:
#    return


def start(update: Update, _: CallbackContext) -> None:
    update.message.reply_text("Hi, lmao")


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    print(update.inline_query)
    if update.inline_query.from_user.id in authorized_users:
        results = []
        query = update.inline_query.query
        post = instaloader.Post.from_shortcode(L.context, query)
        print(post.typename)
        print(post.mediacount)
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
                            + query
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
                            caption="https://instagram.com/p/"
                            + query
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
                    + query
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
            print(post.video_url)
            results.append(
                InlineQueryResultVideo(
                    id=str(uuid4()),
                    title="Video",
                    description="description",
                    video_url=post.video_url,
                    thumb_url=post.video_url,
                    mime_type="video/mp4",
                    caption="https://instagram.com/p/" + query + ("\n" + post.caption)
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
    print(str(update.message))
    ig_post = True
    if update.message.from_user.id in authorized_users:
        if ig_post:
            post = instaloader.Post.from_shortcode(L.context, update.message.text)
            print(str(post))
            if post.typename == "GraphImage":
                print(post.url)
                update.message.reply_photo(
                    photo=post.url,
                    caption="https://instagram.com/p/"
                    + update.message.text
                    + (("\n" + post.caption) if post.caption else (""),)[0],
                    quote=True,
                )
            elif post.typename == "GraphVideo":
                print(post.url)
                update.message.reply_video(
                    video=post.video_url,
                    caption="https://instagram.com/p/"
                    + update.message.text
                    + (("\n" + post.caption) if post.caption else (""),)[0],
                    quote=True,
                )
            elif post.typename == "GraphSidecar":
                counter = 0
                media_group = []
                for x in post.get_sidecar_nodes():
                    counter += 1
                    if x.is_video is not True:
                        media_group.append(
                            InputMediaPhoto(
                                media=x.display_url,
                                caption="https://instagram.com/p/"
                                + update.message.text
                                + " "
                                + str(counter)
                                + "/"
                                + str(post.mediacount)
                                + ("\n" + post.caption)
                                if post.caption
                                else "",
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=x.video_url,
                                caption="https://instagram.com/p/"
                                + update.message.text
                                + " "
                                + str(counter)
                                + "/"
                                + str(post.mediacount)
                                + ("\n" + post.caption)
                                if post.caption
                                else "",
                            )
                        )
                for y in media_group:
                    print(y)
                update.message.reply_media_group(media=media_group, quote=True)
        else:
            update.message.reply_text("Not an Instagram post", quote=True)
    else:
        update.message.reply_text("Unauthorized user", quote=True)


def main() -> None:
    token = os.environ["TG_TOKEN"]
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(InlineQueryHandler(inlinequery))

    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
