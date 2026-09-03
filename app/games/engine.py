"""Deterministic participation mini-game engine without gambling or betting mechanics."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.mini_game import MiniGameSession
from app.db.repositories.engagement_repo import EngagementRepository
from app.db.repositories.game_repo import GameRepository
from app.economy.ledger import EconomyService
from app.engagement.xp import XPManager

logger = get_logger("app.games.engine")


class MiniGameEngine:
    """
    Lightweight deterministic live chat mini-game engine.
    Completely free of gambling, bets, or real-money value.
    Provides Trivia, Word Scramble, Reaction, and Number Guessing.
    """

    TRIVIA_QUESTIONS = [
        {"q": "What is the capital of India?", "a": ["new delhi", "delhi"]},
        {"q": "Which planet is known as the Red Planet?", "a": ["mars"]},
        {"q": "How many players are on the field for one soccer team?", "a": ["11", "eleven"]},
        {"q": "What is the primary currency of Japan?", "a": ["yen"]},
        {"q": "Who created Python programming language?", "a": ["guido van rossum", "guido"]},
        {
            "q": "What is the speed of light in vacuum approximately? (in km/s)",
            "a": ["300000", "300,000"],
        },
        {"q": "What does CPU stand for?", "a": ["central processing unit"]},
    ]

    SCRAMBLE_WORDS = [
        {"word": "HONNEY", "scrambled": "E N O Y H N"},
        {"word": "STREAM", "scrambled": "M T E R A S"},
        {"word": "GAMING", "scrambled": "M G I N A G"},
        {"word": "VICTORY", "scrambled": "Y T C R V I O"},
        {"word": "CHAMPION", "scrambled": "P M C N H I A O"},
    ]

    def __init__(self, xp_manager: XPManager | None = None) -> None:
        self.xp_manager = xp_manager or XPManager()
        # In-memory rate limiting: (creator_id, stream_session_id) -> last_game_started_at
        self._last_game_started: dict[tuple[str, str], float] = {}

    async def start_game(
        self,
        session: AsyncSession,
        creator_id: str,
        stream_session_id: str,
        game_type: str = "TRIVIA",
        duration_seconds: int = 60,
    ) -> tuple[bool, str, MiniGameSession | None]:
        """Start a new participation game for a stream session."""
        repo = GameRepository(session)
        now_ts = datetime.now(UTC).timestamp()
        key = (creator_id, stream_session_id)

        # 1. Check if an active game is already running
        existing = await repo.get_active_game(creator_id, stream_session_id)
        if existing:
            return (
                False,
                f"An active {existing.game_type} game is already running! Prompt: {existing.prompt_text}",
                existing,
            )

        # 2. Check game start cooldown (minimum 60s between games)
        last_start = self._last_game_started.get(key, 0.0)
        if now_ts - last_start < 60.0:
            remaining = int(60.0 - (now_ts - last_start))
            return False, f"Game cooldown active. Please wait {remaining}s.", None

        # 3. Build game question and solution
        gt = game_type.upper()
        if gt == "TRIVIA":
            item = random.choice(self.TRIVIA_QUESTIONS)
            prompt = f"🎯 [TRIVIA]: {item['q']} (First correct answer wins!)"
            solution = {"type": "TRIVIA", "answers": item["a"]}
        elif gt in ("WORD_SCRAMBLE", "WORD"):
            gt = "WORD_SCRAMBLE"
            item = random.choice(self.SCRAMBLE_WORDS)
            prompt = f"🔤 [WORD SCRAMBLE]: Unscramble the letters: {item['scrambled']} (Reward: 50 XP, 25 Coins!)"
            solution = {"type": "WORD_SCRAMBLE", "answer": item["word"].lower()}
        elif gt == "REACTION":
            target = f"GG {random.randint(10, 99)}"
            prompt = f"⚡ [REACTION SPEED]: First person to type '{target}' in chat wins!"
            solution = {"type": "REACTION", "answer": target.lower()}
        else:
            gt = "TRIVIA"
            item = random.choice(self.TRIVIA_QUESTIONS)
            prompt = f"🎯 [TRIVIA]: {item['q']}"
            solution = {"type": "TRIVIA", "answers": item["a"]}

        expires_at = datetime.now(UTC) + timedelta(seconds=duration_seconds)
        game_session = await repo.create_game(
            creator_id=creator_id,
            stream_session_id=stream_session_id,
            game_type=gt,
            prompt_text=prompt,
            solution_data=solution,
            reward_xp=50,
            reward_coins=25,
            expires_at=expires_at,
        )

        self._last_game_started[key] = now_ts
        await session.flush()
        logger.info(f"Started {gt} game session {game_session.id} on stream {stream_session_id}")
        return True, prompt, game_session

    async def evaluate_chat_guess(
        self,
        session: AsyncSession,
        creator_id: str,
        stream_session_id: str,
        viewer_channel_id: str,
        viewer_display_name: str,
        chat_text: str,
    ) -> tuple[bool, str | None]:
        """
        Evaluate incoming chat message against active mini-game solution.
        If correct, settles winner reward and completes game.
        Returns (is_winner: bool, announcement_message: str | None).
        """
        repo = GameRepository(session)
        game = await repo.get_active_game(creator_id, stream_session_id)
        if not game:
            return False, None

        guess = chat_text.strip().lower()
        solution = game.solution_data
        is_correct = False

        if game.game_type == "TRIVIA":
            accepted = solution.get("answers", [])
            is_correct = any(a.lower() in guess for a in accepted)
        elif game.game_type in ("WORD_SCRAMBLE", "REACTION"):
            target = solution.get("answer", "").lower()
            is_correct = target in guess

        if not is_correct:
            return False, None

        # 1. Complete game
        await repo.complete_game(game.id, viewer_channel_id, viewer_display_name)

        # 2. Reward winner XP
        eng_repo = EngagementRepository(session)
        profile = await eng_repo.get_or_create(creator_id, viewer_channel_id, viewer_display_name)
        new_level = self.xp_manager.calculate_level_from_xp(profile.total_xp + game.reward_xp)
        await eng_repo.award_xp(profile, game.reward_xp, new_level)
        await eng_repo.record_game(profile, won=True)

        # 3. Reward winner Coins via Double-Entry Ledger
        economy = EconomyService(session)
        await economy.earn(
            creator_id=creator_id,
            viewer_channel_id=viewer_channel_id,
            amount=game.reward_coins,
            reason=f"Won {game.game_type} mini-game",
            idempotency_key=f"gamewin:{game.id}:{viewer_channel_id}",
            reference_type="mini_game",
            reference_id=game.id,
        )

        await session.flush()
        announcement = (
            f"🏆 Correct! @{viewer_display_name} won the {game.game_type} game! "
            f"(+{game.reward_xp} XP, +{game.reward_coins} Coins)"
        )
        logger.info(announcement)
        return True, announcement
