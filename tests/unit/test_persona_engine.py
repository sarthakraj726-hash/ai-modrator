"""Unit tests for Honney Persona Engine, Adaptive Transitions, and OutputGuard."""

import time

from app.persona.adaptive import AdaptivePersonaStateMachine
from app.persona.engine import HonneyPersonaEngine
from app.persona.guard import OutputGuard
from app.persona.models import PersonaProfile, PersonaType
from app.persona.profiles import get_strategy_for_type


class TestPersonaProfiles:
    def test_all_six_persona_strategies_exist(self):
        types = [
            PersonaType.HYPE,
            PersonaType.PLAYFUL,
            PersonaType.WITTY,
            PersonaType.HELPFUL,
            PersonaType.CO_HOST,
            PersonaType.ADAPTIVE,
        ]
        for t in types:
            strat = get_strategy_for_type(t)
            assert strat is not None
            assert len(strat.sample_greetings) > 0
            assert len(strat.sample_warnings) > 0
            assert len(strat.sample_farewells) > 0

    def test_system_prompt_builder(self):
        engine = HonneyPersonaEngine()
        profile = PersonaProfile(
            name="Honney",
            persona_type=PersonaType.HYPE,
            catchphrases=["Let's cook!"],
        )
        prompt = engine.build_system_prompt(
            profile, {"creator_name": "ProGamer", "game_title": "Valorant"}
        )
        assert "ProGamer" in prompt
        assert "Valorant" in prompt
        assert "Let's cook!" in prompt
        assert "200 characters" in prompt


class TestAdaptivePersonaStateMachine:
    def test_hysteresis_dwell_time(self):
        sm = AdaptivePersonaStateMachine(dwell_time_seconds=1.0)
        # Normal chat -> CO_HOST
        s1 = sm.evaluate_state(chat_velocity_per_min=20, question_density_ratio=0.1)
        assert s1 == PersonaType.CO_HOST

        # Sudden spike in questions within 0.1s -> locked in dwell period!
        s2 = sm.evaluate_state(chat_velocity_per_min=20, question_density_ratio=0.8)
        assert s2 == PersonaType.CO_HOST

        # After dwell time expires -> transitions to HELPFUL
        time.sleep(1.1)
        s3 = sm.evaluate_state(chat_velocity_per_min=20, question_density_ratio=0.8)
        assert s3 == PersonaType.HELPFUL


class TestOutputGuard:
    def test_output_guard_brevity(self):
        long_text = "This is sentence one. " * 20
        sanitized = OutputGuard.sanitize(long_text, max_chars=100)
        assert len(sanitized) <= 100

    def test_output_guard_secret_redaction(self):
        text_with_key = "Check out my key AIzaSyD4j5k6L7m8N9p0Q1r2S3t4U5v6W7x8Y9z"
        sanitized = OutputGuard.sanitize(text_with_key)
        assert "AIza" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_output_guard_prompt_leakage_strip(self):
        text = "As an AI co-host, I think that play was great!"
        sanitized = OutputGuard.sanitize(text)
        assert "As an AI co-host" not in sanitized
