# Deterministic Live Chat Mini-Games Architecture

## Non-Gambling Engagement Philosophy
Goddess AI enforces a strict non-gambling guarantee:
- Zero real-money value or cash redemption.
- No betting, wagering, or pay-to-play mechanics.
- All games are free participation activities rewarding activity and knowledge.

---

## Game Types & Mechanics

### 1. Trivia (`TRIVIA`)
- **Trigger**: `!trivia`
- **Mechanics**: Honney broadcasts a family-safe question. The first viewer to type the correct answer in chat wins.
- **Reward**: 50 XP, 25 Coins.

### 2. Word Scramble (`WORD_SCRAMBLE`)
- **Trigger**: `!word`
- **Mechanics**: Honney scrambles letters for a gaming or tech word (e.g. `E N O Y H N` -> `HONNEY`). The first viewer to unscramble it in chat wins.
- **Reward**: 50 XP, 25 Coins.

### 3. Reaction Speed (`REACTION`)
- **Trigger**: `!reaction`
- **Mechanics**: Honney broadcasts a random target string (e.g. `GG 42`). The fastest chatter to type the target wins.
- **Reward**: 50 XP, 25 Coins.

---

## Isolation & Concurrency Control
- **Session Scoping**: Active games are indexed by `(creator_id, stream_session_id, state)`.
- **Anti-Spam Cooldown**: Minimum 60-second cooldown between consecutive mini-game sessions.
- **Automatic Expiration**: Unanswered games expire after 60 seconds.
