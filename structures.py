#!/usr/bin/env python3
from __future__ import annotations

from typing import List, NamedTuple, Optional, Set
from unicodedata import normalize

from instaloader import InstaloaderContext, Post, Profile, StoryItem
from telegram import MessageEntity, User
from telegram.constants import MAX_CAPTION_LENGTH

from exceptions import InvalidMessageEntity

try:
    import regex as re

except ImportError:
    print("Could not find regex module, using built-in re.")
    import re  # type: ignore[no-redef]

    hashtag_regex = re.compile(r"(?:#)((?:\w){1,150})")

else:
    hashtag_regex = re.compile(r"(?:#)((?:\w|\p{Extended_Pictographic}){1,150})")


mention_regex = re.compile(
    r"(?:@)(?!\d+$)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)", re.ASCII
)

# def parse_for_shortcodes(text: str) -> List[str]:
#    return


def utf16len(string: str) -> int:
    """Returns the UTF-16 length of a string."""
    return len(string.encode("UTF-16-le")) // 2


def find_occurrences(string: str, substring: str) -> Set[int]:
    """Returns the multiple occurrences of a substring in a string"""
    offsets: Set[int] = set()
    pos: int = string.find(substring)
    while pos != -1:
        offsets.add(pos)
        pos = string.find(substring, pos + 1)
    return offsets


def optional_normalize(string: Optional[str]) -> Optional[str]:
    """Return a normalized string or None if input is None"""
    if string is not None:
        return normalize("NFC", string)
    else:
        return None


class TaggedUser(NamedTuple):
    full_name: str
    id: int
    is_verified: bool
    profile_pic_url: str
    username: str


class PatchedPost(Post):
    @property
    def caption(self) -> Optional[str]:
        """Caption."""
        if (
            "edge_media_to_caption" in self._node
            and self._node["edge_media_to_caption"]["edges"]
        ):
            return optional_normalize(
                self._node["edge_media_to_caption"]["edges"][0]["node"]["text"]
            )
        elif "caption" in self._node:
            return optional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        return hashtag_regex.findall(self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        return mention_regex.findall(self.caption.lower())

    @property
    def context(self) -> InstaloaderContext:
        """Return the Instaloader context used for this post"""
        return self._context

    @property
    def owner_username(self) -> str:
        """The Post's lowercase owner name."""
        # Check if owner username data already available in post data
        if "owner" in self._node and "username" in self._node["owner"]:
            return self._node["owner"]["username"]
        else:
            return self.owner_profile.username

    @property
    def patched_tagged_users(self) -> List[TaggedUser]:
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


class PatchedStoryItem(StoryItem):
    @property
    def owner_username(self) -> str:
        """The StoryItem owner's lowercase name."""
        if "owner" in self._node and "username" in self._node["owner"]:
            return self._node["owner"]["username"]
        else:
            return self.owner_profile.username

    @property
    def owner_id(self) -> int:
        """The ID of the StoryItem owner."""
        if "owner" in self._node and "id" in self._node["owner"]:
            return self._node["owner"]["id"]
        else:
            return self.owner_profile.userid

    @property
    def caption(self) -> Optional[str]:
        """Caption."""
        if (
            "edge_media_to_caption" in self._node
            and self._node["edge_media_to_caption"]["edges"]
        ):
            return optional_normalize(
                self._node["edge_media_to_caption"]["edges"][0]["node"]["text"]
            )
        elif "caption" in self._node:
            return optional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        return hashtag_regex.findall(self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        return mention_regex.findall(self.caption.lower())


class PatchedProfile(Profile):
    @property
    def biography(self) -> str:
        return normalize("NFC", self._metadata("biography"))

    @property
    def biography_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Profile's biography."""
        if not self.biography:
            return []
        return hashtag_regex.findall(self.biography.lower())

    @property
    def biography_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Profile's biography, without preceeding @."""
        if not self.biography:
            return []
        return mention_regex.findall(self.biography.lower())


class FormattedText:
    text: str
    _entities: List[MessageEntity]

    def __init__(self, text: str = "", entities=None) -> None:
        if entities is None:
            entities = []

        self.text = text
        for entity in entities:
            if (entity.offset + entity.length) > utf16len(self.text):
                raise InvalidMessageEntity
        self._entities = entities

    @property
    def entities(self) -> List[MessageEntity]:
        return list(self._entities)

    def add_entity(
        self,
        type: str,  # pylint: disable=W0622
        offset: int,
        length: int,
        url: Optional[str] = None,
        user: Optional[User] = None,
        language: Optional[str] = None,
    ) -> None:
        if (offset + length) > utf16len(self.text):
            raise InvalidMessageEntity

        self._entities.append(
            MessageEntity(
                type=type,
                offset=offset,
                length=length,
                url=url,
                user=user,
                language=language,
            )
        )

    def append(
        self,
        text: str,
        type: Optional[str] = None,  # pylint: disable=W0622
        url: Optional[str] = None,
        user: Optional[User] = None,
        language: Optional[str] = None,
    ) -> None:
        if type is not None:
            self._entities.append(
                MessageEntity(
                    type=type,
                    offset=utf16len(self.text),
                    length=utf16len(text),
                    url=url,
                    user=user,
                    language=language,
                )
            )
        self.text += text

    def __add__(self, other: FormattedText) -> FormattedText:
        self_utf16len = utf16len(self.text)
        formatted_text = FormattedText(f"{self.text}{other.text}", self.entities)

        for entity in other.entities:
            formatted_text.add_entity(
                type=entity.type,
                offset=self_utf16len + entity.offset,
                length=self_utf16len + entity.length,
                url=entity.url,
                user=entity.user,
                language=entity.language,
            )

        return formatted_text

    def __len__(self) -> int:
        return len(self.text)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text={self.text!r}, entities={self._entities!r})"

    def __str__(self) -> str:
        return self.text


def shorten_formatted_text(
    formatted_text: FormattedText, length: int = MAX_CAPTION_LENGTH
) -> FormattedText:
    output_formatted_text = FormattedText()

    if len(formatted_text.text) > length:
        output_formatted_text.text = f"{formatted_text.text[0: length - 1]}…"
    else:
        output_formatted_text.text = formatted_text.text

    for long_entity in list(formatted_text.entities):
        if (
            len(
                formatted_text.text.encode("UTF-16-le")[
                    0 : 2 * (long_entity.offset + long_entity.length)
                ].decode("UTF-16-le")
            )
            > length
        ):
            if (
                len(
                    formatted_text.text.encode("UTF-16-le")[
                        0 : 2 * long_entity.offset
                    ].decode("UTF-16-le")
                )
                < length
            ):
                output_formatted_text.add_entity(
                    type=long_entity.type,
                    offset=long_entity.offset,
                    length=utf16len(
                        formatted_text.text[: length - 1]
                        .encode("UTF-16-le")[2 * long_entity.offset :]
                        .decode("UTF-16-le")
                    ),
                    url=long_entity.url,
                    user=long_entity.user,
                    language=long_entity.language,
                )
        else:
            output_formatted_text.add_entity(
                type=long_entity.type,
                offset=long_entity.offset,
                length=long_entity.length,
                url=long_entity.url,
                user=long_entity.user,
                language=long_entity.language,
            )

    return output_formatted_text
