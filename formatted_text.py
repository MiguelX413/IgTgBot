#!/usr/bin/env python3
from __future__ import annotations

from typing import List, Optional, Union

from telegram import MessageEntity, User
from telegram.constants import MessageLimit

from exceptions import InvalidMessageEntity
from structures import utf16len

MAX_CAPTION_LENGTH = MessageLimit.CAPTION_LENGTH


class FormattedText:
    text: str
    _entities: List[MessageEntity]

    def __init__(
        self, text: str = "", entities: Optional[List[MessageEntity]] = None
    ) -> None:
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
        type: str,  # pylint: disable=redefined-builtin
        offset: int,
        length: int,
        url: Optional[str] = None,
        user: Optional[User] = None,
        language: Optional[str] = None,
        custom_emoji_id: Optional[str] = None,
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
                custom_emoji_id=custom_emoji_id,
            )
        )

    def append(
        self,
        text: str,
        type: Optional[str] = None,  # pylint: disable=redefined-builtin
        url: Optional[str] = None,
        user: Optional[User] = None,
        language: Optional[str] = None,
        custom_emoji_id: Optional[str] = None,
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
                    custom_emoji_id=custom_emoji_id,
                )
            )
        self.text += text

    def append_text(self, text: Union[FormattedText, str]) -> FormattedText:
        """Append strings or instances of FormattedText"""
        if isinstance(text, str):
            self.text += text

        elif isinstance(text, FormattedText):
            self_utf16len = utf16len(self.text)
            self.text += text.text
            for entity in text._entities:
                self.add_entity(
                    type=entity.type,
                    offset=self_utf16len + entity.offset,
                    length=self_utf16len + entity.length,
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                )

        else:
            raise TypeError("Expected text to be type str or FormattedText")

        return self

    def get_entities_at_offset(self, offset: int) -> List[MessageEntity]:
        entities: List[MessageEntity] = []
        for entity in self._entities:
            if (
                entity.offset
                <= utf16len(self.text[:offset])
                < (entity.offset + entity.length)
            ):
                entities.append(entity)
        return entities

    def __add__(self, other: Union[FormattedText, str]) -> FormattedText:
        if isinstance(other, str):
            return FormattedText(f"{self.text}{other}", self._entities)

        elif isinstance(other, FormattedText):
            self_utf16len = utf16len(self.text)
            formatted_text = FormattedText(f"{self.text}{other.text}", self._entities)
            for entity in other._entities:
                formatted_text.add_entity(
                    type=entity.type,
                    offset=self_utf16len + entity.offset,
                    length=self_utf16len + entity.length,
                    url=entity.url,
                    user=entity.user,
                    language=entity.language,
                )
            return formatted_text

        raise TypeError("Expected other to be type str or FormattedText")

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
