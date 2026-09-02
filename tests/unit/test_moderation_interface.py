"""Unit tests for Moderation, Persona, and Command interface models."""

from app.commands.models import ChatCommand
from app.core.rbac import Role
from app.moderation.models import (
    ModerationAction,
    ModerationDecision,
    ModerationLayer,
)
from app.persona.models import PersonaProfile, PersonaType, ToneSetting


def test_moderation_models():
    decision = ModerationDecision(
        action=ModerationAction.WARN,
        layer=ModerationLayer.LAYER_1_LIGHT_WARNING,
        reason="Excessive caps",
        suggested_timeout_seconds=0,
    )
    assert decision.action == ModerationAction.WARN
    assert decision.layer == ModerationLayer.LAYER_1_LIGHT_WARNING


def test_persona_models():
    profile = PersonaProfile(
        name="Goddess",
        persona_type=PersonaType.CO_HOST,
        tone=ToneSetting(energy_level=9, humor_level=8),
        catchphrases=["Let's go!", "Namaste chat!"],
    )
    assert profile.name == "Goddess"
    assert profile.persona_type == PersonaType.CO_HOST
    assert profile.tone.energy_level == 9


def test_command_models():
    cmd = ChatCommand(
        name="!uk",
        description="UK command",
        min_role=Role.MODERATOR,
        cooldown_seconds=10,
    )
    assert cmd.name == "!uk"
    assert cmd.min_role == Role.MODERATOR
