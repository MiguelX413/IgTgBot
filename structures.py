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


def utf16len(string: str) -> int:
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


class Pairs(NamedTuple):
    long_caption: str = ""
    long_entities: List[MessageEntity] = []

    @classmethod
    def from_post(cls, input_post: Post, counter: int = None):
        """Create a Pair object from a given post"""
        # Initializing
        caption: str = ""
        entities: List[MessageEntity] = []

        # Media URL
        if counter is None:
            if input_post.typename == "GraphVideo":
                media_url = input_post.video_url
            else:
                media_url = input_post.url
        else:
            node = list(input_post.get_sidecar_nodes(counter, counter))[0]
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
                length=utf16len("@" + input_post.owner_username),
                url="https://instagram.com/" + input_post.owner_username + "/",
            )
        )
        caption += (
            "@"
            + input_post.owner_username
            + " ("
            + str(input_post.owner_id)
            + ")"
            + ": "
            + "https://instagram.com/p/"
            + input_post.shortcode
            + "/"
            + (
                (" " + str(counter + 1) + "/" + str(input_post.mediacount) + "\n")
                if counter is not None
                else "\n"
            )
        )

        # Title
        if input_post.title not in (None, ""):
            caption += input_post.title + "\n"

        # Sponsor(s)
        if input_post.is_sponsored:
            caption += "Sponsors:"
            for sponsor_user in input_post.sponsor_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len("@" + sponsor_user.username),
                        url="https://instagram.com/" + sponsor_user.username + "/",
                    )
                )
                caption += (
                    "@" + sponsor_user.username + " (" + str(sponsor_user.userid) + ")"
                )
            caption += "\n"

        # Tagged Users
        if len(input_post.tagged_users) > 0:
            caption += emojis["person"]
            for tagged_user in input_post.tagged_users:
                caption += " "
                entities.append(
                    MessageEntity(
                        type="text_link",
                        offset=utf16len(caption),
                        length=utf16len("@" + tagged_user),
                        url="https://instagram.com/" + tagged_user + "/",
                    )
                )
                caption += (
                    "@"
                    + tagged_user
                    + " ("
                    + str(Profile.from_username(input_post.context, tagged_user).userid)
                    + ")"
                )
            caption += "\n"

        # Location
        if input_post.location is not None:
            entities.append(
                MessageEntity(
                    type="text_link",
                    offset=utf16len(caption + emojis["location"]),
                    length=utf16len(str(input_post.location.name)),
                    url="https://instagram.com/explore/locations/"
                    + str(input_post.location.id)
                    + "/",
                )
            )
            caption += emojis["location"] + str(input_post.location.name) + "\n"

        # Views, Likes, and Comments
        if input_post.is_video:
            caption += emojis["eyes"] + str(input_post.video_view_count) + " "
        entities.append(
            MessageEntity(
                type="text_link",
                offset=utf16len(caption + emojis["heart"]),
                length=utf16len(str(input_post.likes)),
                url="https://instagram.com/p/" + input_post.shortcode + "/liked_by/",
            )
        )
        caption += (
            emojis["heart"]
            + str(input_post.likes)
            + " "
            + emojis["comments"]
            + str(input_post.comments)
            + "\n"
        )

        # Date
        caption += (
            emojis["calendar"] + f"{input_post.date_utc:%Y-%m-%d %H:%M:%S}" + "\n"
        )

        # Post Caption
        if input_post.caption is not None:
            old_caption = caption
            caption += input_post.caption

            # Mentions + Hashtags
            search_caption = (
                old_caption.replace("@", ",") + input_post.caption
            ).lower()

            # Mentions in caption
            mention_occurrences: Set[int] = set()
            for caption_mention in sorted(
                set(input_post.caption_mentions), key=len, reverse=True
            ):
                for mention_occurrence in find_occurrences(
                    search_caption, "@" + caption_mention
                ):
                    if mention_occurrence not in mention_occurrences:
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:mention_occurrence]),
                                length=utf16len("@" + caption_mention),
                                url="https://instagram.com/" + caption_mention + "/",
                            )
                        )
                    mention_occurrences.add(mention_occurrence)

            # Hashtags in caption
            hashtag_occurrences: Set[int] = set()
            for caption_hashtag in sorted(
                set(input_post.caption_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, "#" + caption_hashtag
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        entities.append(
                            MessageEntity(
                                type="text_link",
                                offset=utf16len(caption[0:hashtag_occurrence]),
                                length=utf16len("#" + caption_hashtag),
                                url="https://instagram.com/explore/tags/"
                                + caption_hashtag
                                + "/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return cls(caption, entities)

    @property
    def short_caption(self) -> str:
        if len(self.long_caption) > 1024:
            return self.long_caption[0:1023] + "…"
        else:
            return self.long_caption

    @property
    def short_entities(self) -> List[MessageEntity]:
        short_entities: List[MessageEntity] = []
        for long_entity in list(self.long_entities):
            if (
                len(
                    self.long_caption.encode("UTF-16-le")[
                        0 : 2 * (long_entity.offset + long_entity.length)
                    ].decode("UTF-16-le")
                )
                > 1024
            ):
                if (
                    len(
                        self.long_caption.encode("UTF-16-le")[
                            0 : 2 * long_entity.offset
                        ].decode("UTF-16-le")
                    )
                    < 1024
                ):
                    short_entities.append(
                        MessageEntity(
                            long_entity.type,
                            long_entity.offset,
                            len(
                                self.long_caption[:1023]
                                .encode("UTF-16-le")[2 * long_entity.offset :]
                                .decode("UTF-16-le")
                            ),
                            long_entity.url,
                        )
                    )
            else:
                short_entities.append(
                    MessageEntity(
                        long_entity.type,
                        long_entity.offset,
                        long_entity.length,
                        long_entity.url,
                    )
                )
        return short_entities
