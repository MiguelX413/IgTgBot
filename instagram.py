#!/usr/bin/env python3
import logging
from types import TracebackType
from typing import List, Optional, Set, Type, Union
from uuid import uuid4

from instagrapi import Client
from telegram import (
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    InputTextMessageContent,
    Message,
    Update,
)
from telegram.constants import MessageLimit
from telegram.ext import CallbackContext

from captions import MediaCaptions, UserCaptions, StoryCaptions
from formatted_text import shorten_formatted_text
from login import login_user

MAX_CAPTION_LENGTH = MessageLimit.CAPTION_LENGTH


class InstagramHandler:
    client: Client
    whitelist: Optional[Set[int]]

    def __init__(
        self,
        ig_user: Optional[str],
        whitelist: Optional[Set[int]],
        delay_range: Optional[List[int]] = None,
    ) -> None:
        self.whitelist = whitelist

        self.client = Client()

        if ig_user is not None:
            login_user(self.client, ig_user)

        self.client.delay_range = [1, 3] if delay_range is None else delay_range

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Legacy code"""
        return None

    async def inlinequery(self, update: Update, context: CallbackContext) -> None:
        """Produces results for Inline Queries"""
        logging.info(update.inline_query)

        if update.inline_query is None:
            raise ValueError("Expected update.inline_query to not be None.")
        # Check if there is anything typed in the inline query
        if update.inline_query.query in ("", None):
            return

        # Check if the Telegram user is authorized to use this function
        if (self.whitelist is not None) and (
            update.inline_query.from_user.id not in self.whitelist
        ):
            await update.inline_query.answer(
                [
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="Unauthorized user",
                        input_message_content=InputTextMessageContent(
                            "Unauthorized user"
                        ),
                    )
                ],
                cache_time=300,
                is_personal=True,
            )
            return

        shortcode: str = update.inline_query.query
        media = self.client.media_info(self.client.media_pk_from_code(shortcode))
        logging.info(str(media.__dict__))
        results: List[InlineQueryResult] = []

        post_captions = MediaCaptions(media)
        long = post_captions.long_caption()

        if media.media_type == 8:  # Album
            for counter, node in enumerate(media.resources):
                short = post_captions.short_caption(counter)
                if node.video_url is not None:
                    results.append(
                        InlineQueryResultVideo(
                            id=str(uuid4()),
                            video_url=node.video_url,
                            mime_type="video/mp4",
                            thumb_url=node.thumbnail_url,
                            title="Video",
                            caption=short.text,
                            caption_entities=short.entities,
                        )
                    )

                else:
                    results.append(
                        InlineQueryResultPhoto(
                            id=str(uuid4()),
                            photo_url=node.thumbnail_url,
                            thumb_url=node.thumbnail_url,
                            title="Photo",
                            caption=short.text,
                            caption_entities=short.entities,
                        )
                    )
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title="URL",
                        input_message_content=InputTextMessageContent(
                            short.text,
                            entities=short.entities,
                        ),
                        thumb_url=node.thumbnail_url,
                    )
                )

        else:
            short = shorten_formatted_text(long)
            if (media.media_type == 2) and (media.video_url is not None):
                results.append(
                    InlineQueryResultVideo(
                        id=str(uuid4()),
                        title="Video",
                        video_url=media.video_url,
                        thumb_url=media.thumbnail_url,
                        mime_type="video/mp4",
                        caption=short.text,
                        caption_entities=short.entities,
                    )
                )

            else:
                results.append(
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        title="Photo",
                        photo_url=media.thumbnail_url,
                        thumb_url=media.thumbnail_url,
                        caption=short.text,
                        caption_entities=short.entities,
                    )
                )
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="URL",
                    input_message_content=InputTextMessageContent(
                        short.text,
                        entities=short.entities,
                    ),
                    thumb_url=media.thumbnail_url,
                )
            )
        await update.inline_query.answer(results, cache_time=21600, is_personal=False)

    async def posts(self, update: Update, context: CallbackContext) -> None:
        """Returns posts"""
        logging.info(str(update.message))

        if update.message is None:
            raise ValueError("Expected update.message to not be None.")

        if (self.whitelist is not None) and (
            (update.message.from_user is not None)
            and (update.message.from_user.id not in self.whitelist)
        ):
            await update.message.reply_text("Unauthorized user", quote=True)
            return

        if (context.args is None) or (len(context.args) < 1):
            await update.message.reply_text(
                "Please run the command with a shortcode.", quote=True
            )
            return

        shortcode: str = context.args[0]
        is_ig_post: bool = True

        if not is_ig_post:
            await update.message.reply_text("Not an Instagram post", quote=True)
            return
        media = self.client.media_info(self.client.media_pk_from_code(shortcode))
        logging.info(str(media.__dict__))

        post_captions = MediaCaptions(media)
        long = post_captions.long_caption()

        if media.media_type == 8:  # Album
            media_group: List[
                Union[
                    InputMediaAudio,
                    InputMediaDocument,
                    InputMediaPhoto,
                    InputMediaVideo,
                ]
            ] = []
            for counter, node in enumerate(media.resources):
                short = post_captions.short_caption(counter)
                if node.video_url is not None:
                    media_group.append(
                        InputMediaVideo(
                            media=node.video_url,
                            caption=short.text,
                            caption_entities=short.entities,
                        )
                    )
                else:
                    media_group.append(
                        InputMediaPhoto(
                            media=node.thumbnail_url,
                            caption=short.text,
                            caption_entities=short.entities,
                        )
                    )
            for input_medium in media_group:
                logging.info(input_medium)
            media_reply: Optional[Message] = (
                await update.message.reply_media_group(
                    media=media_group,
                    quote=True,
                )
            )[-1]

        else:
            short = shorten_formatted_text(long)
            if (media.media_type == 2) and (media.video_url is not None):
                media_reply = await update.message.reply_video(
                    video=media.video_url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

            else:
                if media.media_type != 1:
                    logging.info("Post type irregular: %s", media.media_type)
                    await update.message.reply_text(
                        f"Invalid type: {media.media_type}, will try to send as image.",
                        quote=True,
                    )
                media_reply = await update.message.reply_photo(
                    photo=media.thumbnail_url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

        if (media_reply is not None) and (
            (len(long) > MAX_CAPTION_LENGTH)
            or (
                (media.media_type == 8)  # Album
                and (len(post_captions.long_caption(0)) > MAX_CAPTION_LENGTH)
            )
        ):
            await media_reply.reply_text(long.text, entities=long.entities, quote=True)

    async def story_item(self, update: Update, context: CallbackContext) -> None:
        """Returns story items"""
        logging.info(str(update.message))

        if update.message is None:
            raise ValueError("Expected update.message to not be None.")

        if (
            (self.whitelist is not None)
            and (update.message.from_user is not None)
            and (update.message.from_user.id not in self.whitelist)
        ):
            await update.message.reply_text("Unauthorized user", quote=True)
            return

        if (context.args is None) or (len(context.args) < 1):
            await update.message.reply_text(
                "Please run the command with a storyitem ID.", quote=True
            )
            return

        try:
            media_id: int = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid storyitem ID.", quote=True)
            return

        is_ig_story_item: bool = True
        if not is_ig_story_item:
            await update.message.reply_text("Not an Instagram story item", quote=True)
            return
        story_item = self.client.story_info(str(media_id))
        logging.info(str(story_item.__dict__))

        story_item_captions = StoryCaptions(story_item)
        short = story_item_captions.short_caption()
        if (story_item.media_type == 2) and (story_item.video_url is not None):
            first_reply = await update.message.reply_video(
                video=story_item.video_url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )

        else:
            first_reply = await update.message.reply_photo(
                photo=story_item.thumbnail_url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )
        long = story_item_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            await first_reply.reply_text(long.text, entities=long.entities, quote=True)

    async def _profile(
        self, update: Update, context: CallbackContext, is_id: bool
    ) -> None:
        """Returns Instagram profiles"""
        logging.info(str(update.message))

        if update.message is None:
            raise ValueError("Expected update.message to not be None.")

        if (
            (self.whitelist is not None)
            and (update.message.from_user is not None)
            and (update.message.from_user.id not in self.whitelist)
        ):
            await update.message.reply_text("Unauthorized user", quote=True)
            return
        if (context.args is None) or (len(context.args) < 1):
            await update.message.reply_text(
                "Please run the command with a profile username.", quote=True
            )
            return
        id_or_username = context.args[0]
        is_ig_profile: bool = True
        if not is_ig_profile:
            await update.message.reply_text("Not an Instagram profile", quote=True)
            return
        user = (
            self.client.user_info(id_or_username)
            if is_id
            else self.client.user_info_by_username(id_or_username)
        )
        logging.info(str(user.__dict__))

        profile_captions = UserCaptions(user)
        short = profile_captions.short_caption()
        first_reply = await update.message.reply_photo(
            photo=user.profile_pic_url,
            quote=True,
            caption=short.text,
            caption_entities=short.entities,
        )
        long = profile_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            await first_reply.reply_text(long.text, entities=long.entities, quote=True)

    async def profile(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        return await self._profile(update, context, is_id=False)

    async def profile_id(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        return await self._profile(update, context, is_id=True)
