#!/usr/bin/env python3
from typing import Dict, Optional, Set

from instagrapi.types import Media, Story, User
from telegram.constants import MessageEntityType

from caption_functions import caption_hashtags, caption_mentions
from formatted_text import FormattedText, shorten_formatted_text
from structures import find_occurrences, utf16len

emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


class MediaCaptions:
    _media: Media

    def __init__(self, media: Media) -> None:
        self._media = media

    def long_caption(
        self, counter: Optional[int] = None, location: bool = True
    ) -> FormattedText:
        """Create a FormattedText object from a given post"""
        # Initializing
        formatted_text = FormattedText()

        # Media URL
        if counter is None:
            media_url = (
                self._media.video_url
                if self._media.media_type == 2
                else self._media.thumbnail_url
            )
        else:
            node = self._media.resources[counter]
            media_url = (
                node.video_url if node.video_url is not None else node.thumbnail_url
            )
        formatted_text.append("Media", type=MessageEntityType.TEXT_LINK, url=media_url)
        formatted_text.append("\n")

        # Posting account, post url, and counter
        formatted_text.append(
            f"@{self._media.user.username}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/{self._media.user.username}",
        )
        formatted_text.append(
            f" ({self._media.user.pk}): https://instagram.com/p/{self._media.code}"
        )
        if counter is not None:
            formatted_text.append(f" {counter + 1}/{len(self._media.resources)}")
        formatted_text.append("\n")

        # Title
        if self._media.title not in (None, ""):
            formatted_text.append(f"{self._media.title}\n")

        # Sponsor(s)
        if len(self._media.sponsor_tags) > 0:
            formatted_text.append("Sponsors:")
            for sponsor_user in self._media.sponsor_tags:
                formatted_text.append(" ")
                formatted_text.append(
                    f"@{sponsor_user.username}",
                    type=MessageEntityType.TEXT_LINK,
                    url=f"https://instagram.com/{sponsor_user.username}",
                )
                formatted_text.append(f" ({sponsor_user.pk})")

            formatted_text.append("\n")

        # Tagged Users
        if len(self._media.usertags) > 0:
            formatted_text.append(emojis["person"])
            for tagged_user in self._media.usertags:
                formatted_text.append(" ")
                formatted_text.append(
                    f"@{tagged_user.user.username}",
                    type=MessageEntityType.TEXT_LINK,
                    url=f"https://instagram.com/{tagged_user.user.username}",
                )
                formatted_text.append(f" ({tagged_user.user.pk})")
            formatted_text.append("\n")

        # Location
        # Short-circuit evaluation is important here
        if location and self._media.location is not None:
            formatted_text.append(emojis["location"])
            formatted_text.append(
                f"{self._media.location.name}",
                type=MessageEntityType.TEXT_LINK,
                url=f"https://instagram.com/explore/locations/{self._media.location.pk}",
            )
            formatted_text.append("\n")

        # Views, Likes, and Comments
        if self._media.media_type == 2:  # Video
            formatted_text.append(f"{emojis['eyes']}{self._media.view_count} ")
        formatted_text.append(emojis["heart"])
        formatted_text.append(
            f"{self._media.like_count}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/p/{self._media.code}/liked_by",
        )
        formatted_text.append(f" {emojis['comments']}{self._media.comment_count}\n")

        # Date
        formatted_text.append(
            f"{emojis['calendar']}{self._media.taken_at:%Y-%m-%d %H:%M:%S}\n"
        )

        # Post Caption
        if self._media.caption_text is not None:
            old_caption = formatted_text.text
            formatted_text.append(self._media.caption_text)

            # Mentions + Hashtags
            search_caption = (
                f"{old_caption.replace('@', ',')}{self._media.caption_text}".lower()
            )

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(caption_mentions(self._media.caption_text.lower())),
                key=len,
                reverse=True,
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        formatted_text.add_entity(
                            type=MessageEntityType.TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:mention_occurrence]),
                            length=utf16len(f"@{caption_mention}"),
                            url=f"https://instagram.com/{caption_mention}",
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in caption
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(caption_hashtags(self._media.caption_text.lower())),
                key=len,
                reverse=True,
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_text.add_entity(
                            type=MessageEntityType.TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:hashtag_occurrence]),
                            length=utf16len(f"#{caption_hashtag}"),
                            url=f"https://instagram.com/explore/tags/{caption_hashtag}",
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_text

    def short_caption(
        self, counter: Optional[int] = None, location: bool = True
    ) -> FormattedText:
        return shorten_formatted_text(self.long_caption(counter, location))


class StoryCaptions:
    _story: Story

    def __init__(self, story: Story) -> None:
        self._story = story

    def long_caption(self) -> FormattedText:
        """Create a FormattedText object from a given post"""
        # Initializing
        formatted_text = FormattedText()

        # Media URL
        media_url = (
            self._story.video_url
            if self._story.video_url is not None
            else self._story.thumbnail_url
        )
        formatted_text.append("Media", type=MessageEntityType.TEXT_LINK, url=media_url)
        formatted_text.append("\n")

        # Posting account and story item url
        formatted_text.append(
            f"@{self._story.user.username}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/{self._story.user.username}",
        )
        formatted_text.append(
            f" ({self._story.user.pk}): https://instagram.com"
            f"/stories/{self._story.user.username}/{self._story.pk}"
        )
        formatted_text.append("\n")

        # Date
        formatted_text.append(
            f"{emojis['calendar']}{self._story.taken_at:%Y-%m-%d %H:%M:%S}\n"
        )

        # Mentions
        for i, mention in enumerate(self._story.mentions):
            if i != 0:
                formatted_text.append(" ")
            formatted_text.append(
                f"#{mention.user.username}",
                type=MessageEntityType.TEXT_LINK,
                url=f"https://instagram.com/{mention.user.username}",
            )
        if len(self._story.mentions) != 0:
            formatted_text.append("\n")

        # Hashtags
        for i, hashtag in enumerate(self._story.hashtags):
            if i != 0:
                formatted_text.append(" ")
            formatted_text.append(
                f"#{hashtag.hashtag.name}",
                type=MessageEntityType.TEXT_LINK,
                url=f"https://instagram.com/explore/tags/{hashtag.hashtag.name}",
            )
        if len(self._story.hashtags) != 0:
            formatted_text.append("\n")

        return formatted_text

    def short_caption(self) -> FormattedText:
        return shorten_formatted_text(self.long_caption())


class UserCaptions:
    user: User

    def __init__(self, user: User) -> None:
        self.user = user

    def long_caption(self) -> FormattedText:
        """Create a FormattedText object from a given profile"""
        # Initializing
        formatted_text = FormattedText()

        # URL to profile picture
        formatted_text.append(
            "Profile Picture",
            type=MessageEntityType.TEXT_LINK,
            url=self.user.profile_pic_url,
        )
        formatted_text.append("\n")

        # Profile username and ID
        formatted_text.append(
            f"@{self.user.username}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/{self.user.username}",
        )
        formatted_text.append(f" ({self.user.pk})\n")

        # Post count
        formatted_text.append(f"{self.user.media_count} post")
        if self.user.media_count > 1:
            formatted_text.append("s")
        formatted_text.append(", ")
        # Follower count
        formatted_text.append(
            f"{self.user.follower_count}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/{self.user.username}/followers",
        )
        formatted_text.append(" follower")
        if self.user.follower_count > 1:
            formatted_text.append("s")
        formatted_text.append(", ")
        # Following count
        formatted_text.append(
            f"{self.user.following_count}",
            type=MessageEntityType.TEXT_LINK,
            url=f"https://instagram.com/{self.user.username}/following",
        )
        formatted_text.append(" following\n")

        # Full name
        formatted_text.append(f"{self.user.full_name}", type=MessageEntityType.BOLD)
        formatted_text.append("\n")

        # Business account
        if self.user.is_business:
            formatted_text.append(
                f"{self.user.business_category_name}", type=MessageEntityType.ITALIC
            )
            formatted_text.append("\n")

        # Profile biography
        if self.user.biography is not None:
            old_caption = formatted_text.text
            formatted_text.append(self.user.biography)

            # Mentions + Hashtags
            search_caption = (
                f"{old_caption.replace('@', ',')}{self.user.biography}".lower()
            )

            # Mentions in biography
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(caption_mentions(self.user.biography.lower())),
                key=len,
                reverse=True,
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        formatted_text.add_entity(
                            type=MessageEntityType.TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:mention_occurrence]),
                            length=utf16len(f"@{caption_mention}"),
                            url=f"https://instagram.com/{caption_mention}",
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in biography
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(caption_hashtags(self.user.biography.lower())),
                key=len,
                reverse=True,
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_text.add_entity(
                            type=MessageEntityType.TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:hashtag_occurrence]),
                            length=utf16len(f"#{caption_hashtag}"),
                            url=f"https://instagram.com/explore/tags/{caption_hashtag}",
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        # External URL
        if self.user.external_url is not None:
            if self.user.biography is not None:
                formatted_text.append("\n")
            formatted_text.append(
                f"{self.user.external_url}", type=MessageEntityType.BOLD
            )
            formatted_text.append("\n")

        return formatted_text

    def short_caption(self) -> FormattedText:
        return shorten_formatted_text(self.long_caption())
