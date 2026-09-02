"""Unit tests for secure WebSub Atom XML parser."""

import pytest

from app.core.exceptions import InvalidArgumentError
from app.youtube.websub.parser import WebSubParser

VALID_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <link rel="hub" href="https://pubsubhubbub.appspot.com"/>
  <title>YouTube video feed</title>
  <updated>2026-09-02T12:00:00+00:00</updated>
  <entry>
    <id>yt:video:dQw4w9WgXcQ</id>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <yt:channelId>UC1234567890123456789012</yt:channelId>
    <title>Awesome Live Stream</title>
    <published>2026-09-02T11:59:00+00:00</published>
    <updated>2026-09-02T12:00:00+00:00</updated>
  </entry>
</feed>
"""


def test_parse_valid_atom_feed():
    notification = WebSubParser.parse_atom_feed(VALID_ATOM_FEED)
    assert notification.video_id == "dQw4w9WgXcQ"
    assert notification.channel_id == "UC1234567890123456789012"
    assert notification.title == "Awesome Live Stream"
    assert notification.published_at is not None
    assert notification.updated_at is not None
    assert len(notification.dedupe_hash) == 64


def test_reject_xml_with_entity_expansion_xxe():
    malicious_xml = """<?xml version="1.0"?>
    <!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <yt:videoId>dQw4w9WgXcQ</yt:videoId>
      </entry>
    </feed>
    """
    with pytest.raises(InvalidArgumentError, match="forbidden DOCTYPE or ENTITY"):
        WebSubParser.parse_atom_feed(malicious_xml)


def test_reject_oversized_payload():
    large_xml = VALID_ATOM_FEED + (" " * (300 * 1024))
    with pytest.raises(InvalidArgumentError, match="exceeds safety limit"):
        WebSubParser.parse_atom_feed(large_xml)


def test_reject_empty_payload():
    with pytest.raises(InvalidArgumentError, match="Empty XML"):
        WebSubParser.parse_atom_feed("")
