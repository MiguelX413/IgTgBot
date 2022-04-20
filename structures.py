#!/usr/bin/env python3
from typing import NamedTuple, List, Dict, Set, Optional

from instaloader import Post
from telegram import MessageEntity, User

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


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class Pair:
    caption: str
    entities: List[MessageEntity]

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
        type: Optional[str] = None,  # pylint: disable=W0622
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


class SuperPost:
    _post: PatchedPost
    _media_url: str = None

    def __init__(self, post: PatchedPost):
        self._post = post

    @property
    def post(self) -> PatchedPost:
        return self._post

    def get_media_url(self, counter: Optional[int] = None) -> str:
        if self._media_url is None:
            if counter is None:
                if self._post.typename == "GraphVideo":
                    self._media_url = self._post.video_url
                else:
                    self._media_url = self._post.url
            else:
                node = list(self._post.get_sidecar_nodes(counter, counter))[0]
                if node.is_video:
                    self._media_url = node.video_url
                else:
                    self._media_url = node.display_url
        return self._media_url

    def long(self, counter: Optional[int] = None) -> Pair:
        """Create a Pair object from a given post"""
        # Initializing
        pair = Pair()

        # Media URL
        pair.append("Media", type="text_link", url=self.get_media_url(counter))
        pair.append("\n")

        # Posting account and Counter
        pair.append(
            f"@{self._post.owner_username}",
            type="text_link",
            url=f"https://instagram.com/{self._post.owner_username}/",
        )
        pair.append(
            f" ({self._post.owner_id}): https://instagram.com/p/{self._post.shortcode}/"
        )
        if counter is not None:
            pair.append(f" {counter + 1}/{self._post.mediacount}")
        pair.append("\n")

        # Title
        if self._post.title not in (None, ""):
            pair.append(f"{self._post.title}\n")

        # Sponsor(s)
        if self._post.is_sponsored:
            pair.append("Sponsors:")
            for sponsor_user in self._post.sponsor_users:
                pair.append(" ")
                pair.append(
                    f"@{sponsor_user.username}",
                    type="text_link",
                    url=f"https://instagram.com/{sponsor_user.username}/",
                )
                pair.append(f" ({sponsor_user.userid})")

            pair.append("\n")

        # Tagged Users
        if len(self._post.tagged_users) > 0:
            pair.append(emojis["person"])
            for tagged_user in self._post.tagged_users:
                pair.append(" ")
                pair.append(
                    f"@{tagged_user.username}",
                    type="text_link",
                    url=f"https://instagram.com/{tagged_user.username}/",
                )
                pair.append(f" ({tagged_user.id})")
            pair.append("\n")

        # Location
        if self._post.location is not None:
            pair.append(emojis["location"])
            pair.append(
                f"{self._post.location.name}",
                type="text_link",
                url=f"https://instagram.com/explore/locations/{self._post.location.id}/",
            )
            pair.append("\n")

        # Views, Likes, and Comments
        if self._post.is_video:
            pair.append(f"{emojis['eyes']}{self._post.video_view_count} ")
        pair.append(emojis["heart"])
        pair.append(
            f"{self._post.likes}",
            type="text_link",
            url=f"https://instagram.com/p/{self._post.shortcode}/liked_by/",
        )
        pair.append(f" {emojis['comments']}{self._post.comments}\n")

        # Date
        pair.append(f"{emojis['calendar']}{self._post.date_utc:%Y-%m-%d %H:%M:%S}\n")

        # Post Caption
        if self._post.caption is not None:
            old_caption = pair.caption
            pair.append(self._post.caption)

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
                        pair.entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(pair.caption[0:mention_occurrence]),
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
                        pair.entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(pair.caption[0:hashtag_occurrence]),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return pair

    def short(self, counter: Optional[int] = None) -> Pair:
        pair = Pair()
        long = self.long(counter)

        if len(long.caption) > 1024:
            pair.caption = f"{long.caption[0:1023]}…"
        else:
            pair.caption = long.caption

        for long_entity in list(long.entities):
            if (
                len(
                    long.caption.encode("UTF-16-le")[
                        0 : 2 * (long_entity.offset + long_entity.length)
                    ].decode("UTF-16-le")
                )
                > 1024
            ):
                if (
                    len(
                        long.caption.encode("UTF-16-le")[
                            0 : 2 * long_entity.offset
                        ].decode("UTF-16-le")
                    )
                    < 1024
                ):
                    pair.entities.append(
                        MessageEntity(
                            type=long_entity.type,
                            offset=long_entity.offset,
                            length=utf16len(
                                long.caption[:1023]
                                .encode("UTF-16-le")[2 * long_entity.offset :]
                                .decode("UTF-16-le")
                            ),
                            url=long_entity.url,
                        )
                    )
            else:
                pair.entities.append(
                    MessageEntity(
                        type=long_entity.type,
                        offset=long_entity.offset,
                        length=long_entity.length,
                        url=long_entity.url,
                    )
                )

        return pair
