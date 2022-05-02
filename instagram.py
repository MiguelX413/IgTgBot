#!/usr/bin/env python3
import logging
from typing import List, Optional, Set, Union
from uuid import uuid4

from instaloader import Instaloader
from telegram import (
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
    InputMediaPhoto,
    InputMediaVideo,
    InputTextMessageContent,
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
    whitelist: Set[int]

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

            elif post.typename in ("GraphImage", "GraphVideo"):
                post_captions = PostCaptions(post)
                short = post_captions.short_caption()
                if post.typename == "GraphVideo":
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
        is_ig_post: bool = True
        if (self.whitelist is None) or (update.message.from_user.id in self.whitelist):
            if len(context.args) >= 1:
                shortcode: str = context.args[0]
                if is_ig_post:
                    post: PatchedPost = PatchedPost.from_shortcode(
                        self.instaloader.context, shortcode
                    )
                    logging.info(str(post.__dict__))

                    if post.typename == "GraphSidecar":
                        post_captions = PostCaptions(post)
                        media_group: List[Union[InputMediaPhoto, InputMediaVideo]] = []
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
                        first_reply = update.message.reply_media_group(
                            media=media_group,
                            quote=True,
                        )

                        if len(post_captions.long_caption(0).text) > MAX_CAPTION_LENGTH:
                            long = post_captions.long_caption()
                            first_reply[post.mediacount - 1].reply_text(
                                long.text, entities=long.entities, quote=True
                            )

                    elif post.typename in ("GraphImage", "GraphVideo"):
                        post_captions = PostCaptions(post)
                        short = post_captions.short_caption()
                        if post.typename == "GraphVideo":
                            first_reply = update.message.reply_video(
                                video=post.video_url,
                                quote=True,
                                caption=short.text,
                                caption_entities=short.entities,
                            )

                        else:
                            first_reply = update.message.reply_photo(
                                photo=post.url,
                                quote=True,
                                caption=short.text,
                                caption_entities=short.entities,
                            )
                        long = post_captions.long_caption()
                        if len(long.text) > MAX_CAPTION_LENGTH:
                            first_reply.reply_text(
                                long.text, entities=long.entities, quote=True
                            )
                else:
                    update.message.reply_text("Not an Instagram post", quote=True)
        else:
            update.message.reply_text("Unauthorized user", quote=True)

    def story_item(self, update: Update, context: CallbackContext) -> None:
        """Returns story items"""
        logging.info(str(update.message))
        is_ig_story_item: bool = True
        if (self.whitelist is None) or (update.message.from_user.id in self.whitelist):
            if len(context.args) >= 1:
                media_id: int = int(context.args[0])
                if is_ig_story_item:
                    story_item: PatchedStoryItem = PatchedStoryItem.from_mediaid(
                        self.instaloader.context, media_id
                    )
                    logging.info(str(story_item.__dict__))

                    story_item_captions = StoryItemCaptions(story_item)
                    short = story_item_captions.short_caption()
                    if story_item.is_video:
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
                        first_reply.reply_text(
                            long.text, entities=long.entities, quote=True
                        )
                else:
                    update.message.reply_text("Not an Instagram story item", quote=True)
        else:
            update.message.reply_text("Unauthorized user", quote=True)

    def profile(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        logging.info(str(update.message))
        is_ig_profile: bool = True
        if (self.whitelist is None) or (update.message.from_user.id in self.whitelist):
            if len(context.args) >= 1:
                profile_username: str = context.args[0]
                if is_ig_profile:
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
                        first_reply.reply_text(
                            long.text, entities=long.entities, quote=True
                        )
                else:
                    update.message.reply_text("Not an Instagram profile", quote=True)
        else:
            update.message.reply_text("Unauthorized user", quote=True)

    def profileid(self, update: Update, context: CallbackContext) -> None:
        """Returns Instagram profiles"""
        logging.info(str(update.message))
        is_ig_profile: bool = True
        if (self.whitelist is None) or (update.message.from_user.id in self.whitelist):
            if len(context.args) >= 1:
                profile_id: int = int(context.args[0])
                if is_ig_profile:
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
                        first_reply.reply_text(
                            long.text, entities=long.entities, quote=True
                        )
                else:
                    update.message.reply_text("Not an Instagram profile", quote=True)
        else:
            update.message.reply_text("Unauthorized user", quote=True)
