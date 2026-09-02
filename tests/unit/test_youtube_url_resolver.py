"""Unit tests for YouTube URL and Channel identifier resolvers."""

import pytest

from app.core.exceptions import InvalidArgumentError
from app.youtube.channel_resolver import ChannelIdentifierResolver
from app.youtube.url_resolver import YouTubeUrlResolver


def test_resolve_standard_watch_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res = YouTubeUrlResolver.resolve_video_id(url)
    assert res.video_id == "dQw4w9WgXcQ"
    assert res.normalized_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert res.source_format == "watch"


def test_resolve_shortlink_url():
    url = "https://youtu.be/dQw4w9WgXcQ"
    res = YouTubeUrlResolver.resolve_video_id(url)
    assert res.video_id == "dQw4w9WgXcQ"
    assert res.source_format == "shortlink"


def test_resolve_live_url():
    url = "https://youtube.com/live/dQw4w9WgXcQ"
    res = YouTubeUrlResolver.resolve_video_id(url)
    assert res.video_id == "dQw4w9WgXcQ"
    assert res.source_format == "live"


def test_resolve_direct_id():
    res = YouTubeUrlResolver.resolve_video_id("dQw4w9WgXcQ")
    assert res.video_id == "dQw4w9WgXcQ"
    assert res.source_format == "direct_id"


def test_resolve_shorts_url():
    url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    res = YouTubeUrlResolver.resolve_video_id(url)
    assert res.video_id == "dQw4w9WgXcQ"
    assert res.source_format == "shorts"


def test_reject_non_youtube_domain():
    with pytest.raises(InvalidArgumentError, match="Unsupported domain"):
        YouTubeUrlResolver.resolve_video_id("https://evil-site.com/watch?v=dQw4w9WgXcQ")


def test_reject_invalid_video_id_format():
    with pytest.raises(InvalidArgumentError, match="Could not extract a valid 11-character"):
        YouTubeUrlResolver.resolve_video_id("https://www.youtube.com/watch?v=short_id")


def test_channel_resolver_direct_ucid():
    ucid = "UC1234567890123456789012"
    res = ChannelIdentifierResolver.parse_channel_identifier(ucid)
    assert res.channel_id == ucid
    assert res.source_format == "channel_id"


def test_channel_resolver_handle():
    handle = "@GoddessGaming"
    res = ChannelIdentifierResolver.parse_channel_identifier(handle)
    assert res.handle == handle
    assert res.source_format == "handle"


def test_channel_resolver_url():
    url = "https://www.youtube.com/channel/UC1234567890123456789012"
    res = ChannelIdentifierResolver.parse_channel_identifier(url)
    assert res.channel_id == "UC1234567890123456789012"
    assert res.source_format == "channel_url"


def test_channel_resolver_handle_url():
    url = "https://www.youtube.com/@GoddessGaming"
    res = ChannelIdentifierResolver.parse_channel_identifier(url)
    assert res.handle == "@GoddessGaming"
    assert res.source_format == "handle_url"
