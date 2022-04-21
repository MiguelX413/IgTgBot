#!/usr/bin/env python3
from typing import NamedTuple, List, Dict, Set, Optional

from instaloader import Post
from telegram import MessageEntity, User
from telegram.constants import MAX_CAPTION_LENGTH

emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


class TaggedUser(NamedTuple):
    full_name: str
    id: int
    is_verified: bool
    profile_pic_url: str
    username: str


class PatchedPost(Post):
    @property
    def context(self):
        return self._context

    @property
    def tagged_users(self) -> List[TaggedUser]:
        """List of all users that are tagged in the Post."""
        try:
            return [
                TaggedUser(
                    edge["node"]["user"]["full_name"],
                    edge["node"]["user"]["id"],
                    edge["node"]["user"]["is_verified"],
                    edge["node"]["user"]["profile_pic_url"],
                    edge["node"]["user"]["username"],
                )
                for edge in self._field("edge_media_to_tagged_user", "edges")
            ]
        except KeyError:
            return []


# def parse_for_shortcodes(text: str) -> list:
#    return


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class FormattedCaption:
    caption: str = ""
    entities: List[MessageEntity] = []

    def __init__(
        self, caption: str = "", entities: Optional[List[MessageEntity]] = None
    ):
        if entities is None:
            entities = []
        self.caption = caption
        self.entities = entities

    def append(
        self,
        text: str,
        type: Optional[str] = None,
        url: Optional[str] = None,
        user: Optional[User] = None,
        language: Optional[str] = None,
    ):
        if type is not None:
            self.entities.append(
                MessageEntity(
                    type=type,
                    offset=utf16len(self.caption),
                    length=utf16len(text),
                    url=url,
                    user=user,
                    language=language,
                )
            )
        self.caption += text


class FormattedCaptions:
    _post: PatchedPost

    def __init__(self, post: PatchedPost):
        self._post = post

    def long(self, counter: Optional[int] = None) -> FormattedCaption:
        """Create a FormattedCaption object from a given post"""
        # Initializing
        formatted_caption = FormattedCaption()

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
        formatted_caption.append("Media", type="text_link", url=media_url)
        formatted_caption.append("\n")

        # Posting account and Counter
        formatted_caption.append(
            f"@{self._post.owner_username}",
            type="text_link",
            url=f"https://instagram.com/{self._post.owner_username}/",
        )
        formatted_caption.append(
            f" ({self._post.owner_id}): https://instagram.com/p/{self._post.shortcode}/"
        )
        if counter is not None:
            formatted_caption.append(f" {counter + 1}/{self._post.mediacount}")
        formatted_caption.append("\n")

        # Title
        if self._post.title not in (None, ""):
            formatted_caption.append(f"{self._post.title}\n")

        # Sponsor(s)
        if self._post.is_sponsored:
            formatted_caption.append("Sponsors:")
            for sponsor_user in self._post.sponsor_users:
                formatted_caption.append(" ")
                formatted_caption.append(
                    f"@{sponsor_user.username}",
                    type="text_link",
                    url=f"https://instagram.com/{sponsor_user.username}/",
                )
                formatted_caption.append(f" ({sponsor_user.userid})")

            formatted_caption.append("\n")

        # Tagged Users
        if len(self._post.tagged_users) > 0:
            formatted_caption.append(emojis["person"])
            for tagged_user in self._post.tagged_users:
                formatted_caption.append(" ")
                formatted_caption.append(
                    f"@{tagged_user.username}",
                    type="text_link",
                    url=f"https://instagram.com/{tagged_user.username}/",
                )
                formatted_caption.append(f" ({tagged_user.id})")
            formatted_caption.append("\n")

        # Location
        if self._post.location is not None:
            formatted_caption.append(emojis["location"])
            formatted_caption.append(
                f"{self._post.location.name}",
                type="text_link",
                url=f"https://instagram.com/explore/locations/{self._post.location.id}/",
            )
            formatted_caption.append("\n")

        # Views, Likes, and Comments
        if self._post.is_video:
            formatted_caption.append(f"{emojis['eyes']}{self._post.video_view_count} ")
        formatted_caption.append(emojis["heart"])
        formatted_caption.append(
            f"{self._post.likes}",
            type="text_link",
            url=f"https://instagram.com/p/{self._post.shortcode}/liked_by/",
        )
        formatted_caption.append(f" {emojis['comments']}{self._post.comments}\n")

        # Date
        formatted_caption.append(
            f"{emojis['calendar']}{self._post.date_utc:%Y-%m-%d %H:%M:%S}\n"
        )

        # Post Caption
        if self._post.caption is not None:
            old_caption = formatted_caption.caption
            formatted_caption.append(self._post.caption)

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
                        formatted_caption.entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(
                                    formatted_caption.caption[0:mention_occurrence]
                                ),
                                length=utf16len(f"@{caption_mention}"),
                                url=f"https://instagram.com/{caption_mention}/",
                            )
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
                        formatted_caption.entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(
                                    formatted_caption.caption[0:hashtag_occurrence]
                                ),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_caption

    def short(self, counter: Optional[int] = None) -> FormattedCaption:
        formatted_caption = FormattedCaption()
        long = self.long(counter)

        if len(long.caption) > MAX_CAPTION_LENGTH:
            formatted_caption.caption = f"{long.caption[0 : MAX_CAPTION_LENGTH - 1]}…"
        else:
            formatted_caption.caption = long.caption

        for long_entity in list(long.entities):
            if (
                len(
                    long.caption.encode("UTF-16-le")[
                        0 : 2 * (long_entity.offset + long_entity.length)
                    ].decode("UTF-16-le")
                )
                > MAX_CAPTION_LENGTH
            ):
                if (
                    len(
                        long.caption.encode("UTF-16-le")[
                            0 : 2 * long_entity.offset
                        ].decode("UTF-16-le")
                    )
                    < MAX_CAPTION_LENGTH
                ):
                    formatted_caption.entities.append(
                        MessageEntity(
                            type=long_entity.type,
                            offset=long_entity.offset,
                            length=utf16len(
                                long.caption[: MAX_CAPTION_LENGTH - 1]
                                .encode("UTF-16-le")[2 * long_entity.offset :]
                                .decode("UTF-16-le")
                            ),
                            url=long_entity.url,
                        )
                    )
            else:
                formatted_caption.entities.append(
                    MessageEntity(
                        type=long_entity.type,
                        offset=long_entity.offset,
                        length=long_entity.length,
                        url=long_entity.url,
                    )
                )

        return formatted_caption
