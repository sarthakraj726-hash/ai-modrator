"""Persona models and voice configuration schemas."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PersonaType(str, Enum):
    HYPE = "HYPE"
    PLAYFUL = "PLAYFUL"
    WITTY = "WITTY"
    HELPFUL = "HELPFUL"
    CO_HOST = "CO_HOST"
    ADAPTIVE = "ADAPTIVE"
    CUSTOM = "CUSTOM"


class ToneSetting(BaseModel):
    energy_level: int = Field(default=7, ge=1, le=10)
    humor_level: int = Field(default=8, ge=1, le=10)
    strictness_level: int = Field(default=4, ge=1, le=10)
    emojis_enabled: bool = True
    hinglish_allowed: bool = True


class PersonaProfile(BaseModel):
    name: str = "Goddess"
    persona_type: PersonaType = PersonaType.CO_HOST
    custom_system_prompt: str = ""
    tone: ToneSetting = Field(default_factory=ToneSetting)
    creator_context: dict[str, Any] = Field(default_factory=dict)
    catchphrases: list[str] = Field(default_factory=list)
