#!/usr/bin/env python3
from typing import Dict, Optional, Set

from telegram.constants import (
    MESSAGEENTITY_BOLD,
    MESSAGEENTITY_ITALIC,
    MESSAGEENTITY_TEXT_LINK,
)

from instaloader_patches import PatchedPost, PatchedProfile, PatchedStoryItem
from structures import FormattedText, shorten_formatted_text, utf16len

emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


def find_occurrences(string: str, substring: str) -> Set[int]:
    """Returns the multiple occurrences of a substring in a string"""
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class PostCaptions:
    _post: PatchedPost

    def __init__(self, post: PatchedPost) -> None:
        self._post = post

    def long_caption(self, counter: Optional[int] = None) -> FormattedText:
        """Create a FormattedText object from a given post"""
        # Initializing
        formatted_text = FormattedText()

        # Media URL
        if counter is None:
            if self._post.typename == "GraphVideo":
                media_url = self._post.video_url
            else:
                media_url = self._post.url
        else:
            node = list(self._post.get_sidecar_nodes(counter, counter))[0]
            if node.is_video:
                media_url = node.video_url
            else:
                media_url = node.display_url
        formatted_text.append("Media", type=MESSAGEENTITY_TEXT_LINK, url=media_url)
        formatted_text.append("\n")

        # Posting account, post url, and counter
        formatted_text.append(
            f"@{self._post.owner_username}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._post.owner_username}/",
        )
        formatted_text.append(
            f" ({self._post.owner_id}): https://instagram.com/p/{self._post.shortcode}/"
        )
        if counter is not None:
            formatted_text.append(f" {counter + 1}/{self._post.mediacount}")
        formatted_text.append("\n")

        # Title
        if self._post.title not in (None, ""):
            formatted_text.append(f"{self._post.title}\n")

        # Sponsor(s)
        if self._post.is_sponsored:
            formatted_text.append("Sponsors:")
            for sponsor_user in self._post.sponsor_users:
                formatted_text.append(" ")
                formatted_text.append(
                    f"@{sponsor_user.username}",
                    type=MESSAGEENTITY_TEXT_LINK,
                    url=f"https://instagram.com/{sponsor_user.username}/",
                )
                formatted_text.append(f" ({sponsor_user.userid})")

            formatted_text.append("\n")

        # Tagged Users
        if len(self._post.patched_tagged_users) > 0:
            formatted_text.append(emojis["person"])
            for tagged_user in self._post.patched_tagged_users:
                formatted_text.append(" ")
                formatted_text.append(
                    f"@{tagged_user.username}",
                    type=MESSAGEENTITY_TEXT_LINK,
                    url=f"https://instagram.com/{tagged_user.username}/",
                )
                formatted_text.append(f" ({tagged_user.id})")
            formatted_text.append("\n")

        # Location
        if self._post.location is not None:
            formatted_text.append(emojis["location"])
            formatted_text.append(
                f"{self._post.location.name}",
                type=MESSAGEENTITY_TEXT_LINK,
                url=f"https://instagram.com/explore/locations/{self._post.location.id}/",
            )
            formatted_text.append("\n")

        # Views, Likes, and Comments
        if self._post.is_video:
            formatted_text.append(f"{emojis['eyes']}{self._post.video_view_count} ")
        formatted_text.append(emojis["heart"])
        formatted_text.append(
            f"{self._post.likes}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/p/{self._post.shortcode}/liked_by/",
        )
        formatted_text.append(f" {emojis['comments']}{self._post.comments}\n")

        # Date
        formatted_text.append(
            f"{emojis['calendar']}{self._post.date_utc:%Y-%m-%d %H:%M:%S}\n"
        )

        # Post Caption
        if self._post.caption is not None:
            old_caption = formatted_text.text
            formatted_text.append(self._post.caption)

            # Mentions + Hashtags
            search_caption = (
                f"{old_caption.replace('@', ',')}{self._post.caption}".lower()
            )

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(self._post.caption_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:mention_occurrence]),
                            length=utf16len(f"@{caption_mention}"),
                            url=f"https://instagram.com/{caption_mention}/",
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in caption
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(self._post.caption_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:hashtag_occurrence]),
                            length=utf16len(f"#{caption_hashtag}"),
                            url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_text

    def short_caption(self, counter: Optional[int] = None) -> FormattedText:
        return shorten_formatted_text(self.long_caption(counter))


class StoryItemCaptions:
    _story_item: PatchedStoryItem

    def __init__(self, story_item: PatchedStoryItem) -> None:
        self._story_item = story_item

    def long_caption(self) -> FormattedText:
        """Create a FormattedText object from a given post"""
        # Initializing
        formatted_text = FormattedText()

        # Media URL
        if self._story_item.is_video:
            media_url = self._story_item.video_url
        else:
            media_url = self._story_item.url
        formatted_text.append("Media", type=MESSAGEENTITY_TEXT_LINK, url=media_url)
        formatted_text.append("\n")

        # Posting account and story item url
        formatted_text.append(
            f"@{self._story_item.owner_username}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._story_item.owner_username}/",
        )
        formatted_text.append(
            f" ({self._story_item.owner_id}): https://instagram.com"
            f"/stories/{self._story_item.owner_username}/{self._story_item.mediaid}/"
        )
        formatted_text.append("\n")

        # Date
        formatted_text.append(
            f"{emojis['calendar']}{self._story_item.date_utc:%Y-%m-%d %H:%M:%S}\n"
        )

        # Story item Caption
        if self._story_item.caption is not None:
            old_caption = formatted_text.text
            formatted_text.append(self._story_item.caption)

            # Mentions + Hashtags
            search_caption = (
                f"{old_caption.replace('@', ',')}{self._story_item.caption}".lower()
            )

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(self._story_item.caption_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:mention_occurrence]),
                            length=utf16len(f"@{caption_mention}"),
                            url=f"https://instagram.com/{caption_mention}/",
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in caption
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(self._story_item.caption_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:hashtag_occurrence]),
                            length=utf16len(f"#{caption_hashtag}"),
                            url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_text

    def short_caption(self) -> FormattedText:
        return shorten_formatted_text(self.long_caption())


class ProfileCaptions:
    _profile: PatchedProfile

    def __init__(self, profile: PatchedProfile) -> None:
        self._profile = profile

    def long_caption(self) -> FormattedText:
        """Create a FormattedText object from a given profile"""
        # Initializing
        formatted_text = FormattedText()

        # URL to profile picture
        formatted_text.append(
            "Profile Picture",
            type=MESSAGEENTITY_TEXT_LINK,
            url=self._profile.profile_pic_url,
        )
        formatted_text.append("\n")

        # Profile username and ID
        formatted_text.append(
            f"@{self._profile.username}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/",
        )
        formatted_text.append(f" ({self._profile.userid})\n")

        # Post count
        formatted_text.append(f"{self._profile.mediacount} post")
        if self._profile.mediacount > 1:
            formatted_text.append("s")
        formatted_text.append(", ")
        # Follower count
        formatted_text.append(
            f"{self._profile.followers}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/followers/",
        )
        formatted_text.append(" follower")
        if self._profile.followers > 1:
            formatted_text.append("s")
        formatted_text.append(", ")
        # Following count
        formatted_text.append(
            f"{self._profile.followees}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/following/",
        )
        formatted_text.append(" following\n")

        # IGTV count
        if self._profile.igtvcount > 0:
            formatted_text.append(
                f"{self._profile.igtvcount}",
                type=MESSAGEENTITY_TEXT_LINK,
                url=f"https://instagram.com/{self._profile.username}/channel/",
            )
            formatted_text.append(" IGTV post")
            if self._profile.igtvcount > 1:
                formatted_text.append("s")
            formatted_text.append("\n")

        # Full name
        formatted_text.append(f"{self._profile.full_name}", type=MESSAGEENTITY_BOLD)
        formatted_text.append("\n")

        # Business account
        if self._profile.is_business_account:
            formatted_text.append(
                f"{self._profile.business_category_name}", type=MESSAGEENTITY_ITALIC
            )
            formatted_text.append("\n")

        # Profile biography
        if self._profile.biography is not None:
            old_caption = formatted_text.text
            formatted_text.append(self._profile.biography)

            # Mentions + Hashtags
            search_caption = (
                f"{old_caption.replace('@', ',')}{self._profile.biography}".lower()
            )

            # Mentions in biography
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(self._profile.biography_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:mention_occurrence]),
                            length=utf16len(f"@{caption_mention}"),
                            url=f"https://instagram.com/{caption_mention}/",
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in biography
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(self._profile.biography_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_text.add_entity(
                            type=MESSAGEENTITY_TEXT_LINK,
                            offset=utf16len(formatted_text.text[0:hashtag_occurrence]),
                            length=utf16len(f"#{caption_hashtag}"),
                            url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        # External URL
        if self._profile.external_url is not None:
            if self._profile.biography is not None:
                formatted_text.append("\n")
            formatted_text.append(
                f"{self._profile.external_url}", type=MESSAGEENTITY_BOLD
            )
            formatted_text.append("\n")

        return formatted_text

    def short_caption(self) -> FormattedText:
        return shorten_formatted_text(self.long_caption())
