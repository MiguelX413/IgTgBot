#!/usr/bin/env python3
import logging
from types import TracebackType
from typing import List, Optional, Set, Type, Union
from uuid import uuid4

from instaloader import Instaloader, ConnectionException
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

from captions import PostCaptions, ProfileCaptions, StoryItemCaptions
from formatted_text import shorten_formatted_text
from instaloader_patches import PatchedPost, PatchedProfile, PatchedStoryItem

MAX_CAPTION_LENGTH = MessageLimit.CAPTION_LENGTH


class InstagramHandler:
    instaloader: Instaloader
    whitelist: Optional[Set[int]]

    def __init__(
        self,
        ig_user: Optional[str],
        whitelist: Optional[Set[int]],
        iphone_support: bool = True,
    ) -> None:
        self.whitelist = whitelist

        self.instaloader = Instaloader(iphone_support=iphone_support)
        if ig_user is not None:
            try:
                self.instaloader.load_session_from_file(username=ig_user)
            except FileNotFoundError:
                self.instaloader.interactive_login(ig_user)
            self.instaloader.save_session_to_file()

    def __enter__(self):
        return self

    def close(self) -> None:
        return self.instaloader.close()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        return self.close()

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
        post: PatchedPost = PatchedPost.from_shortcode(
            self.instaloader.context, shortcode
        )
        logging.info(str(post.__dict__))
        results: List[InlineQueryResult] = []

        post_captions = PostCaptions(post)
        location_problems = False
        try:
            long = post_captions.long_caption()
        except ConnectionException as e:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Exception",
                    description="Error message",
                    input_message_content=InputTextMessageContent(
                        "Got a ConnectionException, going to attempt to ignore location"
                    ),
                )
            )
            long = post_captions.long_caption(location=False)
            location_problems = True

        if post.typename == "GraphSidecar":
            for counter, node in enumerate(post.get_sidecar_nodes()):
                short = post_captions.short_caption(
                    counter, location=not location_problems
                )
                if node.is_video is True:
                    results.append(
                        InlineQueryResultVideo(
                            id=str(uuid4()),
                            video_url=node.video_url,
                            mime_type="video/mp4",
                            thumb_url=node.display_url,
                            title="Video",
                            caption=short.text,
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
                        thumb_url=node.display_url,
                    )
                )

        else:
            short = shorten_formatted_text(long)
            if (post.typename == "GraphVideo") and (post.video_url is not None):
                results.append(
                    InlineQueryResultVideo(
                        id=str(uuid4()),
                        title="Video",
                        video_url=post.video_url,
                        thumb_url=post.url,
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
                        photo_url=post.url,
                        thumb_url=post.url,
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
                    thumb_url=post.url,
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
        post: PatchedPost = PatchedPost.from_shortcode(
            self.instaloader.context, shortcode
        )
        logging.info(str(post.__dict__))

        post_captions = PostCaptions(post)
        location_problems = False
        try:
            long = post_captions.long_caption()
        except ConnectionException as e:
            await update.message.reply_text(
                "Got a ConnectionException, going to attempt to ignore location",
                quote=True,
            )
            long = post_captions.long_caption(location=False)
            location_problems = True

        if post.typename == "GraphSidecar":
            media_group: List[
                Union[
                    InputMediaAudio,
                    InputMediaDocument,
                    InputMediaPhoto,
                    InputMediaVideo,
                ]
            ] = []
            for counter, node in enumerate(post.get_sidecar_nodes()):
                short = post_captions.short_caption(
                    counter, location=not location_problems
                )
                if node.is_video is True:
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
                            media=node.display_url,
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
            if (post.typename == "GraphVideo") and (post.video_url is not None):
                media_reply = await update.message.reply_video(
                    video=post.video_url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

            else:
                if post.typename != "GraphImage":
                    logging.info("Post type irregular: %s", post.typename)
                    await update.message.reply_text(
                        f"Invalid type: {post.typename}, will try to send as image.",
                        quote=True,
                    )
                media_reply = await update.message.reply_photo(
                    photo=post.url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

        if (media_reply is not None) and (
            (len(long) > MAX_CAPTION_LENGTH)
            or (
                (post.typename == "GraphSidecar")
                and (
                    len(post_captions.long_caption(0, location=not location_problems))
                    > MAX_CAPTION_LENGTH
                )
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
        story_item: PatchedStoryItem = PatchedStoryItem.from_mediaid(
            self.instaloader.context, media_id
        )
        logging.info(str(story_item.__dict__))

        story_item_captions = StoryItemCaptions(story_item)
        short = story_item_captions.short_caption()
        if story_item.is_video and (story_item.video_url is not None):
            first_reply = await update.message.reply_video(
                video=story_item.video_url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )

        else:
            first_reply = await update.message.reply_photo(
                photo=story_item.url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )
        long = story_item_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            await first_reply.reply_text(long.text, entities=long.entities, quote=True)

    async def profile(self, update: Update, context: CallbackContext) -> None:
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
        profile_username: str = context.args[0]
        is_ig_profile: bool = True
        if not is_ig_profile:
            await update.message.reply_text("Not an Instagram profile", quote=True)
            return
        profile: PatchedProfile = PatchedProfile.from_username(
            self.instaloader.context, profile_username
        )
        logging.info(str(profile.__dict__))

        profile_captions = ProfileCaptions(profile)
        short = profile_captions.short_caption()
        first_reply = await update.message.reply_photo(
            photo=profile.profile_pic_url,
            quote=True,
            caption=short.text,
            caption_entities=short.entities,
        )
        long = profile_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            await first_reply.reply_text(long.text, entities=long.entities, quote=True)

    async def profile_id(self, update: Update, context: CallbackContext) -> None:
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
                "Please run the command with a profile ID.", quote=True
            )
            return

        try:
            profile_id: int = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid profile ID.", quote=True)
            return

        is_ig_profile: bool = True
        if not is_ig_profile:
            await update.message.reply_text("Not an Instagram profile", quote=True)
            return

        profile: PatchedProfile = PatchedProfile.from_id(
            self.instaloader.context, profile_id
        )
        logging.info(str(profile.__dict__))

        profile_captions = ProfileCaptions(profile)
        short = profile_captions.short_caption()
        first_reply = await update.message.reply_photo(
            photo=profile.profile_pic_url,
            quote=True,
            caption=short.text,
            caption_entities=short.entities,
        )
        long = profile_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            await first_reply.reply_text(long.text, entities=long.entities, quote=True)
