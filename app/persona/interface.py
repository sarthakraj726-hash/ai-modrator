"""Persona Engine abstract interface."""

from abc import ABC, abstractmethod

from app.persona.models import PersonaProfile


class PersonaEngine(ABC):
    """Strategy interface ensuring consistent AI persona voice and responses."""

    @abstractmethod
    def build_system_prompt(self, profile: PersonaProfile, channel_context: dict) -> str:
        """Compose the full system prompt embedding persona voice and guidelines."""
        pass

    @abstractmethod
    def format_cohost_remark(self, profile: PersonaProfile, context_event: str) -> str:
        """Generate a persona-aligned remark for in-stream events."""
        pass
