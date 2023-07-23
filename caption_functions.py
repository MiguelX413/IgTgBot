#!/usr/bin/env python3
from typing import List, Optional


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


def caption_hashtags(caption: Optional[str]) -> List[str]:
    if caption is None:
        return []
    return hashtag_regex.findall(caption)


def caption_mentions(caption: Optional[str]) -> List[str]:
    if caption is None:
        return []
    return mention_regex.findall(caption)
