#!/usr/bin/env python3
import re
from typing import NamedTuple, List, Dict, Set, Optional
from unicodedata import normalize

from instaloader import Post, InstaloaderContext, StoryItem, Profile
from telegram import MessageEntity, User
from telegram.constants import (
    MAX_CAPTION_LENGTH,
    MESSAGEENTITY_TEXT_LINK,
    MESSAGEENTITY_BOLD,
    MESSAGEENTITY_ITALIC,
)

emojis: Dict[str, str] = {
    "person": "👤",
    "location": "📍",
    "eyes": "👀",
    "heart": "❤️",
    "comments": "💬",
    "calendar": "📅",
}

hashtag_regex = re.compile(r"(?:#)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)")
mention_regex = re.compile(
    r"(?:^|\W|_)(?:@)(\w(?:(?:\w|(?:\.(?!\.))){0,28}(?:\w))?)", re.ASCII
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


def conditional_normalize(string: Optional[str]) -> Optional[str]:
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
            return conditional_normalize(
                self._node["edge_media_to_caption"]["edges"][0]["node"]["text"]
            )
        elif "caption" in self._node:
            return conditional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        return re.findall(hashtag_regex, self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        return re.findall(mention_regex, self.caption.lower())

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
            return conditional_normalize(
                self._node["edge_media_to_caption"]["edges"][0]["node"]["text"]
            )
        elif "caption" in self._node:
            return conditional_normalize(self._node["caption"])
        return None

    @property
    def caption_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Post's caption."""
        if not self.caption:
            return []
        return re.findall(hashtag_regex, self.caption.lower())

    @property
    def caption_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Post's caption, without preceeding @."""
        if not self.caption:
            return []
        return re.findall(mention_regex, self.caption.lower())


class PatchedProfile(Profile):
    @property
    def biography(self) -> str:
        return conditional_normalize(self._metadata("biography"))

    @property
    def biography_hashtags(self) -> List[str]:
        """List of all lowercased hashtags (without preceeding #) that occur in the Profile's biography."""
        if not self.biography:
            return []
        return re.findall(hashtag_regex, self.biography.lower())

    @property
    def biography_mentions(self) -> List[str]:
        """List of all lowercased profiles that are mentioned in the Profile's biography, without preceeding @."""
        if not self.biography:
            return []
        return re.findall(mention_regex, self.biography.lower())


class FormattedCaption:
    caption: str = ""
    entities: List[MessageEntity] = []

    def __init__(
        self, caption: str = "", entities: Optional[List[MessageEntity]] = None
    ) -> None:
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
    ) -> None:
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


def shorten_formatted_caption(
    formatted_caption: FormattedCaption, length: int = MAX_CAPTION_LENGTH
) -> FormattedCaption:
    output_formatted_caption = FormattedCaption()

    if len(formatted_caption.caption) > length:
        output_formatted_caption.caption = (
            f"{formatted_caption.caption[0 : length - 1]}…"
        )
    else:
        output_formatted_caption.caption = formatted_caption.caption

    for long_entity in list(formatted_caption.entities):
        if (
            len(
                formatted_caption.caption.encode("UTF-16-le")[
                    0 : 2 * (long_entity.offset + long_entity.length)
                ].decode("UTF-16-le")
            )
            > length
        ):
            if (
                len(
                    formatted_caption.caption.encode("UTF-16-le")[
                        0 : 2 * long_entity.offset
                    ].decode("UTF-16-le")
                )
                < length
            ):
                output_formatted_caption.entities.append(
                    MessageEntity(
                        type=long_entity.type,
                        offset=long_entity.offset,
                        length=utf16len(
                            formatted_caption.caption[: length - 1]
                            .encode("UTF-16-le")[2 * long_entity.offset :]
                            .decode("UTF-16-le")
                        ),
                        url=long_entity.url,
                        user=long_entity.user,
                        language=long_entity.language,
                    )
                )
        else:
            output_formatted_caption.entities.append(
                MessageEntity(
                    type=long_entity.type,
                    offset=long_entity.offset,
                    length=long_entity.length,
                    url=long_entity.url,
                    user=long_entity.user,
                    language=long_entity.language,
                )
            )

    return output_formatted_caption


class PostCaptions:
    _post: PatchedPost

    def __init__(self, post: PatchedPost) -> None:
        self._post = post

    def long_caption(self, counter: Optional[int] = None) -> FormattedCaption:
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
        formatted_caption.append("Media", type=MESSAGEENTITY_TEXT_LINK, url=media_url)
        formatted_caption.append("\n")

        # Posting account, post url, and counter
        formatted_caption.append(
            f"@{self._post.owner_username}",
            type=MESSAGEENTITY_TEXT_LINK,
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
                    type=MESSAGEENTITY_TEXT_LINK,
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
                    type=MESSAGEENTITY_TEXT_LINK,
                    url=f"https://instagram.com/{tagged_user.username}/",
                )
                formatted_caption.append(f" ({tagged_user.id})")
            formatted_caption.append("\n")

        # Location
        if self._post.location is not None:
            formatted_caption.append(emojis["location"])
            formatted_caption.append(
                f"{self._post.location.name}",
                type=MESSAGEENTITY_TEXT_LINK,
                url=f"https://instagram.com/explore/locations/{self._post.location.id}/",
            )
            formatted_caption.append("\n")

        # Views, Likes, and Comments
        if self._post.is_video:
            formatted_caption.append(f"{emojis['eyes']}{self._post.video_view_count} ")
        formatted_caption.append(emojis["heart"])
        formatted_caption.append(
            f"{self._post.likes}",
            type=MESSAGEENTITY_TEXT_LINK,
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
                                type=MESSAGEENTITY_TEXT_LINK,
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
                                type=MESSAGEENTITY_TEXT_LINK,
                                offset=utf16len(
                                    formatted_caption.caption[0:hashtag_occurrence]
                                ),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_caption

    def short_caption(self, counter: Optional[int] = None) -> FormattedCaption:
        return shorten_formatted_caption(self.long_caption(counter))


class StoryItemCaptions:
    _story_item: PatchedStoryItem

    def __init__(self, story_item: PatchedStoryItem) -> None:
        self._story_item = story_item

    def long_caption(self) -> FormattedCaption:
        """Create a FormattedCaption object from a given post"""
        # Initializing
        formatted_caption = FormattedCaption()

        # Media URL
        if self._story_item.is_video:
            media_url = self._story_item.video_url
        else:
            media_url = self._story_item.url
        formatted_caption.append("Media", type=MESSAGEENTITY_TEXT_LINK, url=media_url)
        formatted_caption.append("\n")

        # Posting account and story item url
        formatted_caption.append(
            f"@{self._story_item.owner_username}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._story_item.owner_username}/",
        )
        formatted_caption.append(
            f" ({self._story_item.owner_id}): https://instagram.com/stories/{self._story_item.owner_username}/{self._story_item.mediaid}/"
        )
        formatted_caption.append("\n")

        # Date
        formatted_caption.append(
            f"{emojis['calendar']}{self._story_item.date_utc:%Y-%m-%d %H:%M:%S}\n"
        )

        # Story item Caption
        if self._story_item.caption is not None:
            old_caption = formatted_caption.caption
            formatted_caption.append(self._story_item.caption)

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
                        formatted_caption.entities.append(
                            MessageEntity(
                                type=MESSAGEENTITY_TEXT_LINK,
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
                set(self._story_item.caption_hashtags), key=len, reverse=True
            ):
                for hashtag_occurrence in find_occurrences(
                    search_caption, f"#{caption_hashtag}"
                ):
                    if hashtag_occurrence not in hashtag_occurrences:
                        formatted_caption.entities.append(
                            MessageEntity(
                                type=MESSAGEENTITY_TEXT_LINK,
                                offset=utf16len(
                                    formatted_caption.caption[0:hashtag_occurrence]
                                ),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        return formatted_caption

    def short_caption(self) -> FormattedCaption:
        return shorten_formatted_caption(self.long_caption())


class ProfileCaptions:
    _profile: PatchedProfile

    def __init__(self, profile: PatchedProfile) -> None:
        self._profile = profile

    def long_caption(self) -> FormattedCaption:
        """Create a FormattedCaption object from a given profile"""
        # Initializing
        formatted_caption = FormattedCaption()

        # URL to profile picture
        formatted_caption.append(
            "Profile Picture",
            type=MESSAGEENTITY_TEXT_LINK,
            url=self._profile.profile_pic_url,
        )
        formatted_caption.append("\n")

        # Profile username and ID
        formatted_caption.append(
            f"@{self._profile.username}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/",
        )
        formatted_caption.append(f" ({self._profile.userid})\n")

        # Post count
        formatted_caption.append(f"{self._profile.mediacount} post")
        if self._profile.mediacount > 1:
            formatted_caption.append("s")
        formatted_caption.append(", ")
        # Follower count
        formatted_caption.append(
            f"{self._profile.followers}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/followers/",
        )
        formatted_caption.append(" follower")
        if self._profile.followers > 1:
            formatted_caption.append("s")
        formatted_caption.append(", ")
        # Following count
        formatted_caption.append(
            f"{self._profile.followees}",
            type=MESSAGEENTITY_TEXT_LINK,
            url=f"https://instagram.com/{self._profile.username}/following/",
        )
        formatted_caption.append(" following\n")

        # IGTV count
        if self._profile.igtvcount > 0:
            formatted_caption.append(
                f"{self._profile.igtvcount}",
                type=MESSAGEENTITY_TEXT_LINK,
                url=f"https://instagram.com/{self._profile.username}/channel/",
            )
            formatted_caption.append(f" IGTV post")
            if self._profile.igtvcount > 1:
                formatted_caption.append("s")
            formatted_caption.append("\n")

        # Full name
        formatted_caption.append(f"{self._profile.full_name}", type=MESSAGEENTITY_BOLD)
        formatted_caption.append("\n")

        # Business account
        if self._profile.is_business_account:
            formatted_caption.append(
                f"{self._profile.business_category_name}", type=MESSAGEENTITY_ITALIC
            )
            formatted_caption.append("\n")

        # Profile biography
        if self._profile.biography is not None:
            old_caption = formatted_caption.caption
            formatted_caption.append(self._profile.biography)

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
                        formatted_caption.entities.append(
                            MessageEntity(
                                type=MESSAGEENTITY_TEXT_LINK,
                                offset=utf16len(
                                    formatted_caption.caption[0:mention_occurrence]
                                ),
                                length=utf16len(f"@{caption_mention}"),
                                url=f"https://instagram.com/{caption_mention}/",
                            )
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
                        formatted_caption.entities.append(
                            MessageEntity(
                                type=MESSAGEENTITY_TEXT_LINK,
                                offset=utf16len(
                                    formatted_caption.caption[0:hashtag_occurrence]
                                ),
                                length=utf16len(f"#{caption_hashtag}"),
                                url=f"https://instagram.com/explore/tags/{caption_hashtag}/",
                            )
                        )
                    hashtag_occurrences.add(hashtag_occurrence)

        # External URL
        if self._profile.external_url is not None:
            if self._profile.biography is not None:
                formatted_caption.append("\n")
            formatted_caption.append(
                f"{self._profile.external_url}", type=MESSAGEENTITY_BOLD
            )
            formatted_caption.append("\n")

        return formatted_caption

    def short_caption(self) -> FormattedCaption:
        return shorten_formatted_caption(self.long_caption())
