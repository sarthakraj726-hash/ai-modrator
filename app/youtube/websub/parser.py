"""Secure XML parser for YouTube WebSub Atom feeds."""

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime

from app.core.exceptions import InvalidArgumentError
from app.youtube.websub.models import WebSubNotification

# Namespaces in YouTube WebSub Atom feeds
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


class WebSubParser:
    """Parses incoming YouTube WebSub Atom XML notifications securely."""

    MAX_PAYLOAD_BYTES = 256 * 1024  # 256 KB limit to prevent XML bomb / DoS

    @classmethod
    def parse_atom_feed(cls, xml_content: bytes | str) -> WebSubNotification:
        """
        Parse YouTube Atom XML feed and extract video ID, channel ID, and metadata.
        Rejects payloads exceeding size limits or containing entity expansions.
        """
        if isinstance(xml_content, str):
            raw_bytes = xml_content.encode("utf-8")
        else:
            raw_bytes = xml_content

        if not raw_bytes:
            raise InvalidArgumentError("Empty XML payload received.")

        if len(raw_bytes) > cls.MAX_PAYLOAD_BYTES:
            raise InvalidArgumentError(
                f"XML payload size ({len(raw_bytes)} bytes) exceeds safety limit of {cls.MAX_PAYLOAD_BYTES} bytes."
            )

        # XML entity expansion protection: Reject XML with <!ENTITY or <!DOCTYPE
        xml_str = raw_bytes.decode("utf-8", errors="replace")
        if "<!ENTITY" in xml_str.upper() or "<!DOCTYPE" in xml_str.upper():
            raise InvalidArgumentError(
                "XML payload contains forbidden DOCTYPE or ENTITY definitions."
            )

        try:
            root = ET.fromstring(raw_bytes)
        except Exception as e:
            raise InvalidArgumentError(f"Failed to parse XML payload: {e}") from e

        # Extract entry
        entry = root.find(f"{ATOM_NS}entry")
        if entry is None:
            # Check if root itself is the entry
            if root.tag == f"{ATOM_NS}entry":
                entry = root
            else:
                raise InvalidArgumentError("No <entry> element found in Atom feed.")

        # Extract yt:videoId
        video_id_elem = entry.find(f"{YT_NS}videoId")
        if video_id_elem is None or not video_id_elem.text:
            raise InvalidArgumentError("No <yt:videoId> found in Atom feed entry.")
        video_id = video_id_elem.text.strip()

        # Extract yt:channelId
        channel_id_elem = entry.find(f"{YT_NS}channelId")
        if channel_id_elem is None or not channel_id_elem.text:
            raise InvalidArgumentError("No <yt:channelId> found in Atom feed entry.")
        channel_id = channel_id_elem.text.strip()

        # Extract title
        title_elem = entry.find(f"{ATOM_NS}title")
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

        # Extract timestamps
        published_at = None
        published_elem = entry.find(f"{ATOM_NS}published")
        if published_elem is not None and published_elem.text:
            try:
                published_at = datetime.fromisoformat(
                    published_elem.text.strip().replace("Z", "+00:00")
                )
            except Exception:
                pass

        updated_at = None
        updated_elem = entry.find(f"{ATOM_NS}updated")
        if updated_elem is not None and updated_elem.text:
            try:
                updated_at = datetime.fromisoformat(
                    updated_elem.text.strip().replace("Z", "+00:00")
                )
            except Exception:
                pass

        # Extract feed ID
        id_elem = entry.find(f"{ATOM_NS}id")
        feed_id = (
            id_elem.text.strip() if id_elem is not None and id_elem.text else f"yt:video:{video_id}"
        )

        # Generate deterministic dedupe hash (channel_id + video_id + timestamp)
        ts_str = (
            updated_elem.text.strip()
            if updated_elem is not None and updated_elem.text
            else (
                published_elem.text.strip()
                if published_elem is not None and published_elem.text
                else "now"
            )
        )
        dedupe_str = f"{channel_id}:{video_id}:{ts_str}"
        dedupe_hash = hashlib.sha256(dedupe_str.encode()).hexdigest()

        return WebSubNotification(
            channel_id=channel_id,
            video_id=video_id,
            title=title,
            published_at=published_at,
            updated_at=updated_at,
            dedupe_hash=dedupe_hash,
            feed_id=feed_id,
        )
