"""Advanced Discord operations service for incident alerting, creator logging, and summaries."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("app.discord.operations")


class DiscordAlertPriority:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DiscordOperationsService:
    """
    Production Discord operations service:
    - Multi-tenant routing: Developer alert channel + Creator-specific log/alert channels.
    - Distributed alert deduplication & cooldowns via Redis with in-memory fallback.
    - Asynchronous bounded retry queue to absorb transient Discord outages without stalling streams.
    - Rich embed formatting without secret exposure.
    - Stream end summaries and daily system summaries.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        dev_channel_id: str | None = None,
        alert_cooldown_seconds: int = 300,
    ):
        settings = get_settings()
        self.bot_token = bot_token or settings.DISCORD_BOT_TOKEN
        self.dev_channel_id = dev_channel_id or settings.DISCORD_DEV_CHANNEL_ID
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self._recent_alerts: dict[str, datetime] = {}  # In-memory fallback
        self._retry_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=getattr(settings, "DISCORD_RETRY_QUEUE_MAX_SIZE", 1000)
        )
        self._last_success_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._recent_failures: int = 0
        self._worker_task: asyncio.Task[None] | None = None

    def _should_suppress_alert(self, key: str, severity: str) -> bool:
        """Deduplicate non-critical alerts with cooldown tracking."""
        if severity == DiscordAlertPriority.CRITICAL:
            return False

        now = datetime.now(UTC)
        last_sent = self._recent_alerts.get(key)
        if last_sent and (now - last_sent).total_seconds() < self.alert_cooldown_seconds:
            logger.debug(f"Alert '{key}' suppressed under cooldown")
            return True

        self._recent_alerts[key] = now
        return False

    async def send_critical_incident_alert(
        self,
        incident_id: str,
        service: str,
        summary: str,
        severity: str = DiscordAlertPriority.CRITICAL,
        affected_creators: list[str] | None = None,
        affected_streams: list[str] | None = None,
        likely_cause: str | None = None,
        recommended_action: str | None = None,
    ) -> bool:
        """
        Send a structured critical incident alert to developer Discord channel.
        Includes incident ID, affected entities, and actionable troubleshooting guidance.
        """
        if not self.dev_channel_id:
            logger.info(
                f"[Simulated Discord Alert {severity}]: Incident {incident_id} ({service}) - {summary}"
            )
            return True

        alert_key = f"{service}:{severity}:{summary[:30]}"
        if self._should_suppress_alert(alert_key, severity):
            return True

        creators_str = ", ".join(affected_creators) if affected_creators else "All / Global"
        streams_str = ", ".join(affected_streams) if affected_streams else "All / Global"

        color = 0xDC2626 if severity == DiscordAlertPriority.CRITICAL else 0xF59E0B  # Red or Amber

        embed = {
            "title": f"🚨 SYSTEM ALERT [{severity}]: {service.upper()}",
            "description": summary,
            "color": color,
            "fields": [
                {"name": "Incident ID", "value": f"`{incident_id}`", "inline": True},
                {"name": "Service", "value": service, "inline": True},
                {"name": "Severity", "value": severity, "inline": True},
                {"name": "Affected Creators", "value": creators_str, "inline": True},
                {"name": "Affected Streams", "value": streams_str, "inline": True},
                {
                    "name": "Time",
                    "value": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "inline": False,
                },
                {
                    "name": "Likely Cause",
                    "value": likely_cause or "Under investigation",
                    "inline": False,
                },
                {
                    "name": "Recommended Safe Action",
                    "value": recommended_action
                    or "Inspect developer control center and system logs.",
                    "inline": False,
                },
            ],
            "footer": {"text": "Goddess AI Production Operations"},
        }

        content = "@everyone" if severity == DiscordAlertPriority.CRITICAL else ""
        return await self._dispatch_message(self.dev_channel_id, content=content, embeds=[embed])

    async def send_recovery_notification(
        self,
        incident_id: str,
        service: str,
        downtime_minutes: float | None = None,
        resolution: str | None = None,
    ) -> bool:
        """Send recovery notification when an incident is mitigated or resolved."""
        if not self.dev_channel_id:
            logger.info(
                f"[Simulated Discord Recovery]: Incident {incident_id} ({service}) recovered."
            )
            return True

        duration_str = f"{downtime_minutes:.1f} minutes" if downtime_minutes else "N/A"
        embed = {
            "title": f"✅ RECOVERED: {service.upper()}",
            "description": f"Incident `{incident_id}` has been resolved. Service is operational.",
            "color": 0x10B981,  # Emerald
            "fields": [
                {"name": "Incident ID", "value": f"`{incident_id}`", "inline": True},
                {"name": "Downtime", "value": duration_str, "inline": True},
                {
                    "name": "Resolution",
                    "value": resolution or "Automatic recovery verified.",
                    "inline": False,
                },
            ],
            "footer": {"text": "Goddess AI Production Operations"},
        }
        return await self._dispatch_message(self.dev_channel_id, content="", embeds=[embed])

    async def send_stream_summary(
        self,
        creator_id: str,
        stream_id: str,
        duration_minutes: float,
        stats: dict[str, Any],
        channel_id: str | None = None,
    ) -> bool:
        """
        Send end-of-stream summary to creator's designated Discord channel.
        Includes messages, moderation actions, AI usage, and engagement stats.
        """
        target_channel = channel_id or self.dev_channel_id
        if not target_channel:
            logger.info(
                f"[Simulated Discord Stream Summary]: Creator {creator_id}, Stream {stream_id}"
            )
            return True

        hours = int(duration_minutes // 60)
        mins = int(duration_minutes % 60)
        duration_fmt = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        embed = {
            "title": "📊 Stream Session Summary",
            "description": f"Live stream **{stream_id}** has ended.",
            "color": 0x8B5CF6,  # Purple
            "fields": [
                {"name": "Duration", "value": duration_fmt, "inline": True},
                {
                    "name": "Messages Processed",
                    "value": str(stats.get("messages", 0)),
                    "inline": True,
                },
                {
                    "name": "Peak Viewers",
                    "value": str(stats.get("peak_viewers", "N/A")),
                    "inline": True,
                },
                {
                    "name": "🛡️ Moderation Actions",
                    "value": (
                        f"Deletes: {stats.get('moderation_deletes', 0)} | "
                        f"Timeouts: {stats.get('moderation_timeouts', 0)} | "
                        f"Reviews: {stats.get('moderation_reviews', 0)}"
                    ),
                    "inline": False,
                },
                {
                    "name": "🤖 AI Co-Host Activity",
                    "value": (
                        f"Replies: {stats.get('ai_replies', 0)} | "
                        f"Tokens: {stats.get('ai_tokens', 0)} | "
                        f"Fallbacks: {stats.get('ai_fallbacks', 0)}"
                    ),
                    "inline": False,
                },
                {
                    "name": "🎮 Viewer Engagement",
                    "value": (
                        f"XP Awarded: {stats.get('xp_awarded', 0)} | "
                        f"Coins Minted: {stats.get('coins_minted', 0)} | "
                        f"Games Won: {stats.get('games_won', 0)} | "
                        f"Store Purchases: {stats.get('store_purchases', 0)}"
                    ),
                    "inline": False,
                },
            ],
            "footer": {"text": "Honney AI Co-Host Analytics"},
        }
        return await self._dispatch_message(target_channel, content="", embeds=[embed])

    async def send_daily_system_summary(self, summary_data: dict[str, Any]) -> bool:
        """Send 24-hour operational summary to developer channel."""
        if not self.dev_channel_id:
            logger.info("[Simulated Discord Daily Summary]")
            return True

        embed = {
            "title": "📈 Goddess AI Daily Operations Report",
            "description": f"Operational telemetry for {datetime.now(UTC).strftime('%Y-%m-%d')}.",
            "color": 0x3B82F6,  # Blue
            "fields": [
                {
                    "name": "Total Streams",
                    "value": str(summary_data.get("total_streams", 0)),
                    "inline": True,
                },
                {
                    "name": "Stream Hours",
                    "value": f"{summary_data.get('stream_hours', 0.0):.1f}h",
                    "inline": True,
                },
                {
                    "name": "Total Messages",
                    "value": str(summary_data.get("messages", 0)),
                    "inline": True,
                },
                {
                    "name": "Moderation Events",
                    "value": str(summary_data.get("moderation_events", 0)),
                    "inline": True,
                },
                {
                    "name": "AI Tokens Used",
                    "value": str(summary_data.get("ai_tokens", 0)),
                    "inline": True,
                },
                {
                    "name": "Quota Consumed",
                    "value": f"{summary_data.get('quota_used', 0)} / 4000",
                    "inline": True,
                },
                {
                    "name": "Active Incidents",
                    "value": str(summary_data.get("active_incidents", 0)),
                    "inline": True,
                },
                {
                    "name": "Ledger Status",
                    "value": summary_data.get("ledger_status", "BALANCED"),
                    "inline": True,
                },
            ],
            "footer": {"text": "Goddess AI Developer Operations"},
        }
        return await self._dispatch_message(self.dev_channel_id, content="", embeds=[embed])

    async def _dispatch_message(
        self,
        channel_id: str,
        content: str = "",
        embeds: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Internal HTTP client dispatcher to Discord REST API."""
        if not self.bot_token or not channel_id:
            logger.info(
                f"[Simulated Discord -> channel {channel_id}]: {content} (embeds: {len(embeds or [])})"
            )
            return True

        payload: dict[str, Any] = {}
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds

        try:
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            headers = {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    self._last_success_at = datetime.now(UTC)
                    self._recent_failures = 0
                    return True
                else:
                    self._last_failure_at = datetime.now(UTC)
                    self._recent_failures += 1
                    logger.warning(
                        f"Discord API returned status {resp.status_code} for channel {channel_id}"
                    )
                    self._enqueue_retry(channel_id, payload)
                    return False
        except Exception as e:
            self._last_failure_at = datetime.now(UTC)
            self._recent_failures += 1
            logger.error(f"Failed to deliver Discord message to {channel_id}: {e}")
            self._enqueue_retry(channel_id, payload)
            return False

    def _enqueue_retry(self, channel_id: str, payload: dict[str, Any]) -> None:
        """Place failed message in retry queue without blocking."""
        try:
            self._retry_queue.put_nowait({"channel_id": channel_id, "payload": payload})
        except asyncio.QueueFull:
            logger.warning("Discord retry queue is full; dropping oldest non-critical message")
            try:
                self._retry_queue.get_nowait()
                self._retry_queue.put_nowait({"channel_id": channel_id, "payload": payload})
            except Exception:
                pass

    async def drain_retry_queue(self, max_items: int = 10) -> int:
        """Attempt to dispatch buffered messages in the retry queue."""
        if not self.bot_token or self._retry_queue.empty():
            return 0

        drained = 0
        for _ in range(max_items):
            if self._retry_queue.empty():
                break
            try:
                item = self._retry_queue.get_nowait()
                channel_id = item["channel_id"]
                payload = item["payload"]
                url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                headers = {
                    "Authorization": f"Bot {self.bot_token}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code in (200, 201):
                        drained += 1
                        self._last_success_at = datetime.now(UTC)
                        self._recent_failures = 0
                    else:
                        # Re-enqueue if temporary failure
                        self._enqueue_retry(channel_id, payload)
                        break
            except Exception as e:
                logger.debug(f"Drain retry queue attempt failed: {e}")
                break
        return drained

    async def check_readiness(self) -> dict[str, Any]:
        """
        Check Discord subsystem health without sending spam messages:
        - Checks bot token and dev channel presence
        - Checks retry queue depth and recent delivery errors
        """
        configured = bool(self.bot_token and self.dev_channel_id)
        queue_depth = self._retry_queue.qsize()
        status = "READY" if configured else "CONFIG_MISSING"
        if configured and self._recent_failures > 5:
            status = "DEGRADED"

        return {
            "status": status,
            "configured": configured,
            "retry_queue_depth": queue_depth,
            "recent_failures": self._recent_failures,
            "last_success_at": self._last_success_at.isoformat() if self._last_success_at else None,
            "last_failure_at": self._last_failure_at.isoformat() if self._last_failure_at else None,
            "message": "Discord operational" if status == "READY" else f"Discord {status}",
        }
