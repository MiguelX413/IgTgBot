#!/usr/bin/env python3
import logging
import os
from typing import NamedTuple, List, Union, Dict, Set
from uuid import uuid4

from instaloader import Instaloader, Post, Profile
from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
    InlineQueryResult,
    InputTextMessageContent,
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    MessageEntity,
)
from telegram.ext import (
    Updater,
    InlineQueryHandler,
    CommandHandler,
    CallbackContext,
)


emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class Pairs(NamedTuple):
    long_caption: str = ""
    long_entities: List[MessageEntity] = []

    @classmethod
    def from_post(cls, input_post: Post, counter: int = None):
        """Create a Pair object from a given post"""
        # Initializing
        caption: str = ""
        entities: List[MessageEntity] = []

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
            MessageEntity(
                type="text_link",
                offset=utf16len(caption),
                length=utf16len("Media"),
                url=media_url,
            )
        )
        caption += "Media\n"

        # Posting account and Counter
        entities.append(
            MessageEntity(
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

        # Title
        if input_post.title not in (None, ""):
            caption += input_post.title + "\n"

        # Sponsor(s)
        if input_post.is_sponsored:
            caption += "Sponsors:"
            for sponsor_user in input_post.sponsor_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len("@" + sponsor_user.username),
                        url="https://instagram.com/" + sponsor_user.username + "/",
                    )
                )
                caption += (
                    "@" + sponsor_user.username + " (" + str(sponsor_user.userid) + ")"
                )
            caption += "\n"

        # Tagged Users
        if len(input_post.tagged_users) > 0:
            caption += emojis["person"]
            for tagged_user in input_post.tagged_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len("@" + tagged_user),
                        url="https://instagram.com/" + tagged_user + "/",
                    )
                )
                caption += (
                    "@"
                    + tagged_user
                    + " ("
                    + str(Profile.from_username(L.context, tagged_user).userid)
                    + ")"
                )
            caption += "\n"

        # Location
        if input_post.location is not None:
            entities.append(
                MessageEntity(
                    type="text_link",
                    offset=utf16len(caption + emojis["location"]),
                    length=utf16len(str(input_post.location.name)),
                    url="https://instagram.com/explore/locations/"
                    + str(input_post.location.id)
                    + "/",
                )
            )
            caption += emojis["location"] + str(input_post.location.name) + "\n"

        # Views, Likes, and Comments
        if input_post.is_video:
            caption += emojis["eyes"] + str(input_post.video_view_count) + " "
        entities.append(
            MessageEntity(
                type="text_link",
                offset=utf16len(caption + emojis["heart"]),
                length=utf16len(str(input_post.likes)),
                url="https://instagram.com/p/" + input_post.shortcode + "/liked_by/",
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
        caption += (
            emojis["calendar"] + f"{input_post.date_utc:%Y-%m-%d %H:%M:%S}" + "\n"
        )

        # Post Caption
        if input_post.caption is not None:
            old_caption = caption
            caption += input_post.caption

            # Mentions + Hashtags
            search_caption = (
                old_caption.replace("@", ",") + input_post.caption
            ).lower()

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(input_post.caption_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, "@" + caption_mention
                ):
                    if mention_occurrence not in mention_occurrences:
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:mention_occurrence]),
                                length=utf16len("@" + caption_mention),
                                url="https://instagram.com/" + caption_mention + "/",
                            )
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in caption
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(input_post.caption_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, "#" + caption_hashtag
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:hashtag_occurrence]),
                                length=utf16len("#" + caption_hashtag),
                                url="https://instagram.com/explore/tags/"
                                + caption_hashtag
                                + "/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return cls(caption, entities)

    @property
    def short_caption(self) -> str:
        if len(self.long_caption) > 1024:
            return self.long_caption[0:1023] + "…"
        else:
            return self.long_caption

    @property
    def short_entities(self) -> List[MessageEntity]:
        short_entities: List[MessageEntity] = []
        for long_entity in list(self.long_entities):
            if (
                len(
                    self.long_caption.encode("UTF-16-le")[
                        0 : 2 * (long_entity.offset + long_entity.length)
                    ].decode("UTF-16-le")
                )
                > 1024
            ):
                if (
                    len(
                        self.long_caption.encode("UTF-16-le")[
                            0 : 2 * long_entity.offset
                        ].decode("UTF-16-le")
                    )
                    < 1024
                ):
                    short_entities.append(
                        MessageEntity(
                            long_entity.type,
                            long_entity.offset,
                            len(
                                self.long_caption[:1023]
                                .encode("UTF-16-le")[2 * long_entity.offset :]
                                .decode("UTF-16-le")
                            ),
                            long_entity.url,
                        )
                    )
            else:
                short_entities.append(
                    MessageEntity(
                        long_entity.type,
                        long_entity.offset,
                        long_entity.length,
                        long_entity.url,
                    )
                )
        return short_entities


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
        logging.info("Authorized users: " + str(whitelist))

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
        post: Post = Post.from_shortcode(L.context, shortcode)
        logging.info(post.typename)
        logging.info(post.mediacount)
        if post.typename == "GraphSidecar":
            counter: int = 0
            for node in post.get_sidecar_nodes():
                pairs = Pairs.from_post(post, counter)
                if node.is_video is not True:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=node.display_url,
                            thumb_url=node.display_url,
                            title="Photo",
                            caption=pairs.short_caption,
                            caption_entities=pairs.short_entities,
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
                            caption=pairs.short_caption,
                            caption_entities=pairs.short_entities,
                        )
                    )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="URL",
                        input_message_content=InputTextMessageContent(
                            pairs.short_caption,
                            entities=pairs.short_entities,
                        ),
                        thumb_url=node.display_url,
                    )
                )
                counter += 1

        elif post.typename in ("GraphImage", "GraphVideo"):
            pairs = Pairs.from_post(post)
            if post.typename == "GraphImage":
                results.append(
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        title="Photo",
                        photo_url=post.url,
                        thumb_url=post.url,
                        caption=pairs.short_caption,
                        caption_entities=pairs.short_entities,
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
                        caption=pairs.short_caption,
                        caption_entities=pairs.short_entities,
                    )
                )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    input_message_content=InputTextMessageContent(
                        pairs.short_caption,
                        entities=pairs.short_entities,
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
                post: Post = Post.from_shortcode(L.context, shortcode)
                logging.info(str(post))

                if post.typename == "GraphSidecar":
                    counter: int = 0
                    media_group: List[Union[InputMediaPhoto, InputMediaVideo]] = []
                    for node in post.get_sidecar_nodes():
                        pairs = Pairs.from_post(post, counter)
                        if node.is_video is not True:
                            media_group.append(
                                InputMediaPhoto(
                                    media=node.display_url,
                                    caption=pairs.short_caption,
                                    caption_entities=pairs.short_entities,
                                )
                            )
                        else:
                            media_group.append(
                                InputMediaVideo(
                                    media=node.video_url,
                                    caption=pairs.short_caption,
                                    caption_entities=pairs.short_entities,
                                )
                            )
                        counter += 1
                    for input_medium in media_group:
                        logging.info(input_medium)
                    first_reply = update.message.reply_media_group(
                        media=media_group,
                        quote=True,
                    )
                    pairs = Pairs.from_post(post)
                    if len(pairs.long_caption) > 1024:
                        first_reply[post.mediacount - 1].reply_text(
                            pairs.long_caption, entities=pairs.long_entities, quote=True
                        )

                elif post.typename in ("GraphImage", "GraphVideo"):
                    pairs = Pairs.from_post(post)
                    if post.typename == "GraphImage":
                        first_reply = update.message.reply_photo(
                            photo=post.url,
                            quote=True,
                            caption=pairs.short_caption,
                            caption_entities=pairs.short_entities,
                        )

                    elif post.typename == "GraphVideo":
                        first_reply = update.message.reply_video(
                            video=post.video_url,
                            quote=True,
                            caption=pairs.short_caption,
                            caption_entities=pairs.short_entities,
                        )
                    if len(pairs.long_caption) > 1024:
                        first_reply.reply_text(
                            pairs.long_caption, entities=pairs.long_entities, quote=True
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
