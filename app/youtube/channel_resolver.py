"""YouTube Channel identifier and handle resolver."""

import re
from urllib.parse import urlparse

from app.core.exceptions import InvalidArgumentError
from app.youtube.models import ResolvedChannel

# Standard 24-character YouTube Channel ID regex (UC...)
YOUTUBE_CHANNEL_ID_REGEX = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")

# YouTube Handle regex (e.g. @CreatorName)
YOUTUBE_HANDLE_REGEX = re.compile(r"^@[a-zA-Z0-9_.-]{3,30}$")


class ChannelIdentifierResolver:
    """Parses and validates YouTube Channel identifiers (UCIDs, handles, custom URLs)."""

    @classmethod
    def parse_channel_identifier(cls, input_identifier: str) -> ResolvedChannel:
        """
        Extract channel ID or handle from string or URL without network call.
        If a handle or custom URL is provided, returns structured format for downstream API resolution.
        """
        if not input_identifier or not isinstance(input_identifier, str):
            raise InvalidArgumentError("Channel identifier cannot be empty.")

        cleaned = input_identifier.strip()

        # 1. Direct UCID
        if YOUTUBE_CHANNEL_ID_REGEX.match(cleaned):
            return ResolvedChannel(
                channel_id=cleaned,
                source_format="channel_id",
            )

        # 2. Direct Handle (@handle)
        if YOUTUBE_HANDLE_REGEX.match(cleaned):
            return ResolvedChannel(
                channel_id="",
                handle=cleaned,
                source_format="handle",
            )

        # 3. Parse Channel URL
        if (
            cleaned.startswith("http://")
            or cleaned.startswith("https://")
            or "youtube.com" in cleaned
        ):
            if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
                cleaned = f"https://{cleaned}"

            try:
                parsed = urlparse(cleaned)
            except Exception as e:
                raise InvalidArgumentError(f"Malformed channel URL: {e}") from e

            path_parts = [p for p in parsed.path.split("/") if p]
            if not path_parts:
                raise InvalidArgumentError(f"No path found in channel URL '{input_identifier}'.")

            # /channel/UC...
            if path_parts[0] == "channel" and len(path_parts) >= 2:
                ucid = path_parts[1]
                if YOUTUBE_CHANNEL_ID_REGEX.match(ucid):
                    return ResolvedChannel(
                        channel_id=ucid,
                        source_format="channel_url",
                    )
                raise InvalidArgumentError(f"Invalid UCID '{ucid}' in channel URL.")

            # /@handle
            if path_parts[0].startswith("@"):
                handle = path_parts[0]
                if YOUTUBE_HANDLE_REGEX.match(handle):
                    return ResolvedChannel(
                        channel_id="",
                        handle=handle,
                        source_format="handle_url",
                    )

            # /c/CustomName or /user/UserName
            if path_parts[0] in ("c", "user") and len(path_parts) >= 2:
                return ResolvedChannel(
                    channel_id="",
                    custom_url=path_parts[1],
                    source_format="custom_url",
                )

        raise InvalidArgumentError(
            f"Could not parse valid YouTube channel ID or handle from '{input_identifier}'."
        )
