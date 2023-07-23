#!/usr/bin/env python3
from typing import Optional, Set
from unicodedata import normalize as _uni_normalize


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


def normalize(string: str) -> str:
    """Return a normalized string"""
    return _uni_normalize("NFC", string)


def optional_normalize(string: Optional[str]) -> Optional[str]:
    """Return a normalized string or None if input is None"""
    if string is not None:
        return normalize(string)
    else:
        return None
