#!/usr/bin/env python3
from typing import List, Optional
from unicodedata import normalize

from instaloader import InstaloaderContext, Post, Profile, StoryItem

from structures import TaggedUser, optional_normalize

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
