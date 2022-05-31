#!/usr/bin/env python3
from __future__ import annotations

from typing import List, NamedTuple, Optional, Set
from unicodedata import normalize

from telegram import MessageEntity, User
from telegram.constants import MAX_CAPTION_LENGTH

from exceptions import InvalidMessageEntity


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
