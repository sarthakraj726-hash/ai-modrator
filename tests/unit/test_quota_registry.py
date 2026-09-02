"""Unit tests for YouTube Quota Cost Registry."""

from app.youtube.quota_registry import YouTubeQuotaCostRegistry


def test_quota_registry_defaults():
    registry = YouTubeQuotaCostRegistry()
    assert registry.get_cost("videos.list") == 1
    assert registry.get_cost("channels.list") == 1
    assert registry.get_cost("search.list") == 100
    assert registry.get_cost("liveChatMessages.insert") == 50
    assert registry.get_cost("unknown.endpoint") == 1


def test_quota_registry_dynamic_override():
    registry = YouTubeQuotaCostRegistry()
    registry.set_cost("videos.list", 5)
    assert registry.get_cost("videos.list") == 5


def test_quota_registry_usage_telemetry():
    registry = YouTubeQuotaCostRegistry()
    registry.record_usage("videos.list", cost=1, success=True)
    registry.record_usage("videos.list", cost=1, success=False)
    registry.record_usage("search.list", cost=100, success=True)

    stats = registry.get_stats()
    assert "videos.list" in stats
    assert stats["videos.list"]["total_calls"] == 2
    assert stats["videos.list"]["total_quota_consumed"] == 2
    assert stats["videos.list"]["failed_calls"] == 1

    assert stats["search.list"]["total_calls"] == 1
    assert stats["search.list"]["total_quota_consumed"] == 100
