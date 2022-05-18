#!/usr/bin/env python3
import logging
from types import TracebackType
from typing import List, Optional, Set, Type, Union
from uuid import uuid4

from instaloader import Instaloader
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
from telegram.constants import MAX_CAPTION_LENGTH
from telegram.ext import CallbackContext

from structures import (
    PatchedPost,
    PatchedProfile,
    PatchedStoryItem,
    PostCaptions,
    ProfileCaptions,
    StoryItemCaptions,
)


class InstagramHandler:
    instaloader: Instaloader
    whitelist: Optional[Set[int]]

    def __init__(self, ig_user: Optional[str], whitelist: Optional[Set[int]]) -> None:
        self.whitelist = whitelist

        instaloader = Instaloader()
        if ig_user is not None:
            try:
                instaloader.load_session_from_file(username=ig_user)
            except FileNotFoundError:
                instaloader.interactive_login(ig_user)
            instaloader.save_session_to_file()
        self.instaloader = instaloader

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

    def inlinequery(self, update: Update, context: CallbackContext) -> None:
        """Produces results for Inline Queries"""
        logging.info(update.inline_query)

        if update.inline_query is None:
            return
        # Check if there is anything typed in the inline query
        if update.inline_query.query in ("", None):
            return

        # Check if the Telegram user is authorized to use this function
        if (self.whitelist is not None) and (
            update.inline_query.from_user.id not in self.whitelist
        ):
            update.inline_query.answer(
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
        if post.typename == "GraphSidecar":
            post_captions = PostCaptions(post)
            for counter, node in enumerate(post.get_sidecar_nodes()):
                short = post_captions.short_caption(counter)
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
            post_captions = PostCaptions(post)
            short = post_captions.short_caption()
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
        update.inline_query.answer(results, cache_time=21600, is_personal=False)

    def posts(self, update: Update, context: CallbackContext) -> None:
        """Returns posts"""
        logging.info(str(update.message))

        if update.message is None:
            return

        if (self.whitelist is not None) and (
            (update.message.from_user is not None)
            and (update.message.from_user.id not in self.whitelist)
        ):
            update.message.reply_text("Unauthorized user", quote=True)
            return

        if (context.args is None) or (len(context.args) < 1):
            update.message.reply_text(
                "Please run the command with a shortcode.", quote=True
            )
            return

        shortcode: str = context.args[0]
        is_ig_post: bool = True

        if not is_ig_post:
            update.message.reply_text("Not an Instagram post", quote=True)
            return
        post: PatchedPost = PatchedPost.from_shortcode(
            self.instaloader.context, shortcode
        )
        logging.info(str(post.__dict__))

        if post.typename == "GraphSidecar":
            post_captions = PostCaptions(post)
            media_group: List[
                Union[
                    InputMediaAudio,
                    InputMediaDocument,
                    InputMediaPhoto,
                    InputMediaVideo,
                ]
            ] = []
            for counter, node in enumerate(post.get_sidecar_nodes()):
                short = post_captions.short_caption(counter)
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
            media_reply: Optional[Message] = update.message.reply_media_group(
                media=media_group,
                quote=True,
            )[-1]

        else:
            post_captions = PostCaptions(post)
            short = post_captions.short_caption()
            if (post.typename == "GraphVideo") and (post.video_url is not None):
                media_reply = update.message.reply_video(
                    video=post.video_url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

            else:
                if post.typename != "GraphImage":
                    logging.info("Post type irregular: %s", post.typename)
                    update.message.reply_text(
                        f"Invalid type: {post.typename}, will try to send as image.",
                        quote=True,
                    )
                media_reply = update.message.reply_photo(
                    photo=post.url,
                    quote=True,
                    caption=short.text,
                    caption_entities=short.entities,
                )

        long = post_captions.long_caption()
        if (media_reply is not None) and (
            (len(long) > MAX_CAPTION_LENGTH)
            or (
                (post.typename == "GraphSidecar")
                and (len(post_captions.long_caption(0)) > MAX_CAPTION_LENGTH)
            )
        ):
            media_reply.reply_text(long.text, entities=long.entities, quote=True)

    def story_item(self, update: Update, context: CallbackContext) -> None:
        """Returns story items"""
        logging.info(str(update.message))

        if (update.message is None) or (update.message.from_user is None):
            return

        if (self.whitelist is not None) and (
            update.message.from_user.id not in self.whitelist
        ):
            update.message.reply_text("Unauthorized user", quote=True)
            return
        if (context.args is None) or (len(context.args) < 1):
            update.message.reply_text(
                "Please run the command with a storyitem ID.", quote=True
            )
            return

        try:
            media_id: int = int(context.args[0])
        except ValueError:
            update.message.reply_text("Invalid storyitem ID.", quote=True)
            return

        is_ig_story_item: bool = True
        if not is_ig_story_item:
            update.message.reply_text("Not an Instagram story item", quote=True)
            return
        story_item: PatchedStoryItem = PatchedStoryItem.from_mediaid(
            self.instaloader.context, media_id
        )
        logging.info(str(story_item.__dict__))

        story_item_captions = StoryItemCaptions(story_item)
        short = story_item_captions.short_caption()
        if story_item.is_video and (story_item.video_url is not None):
            first_reply = update.message.reply_video(
                video=story_item.video_url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )

        else:
            first_reply = update.message.reply_photo(
                photo=story_item.url,
                quote=True,
                caption=short.text,
                caption_entities=short.entities,
            )
        long = story_item_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            first_reply.reply_text(long.text, entities=long.entities, quote=True)

    def profile(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        logging.info(str(update.message))

        if update.message is None or update.message.from_user is None:
            return

        if (self.whitelist is not None) and (
            update.message.from_user.id not in self.whitelist
        ):
            update.message.reply_text("Unauthorized user", quote=True)
            return
        if (context.args is None) or (len(context.args) < 1):
            update.message.reply_text(
                "Please run the command with a profile username.", quote=True
            )
            return
        profile_username: str = context.args[0]
        is_ig_profile: bool = True
        if not is_ig_profile:
            update.message.reply_text("Not an Instagram profile", quote=True)
            return
        profile: PatchedProfile = PatchedProfile.from_username(
            self.instaloader.context, profile_username
        )
        logging.info(str(profile.__dict__))

        profile_captions = ProfileCaptions(profile)
        short = profile_captions.short_caption()
        first_reply = update.message.reply_photo(
            photo=profile.profile_pic_url,
            quote=True,
            caption=short.text,
            caption_entities=short.entities,
        )
        long = profile_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            first_reply.reply_text(long.text, entities=long.entities, quote=True)

    def profile_id(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        logging.info(str(update.message))

        if (update.message is None) or (update.message.from_user is None):
            return

        if (self.whitelist is not None) and (
            update.message.from_user.id not in self.whitelist
        ):
            update.message.reply_text("Unauthorized user", quote=True)
            return
        if (context.args is None) or (len(context.args) < 1):
            update.message.reply_text(
                "Please run the command with a profile ID.", quote=True
            )
            return

        try:
            profile_id: int = int(context.args[0])
        except ValueError:
            update.message.reply_text("Invalid profile ID.", quote=True)
            return

        is_ig_profile: bool = True
        if not is_ig_profile:
            update.message.reply_text("Not an Instagram profile", quote=True)
            return

        profile: PatchedProfile = PatchedProfile.from_id(
            self.instaloader.context, profile_id
        )
        logging.info(str(profile.__dict__))

        profile_captions = ProfileCaptions(profile)
        short = profile_captions.short_caption()
        first_reply = update.message.reply_photo(
            photo=profile.profile_pic_url,
            quote=True,
            caption=short.text,
            caption_entities=short.entities,
        )
        long = profile_captions.long_caption()
        if len(long.text) > MAX_CAPTION_LENGTH:
            first_reply.reply_text(long.text, entities=long.entities, quote=True)
