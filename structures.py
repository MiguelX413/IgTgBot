#!/usr/bin/env python3
from typing import NamedTuple, List, Dict, Set

from instaloader import Post, Profile
from telegram import MessageEntity

emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}


class PatchedPost(Post):
    @property
    def context(self):
        return self._context


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class Pair(NamedTuple):
    caption: str
    entities: List[MessageEntity]


class Pairs:
    _post: PatchedPost
    _tagged_users: List[Profile] = []

    def __init__(self, post: PatchedPost):
        self._post = post
        for tagged_user in self._post.tagged_users:
            self._tagged_users.append(
                Profile.from_username(self._post.context, tagged_user)
            )

    def long(self, counter: int = None) -> Pair:
        """Create a Pair object from a given post"""
        # Initializing
        caption: str = ""
        entities: List[MessageEntity] = []

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
                length=utf16len(f"@{self._post.owner_username}"),
                url=f"https://instagram.com/{self._post.owner_username}/",
            )
        )
        caption += f"@{self._post.owner_username} ({self._post.owner_id}): https://instagram.com/p/{self._post.shortcode}/"
        if counter is not None:
            caption += f" {counter + 1}/{self._post.mediacount}"
        caption += "\n"

        # Title
        if self._post.title not in (None, ""):
            caption += f"{self._post.title}\n"

        # Sponsor(s)
        if self._post.is_sponsored:
            caption += "Sponsors:"
            for sponsor_user in self._post.sponsor_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len(f"@{sponsor_user.username}"),
                        url=f"https://instagram.com/{sponsor_user.username}/",
                    )
                )
                caption += f"@{sponsor_user.username} ({sponsor_user.userid})"

            caption += "\n"

        # Tagged Users
        if len(self._tagged_users) > 0:
            caption += emojis["person"]
            for tagged_user in self._tagged_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len(f"@{tagged_user.username}"),
                        url=f"https://instagram.com/{tagged_user.username}/",
                    )
                )
                caption += f"@{tagged_user.username} ({tagged_user.userid})"
            caption += "\n"

        # Location
        if self._post.location is not None:
            entities.append(
                MessageEntity(
                    type="text_link",
                    offset=utf16len(caption + emojis["location"]),
                    length=utf16len(self._post.location.name),
                    url=f"https://instagram.com/explore/locations/{self._post.location.id}/",
                )
            )
            caption += f"{emojis['location']}{self._post.location.name}\n"

        # Views, Likes, and Comments
        if self._post.is_video:
            caption += f"{emojis['eyes']}{self._post.video_view_count} "
        entities.append(
            MessageEntity(
                type="text_link",
                offset=utf16len(caption + emojis["heart"]),
                length=utf16len(str(self._post.likes)),
                url=f"https://instagram.com/p/{self._post.shortcode}/liked_by/",
            )
        )
        caption += f"{emojis['heart']}{self._post.likes} {emojis['comments']}{self._post.comments}\n"

        # Date
        caption += f"{emojis['calendar']}{self._post.date_utc:%Y-%m-%d %H:%M:%S}\n"

        # Post Caption
        if self._post.caption is not None:
            old_caption = caption
            caption += self._post.caption

            # Mentions + Hashtags
            search_caption = (
                old_caption.replace("@", ",") + self._post.caption
            ).lower()

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(self._post.caption_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, f"@{caption_mention}"
                ):
                    if mention_occurrence not in mention_occurrences:
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:mention_occurrence]),
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
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:hashtag_occurrence]),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return Pair(caption, entities)

    def short(self, counter: int = None) -> Pair:
        short_caption: str
        short_entities: List[MessageEntity] = []
        long = self.long(counter)

        if len(long.caption) > 1024:
            short_caption = long.caption[0:1023] + "…"
        else:
            short_caption = long.caption

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
                    short_entities.append(
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
                short_entities.append(
                    MessageEntity(
                        type=long_entity.type,
                        offset=long_entity.offset,
                        length=long_entity.length,
                        url=long_entity.url,
                    )
                )

        return Pair(short_caption, short_entities)
