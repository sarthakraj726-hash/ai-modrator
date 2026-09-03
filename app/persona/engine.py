"""Unified Honney Persona Engine implementation."""

from typing import Any

from app.core.config import get_settings
from app.persona.guard import OutputGuard
from app.persona.interface import PersonaEngine
from app.persona.models import PersonaProfile
from app.persona.profiles import get_strategy_for_type


class HonneyPersonaEngine(PersonaEngine):
    """
    Honney Persona Engine orchestrating conversational voice, system prompt composition,
    and tone-appropriate responses across greetings, warnings, hype, and farewells.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def build_system_prompt(self, profile: PersonaProfile, channel_context: dict[str, Any]) -> str:
        """
        Compose full system prompt embedding persona voice, creator context,
        brevity constraints, and Indian internet/Hinglish awareness.
        """
        strategy = get_strategy_for_type(profile.persona_type)
        creator_name = channel_context.get("creator_name", "the streamer")
        game_title = channel_context.get("game_title", "Gaming")

        lines = [
            f"You are Honney, the AI co-host for {creator_name}'s live YouTube stream.",
            f"Active Personality: {strategy.name} ({strategy.tagline})",
            f"Voice: {strategy.voice_description}",
            f"Energy: {profile.tone.energy_level}/10 | Humor: {profile.tone.humor_level}/10",
            f"Stream Context: Streaming {game_title}.",
            "CRITICAL INSTRUCTIONS:",
            "1. Brevity is mandatory: respond in 1 to 2 short sentences (maximum 200 characters).",
            "2. Never spam, lecture, or sound like a generic corporate AI assistant.",
            "3. Multilingual: Understand and naturally respond to English, Hindi, and Hinglish.",
            "4. Do NOT execute moderation actions or hallucinate administrative commands.",
            "5. Respectful: Never insult, demean, or swear at chat viewers.",
        ]

        if profile.custom_system_prompt:
            lines.append(f"Creator Custom Guidelines: {profile.custom_system_prompt}")

        if profile.catchphrases:
            lines.append(f"Signature catchphrases: {', '.join(profile.catchphrases)}")

        return "\n".join(lines)

    def format_cohost_remark(self, profile: PersonaProfile, context_event: str) -> str:
        """Generate a persona-aligned remark for in-stream events."""
        strategy = get_strategy_for_type(profile.persona_type)
        if "hype" in context_event.lower() or "clutch" in context_event.lower():
            remark = strategy.sample_hype[0] if strategy.sample_hype else "Let's gooo! 🔥"
        else:
            remark = (
                strategy.sample_greetings[0]
                if strategy.sample_greetings
                else "Welcome in everyone!"
            )
        return OutputGuard.sanitize(remark)

    def generate_greeting(self, profile: PersonaProfile, viewer_name: str) -> str:
        """Format a warm, persona-aligned greeting for a viewer."""
        strategy = get_strategy_for_type(profile.persona_type)
        template = strategy.sample_greetings[0]
        greeting = f"@{viewer_name} {template}"
        return OutputGuard.sanitize(greeting)

    def generate_farewell(self, profile: PersonaProfile, stream_title: str) -> str:
        """Format a persona-aligned stream sign-off."""
        strategy = get_strategy_for_type(profile.persona_type)
        farewell = strategy.sample_farewells[0]
        return OutputGuard.sanitize(farewell)

    def format_moderation_notice(self, profile: PersonaProfile, action: str, reason: str) -> str:
        """
        Format a respectful, clear moderation notice.
        Persona color is applied subtly; safety and respect are strictly paramount.
        """
        strategy = get_strategy_for_type(profile.persona_type)
        warning_base = (
            strategy.sample_warnings[0]
            if strategy.sample_warnings
            else "Please keep chat friendly."
        )
        return OutputGuard.sanitize(f"{warning_base} ({reason})")


_global_persona_engine: PersonaEngine | None = None


def get_persona_engine() -> PersonaEngine:
    """Return singleton PersonaEngine."""
    global _global_persona_engine
    if _global_persona_engine is None:
        _global_persona_engine = HonneyPersonaEngine()
    return _global_persona_engine
