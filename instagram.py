#!/usr/bin/env python3
import logging
from typing import List, Union, Set, Optional
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
from telegram.ext import CallbackContext

from structures import PatchedPost, Pairs


class InstagramHandler:
    instaloader: Instaloader
    whitelist: Set[int]

    def __init__(self, ig_user: Optional[str], whitelist: Optional[Set[int]]):
        self.whitelist = whitelist

        L = Instaloader()
        if ig_user is not None:
            ig_user: str = (
                ig_user
                if ig_user is not None
                else input("Please type your Instagram username: ")
            )
            try:
                L.load_session_from_file(username=ig_user)
            except FileNotFoundError:
                L.interactive_login(ig_user)
            L.save_session_to_file()
        self.instaloader = L

    def inlinequery(self, update: Update, context: CallbackContext) -> None:
        """Produces results for Inline Queries"""
        logging.info(update.inline_query)
        if (self.whitelist is None) or (
            update.inline_query.from_user.id in self.whitelist
        ):
            results: List[InlineQueryResult] = []
            shortcode: str = update.inline_query.query
            post: PatchedPost = PatchedPost.from_shortcode(
                self.instaloader.context, shortcode
            )
            logging.info(str(post.__dict__))
            if post.typename == "GraphSidecar":
                counter: int = 0
                pairs = Pairs(post)
                for node in post.get_sidecar_nodes():
                    short = pairs.short(counter)
                    if node.is_video is True:
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

                    else:
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
                if post.typename == "GraphVideo":
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

                else:
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

    def posts(self, update: Update, context: CallbackContext) -> None:
        """Returns posts"""
        logging.info(str(update.message))
        ig_post: bool = True
        print(self.whitelist)
        if (self.whitelist is None) or (update.message.from_user.id in self.whitelist):
            if len(context.args) >= 1:
                shortcode: str = context.args[0]
                if ig_post:
                    post: PatchedPost = PatchedPost.from_shortcode(
                        self.instaloader.context, shortcode
                    )
                    logging.info(str(post.__dict__))

                    if post.typename == "GraphSidecar":
                        pairs = Pairs(post)
                        counter: int = 0
                        media_group: List[Union[InputMediaPhoto, InputMediaVideo]] = []
                        for node in post.get_sidecar_nodes():
                            short = pairs.short(counter)
                            if node.is_video is True:
                                media_group.append(
                                    InputMediaVideo(
                                        media=node.video_url,
                                        caption=short.caption,
                                        caption_entities=short.entities,
                                    )
                                )
                            else:
                                media_group.append(
                                    InputMediaPhoto(
                                        media=node.display_url,
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
                        if post.typename == "GraphVideo":
                            first_reply = update.message.reply_video(
                                video=post.video_url,
                                quote=True,
                                caption=short.caption,
                                caption_entities=short.entities,
                            )

                        else:
                            first_reply = update.message.reply_photo(
                                photo=post.url,
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
