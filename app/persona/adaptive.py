"""Adaptive persona state machine with temporal hysteresis."""

import time

from app.core.logging import get_logger
from app.persona.models import PersonaType

logger = get_logger("app.persona.adaptive")


class AdaptivePersonaStateMachine:
    """
    Dynamically modulates Honney's active persona based on stream state:
    - High chat velocity & clutch plays -> HYPE
    - High question density -> HELPFUL
    - Slow/chill chat -> PLAYFUL or WITTY
    Applies 30-second dwell time (hysteresis) to prevent rapid persona flickering.
    """

    def __init__(self, dwell_time_seconds: float = 30.0) -> None:
        self.dwell_time = dwell_time_seconds
        self.active_type: PersonaType = PersonaType.CO_HOST
        self.last_transition_time: float = time.time()

    def evaluate_state(
        self,
        chat_velocity_per_min: float,
        question_density_ratio: float,
        stream_intensity: str = "NORMAL",
    ) -> PersonaType:
        """
        Evaluate stream dynamics and return persona type.
        Honors minimum dwell time before allowing a transition.
        """
        now = time.time()
        time_in_state = now - self.last_transition_time

        # If locked in dwell period, retain current persona
        if time_in_state < self.dwell_time and self.last_transition_time > 0:
            return self.active_type

        new_type = self._determine_target_type(
            chat_velocity_per_min, question_density_ratio, stream_intensity
        )

        if new_type != self.active_type:
            logger.info(
                f"Adaptive Persona transitioning from {self.active_type.value} -> {new_type.value} "
                f"(Velocity: {chat_velocity_per_min}/m, Questions: {question_density_ratio * 100:.1f}%, Intensity: {stream_intensity})"
            )
            self.active_type = new_type
            self.last_transition_time = now

        return self.active_type

    def _determine_target_type(
        self,
        velocity: float,
        question_ratio: float,
        intensity: str,
    ) -> PersonaType:
        if intensity == "HYPE" or velocity > 60:
            return PersonaType.HYPE
        if question_ratio > 0.4:
            return PersonaType.HELPFUL
        if velocity < 15:
            return PersonaType.PLAYFUL
        return PersonaType.CO_HOST
