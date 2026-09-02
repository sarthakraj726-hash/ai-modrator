"""YouTube URL parser and identifier normalizer."""

import re
from urllib.parse import parse_qs, urlparse

from app.core.exceptions import InvalidArgumentError
from app.youtube.models import ResolvedYouTubeUrl

# Standard 11-character YouTube video ID regex
YOUTUBE_VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# Allowed YouTube domains for SSRF protection
ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


class YouTubeUrlResolver:
    """Parses, validates, and normalizes YouTube video URLs and IDs."""

    @classmethod
    def resolve_video_id(cls, input_url_or_id: str) -> ResolvedYouTubeUrl:
        """
        Extract video ID from URL or raw ID, validate structure, and normalize.
        Raises InvalidArgumentError for malformed or unsupported inputs.
        """
        if not input_url_or_id or not isinstance(input_url_or_id, str):
            raise InvalidArgumentError("YouTube URL or Video ID cannot be empty.")

        cleaned = input_url_or_id.strip()

        # 1. Direct 11-character ID
        if YOUTUBE_VIDEO_ID_REGEX.match(cleaned):
            return ResolvedYouTubeUrl(
                original_url=cleaned,
                normalized_url=f"https://www.youtube.com/watch?v={cleaned}",
                video_id=cleaned,
                source_format="direct_id",
            )

        # 2. Parse URL
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            cleaned_url = f"https://{cleaned}"
        else:
            cleaned_url = cleaned

        try:
            parsed = urlparse(cleaned_url)
        except Exception as e:
            raise InvalidArgumentError(f"Malformed URL: {e}") from e

        hostname = (parsed.hostname or "").lower()
        if hostname not in ALLOWED_YOUTUBE_HOSTS:
            raise InvalidArgumentError(
                f"Unsupported domain '{hostname}'. Expected YouTube domain (e.g. youtube.com, youtu.be)."
            )

        video_id: str | None = None
        source_format: str = "unknown"

        # Handle youtu.be shortlinks (e.g. youtu.be/dQw4w9WgXcQ)
        if "youtu.be" in hostname:
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                video_id = path_parts[0]
                source_format = "shortlink"

        # Handle /watch?v=VIDEO_ID
        elif parsed.path == "/watch" or parsed.path.startswith("/watch/"):
            query_params = parse_qs(parsed.query)
            v_param = query_params.get("v")
            if v_param:
                video_id = v_param[0]
                source_format = "watch"

        # Handle /live/VIDEO_ID
        elif parsed.path.startswith("/live/"):
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 2:
                video_id = path_parts[1]
                source_format = "live"

        # Handle /shorts/VIDEO_ID or /embed/VIDEO_ID
        elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 2:
                video_id = path_parts[1]
                source_format = path_parts[0]

        if not video_id or not YOUTUBE_VIDEO_ID_REGEX.match(video_id):
            raise InvalidArgumentError(
                f"Could not extract a valid 11-character YouTube video ID from '{input_url_or_id}'."
            )

        normalized_url = f"https://www.youtube.com/watch?v={video_id}"
        return ResolvedYouTubeUrl(
            original_url=input_url_or_id,
            normalized_url=normalized_url,
            video_id=video_id,
            source_format=source_format,
        )
