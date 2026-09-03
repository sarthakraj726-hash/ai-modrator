"""Response trigger evaluation and stream context tracking."""

import re
import time
from enum import Enum

from app.core.logging import get_logger

logger = get_logger("app.persona.triggers")


class StreamState(str, Enum):
    NORMAL = "NORMAL"
    QUIET = "QUIET"
    HYPE = "HYPE"
    INTENSE_GAMEPLAY = "INTENSE_GAMEPLAY"
    CREATOR_SPEAKING = "CREATOR_SPEAKING"
    ENDING = "ENDING"


class TriggerType(str, Enum):
    DIRECT_MENTION = "DIRECT_MENTION"
    QUESTION = "QUESTION"
    GREETING = "GREETING"
    FAREWELL = "FAREWELL"
    HYPE_EVENT = "HYPE_EVENT"
    NONE = "NONE"


class StreamContextEngine:
    """Tracks active stream state and enforces quiet/creator-speaking silence periods."""

    def __init__(self) -> None:
        self._states: dict[str, StreamState] = {}  # stream_session_id -> StreamState
        self._last_speaking: dict[str, float] = {}  # stream_session_id -> timestamp

    def set_state(self, stream_session_id: str, state: StreamState) -> None:
        self._states[stream_session_id] = state

    def get_state(self, stream_session_id: str) -> StreamState:
        return self._states.get(stream_session_id, StreamState.NORMAL)

    def record_creator_speaking(self, stream_session_id: str) -> None:
        """Mark that creator is actively speaking, triggering a 15-second ambient quiet period."""
        self._last_speaking[stream_session_id] = time.time()

    def should_suppress_ambient(self, stream_session_id: str) -> bool:
        """Check if ambient unprompted responses should be suppressed."""
        state = self.get_state(stream_session_id)
        if state in (StreamState.QUIET, StreamState.INTENSE_GAMEPLAY, StreamState.CREATOR_SPEAKING):
            return True

        # Silence preference for 15s after creator speaks
        last_spoke = self._last_speaking.get(stream_session_id, 0.0)
        if time.time() - last_spoke < 15.0:
            return True

        return False


class ResponseTriggerEngine:
    """Evaluates chat messages to identify legitimate triggers for co-host responses."""

    MENTION_REGEX = re.compile(r"@(honney|goddess|ai|mod)\b", re.IGNORECASE)
    GREETING_REGEX = re.compile(
        r"\b(hi|hello|hey|namaste|kem cho|kya haal|wassup|yo)\b", re.IGNORECASE
    )
    FAREWELL_REGEX = re.compile(
        r"\b(bye|good\s*night|gn|see\s*ya|cya|alvida|tata)\b", re.IGNORECASE
    )

    @classmethod
    def evaluate_trigger(
        cls,
        text: str,
        stream_session_id: str,
        context_engine: StreamContextEngine | None = None,
    ) -> tuple[TriggerType, str]:
        """
        Evaluate message text to decide trigger category.
        Returns (TriggerType, matched_keyword).
        """
        cleaned = text.strip()

        # 1. Direct bot mention
        mention = cls.MENTION_REGEX.search(cleaned)
        if mention:
            return TriggerType.DIRECT_MENTION, mention.group(0)

        # 2. Check if ambient responses are currently suppressed by stream context
        if context_engine and context_engine.should_suppress_ambient(stream_session_id):
            return TriggerType.NONE, ""

        # 3. Direct question
        if "?" in cleaned and len(cleaned) > 5:
            return TriggerType.QUESTION, "?"

        # 4. Greeting
        greet = cls.GREETING_REGEX.search(cleaned)
        if greet and len(cleaned.split()) <= 4:
            return TriggerType.GREETING, greet.group(0)

        # 5. Farewell
        farewell = cls.FAREWELL_REGEX.search(cleaned)
        if farewell and len(cleaned.split()) <= 4:
            return TriggerType.FAREWELL, farewell.group(0)

        return TriggerType.NONE, ""
