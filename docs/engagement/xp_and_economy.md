# XP Progression & Double-Entry Virtual Economy

## XP Progression Model

The XP progression curve follows a deterministic formula:
$$\text{required\_xp}(L) = \text{base\_xp} \times (L^{\text{multiplier}})$$
where:
- $\text{base\_xp} = 100$
- $\text{multiplier} = 1.5$

### Anti-Farming Defenses
To prevent spam farming, the `AntiFarmingGuard` applies multiple defensive checks:
1. **Cooldown Suppression**: Minimum 60-second cooldown between XP awards per viewer.
2. **Quality Filter**:
   - Rejects messages shorter than 4 characters.
   - Rejects character repetition (e.g. `aaaaaaa`, `111111`).
   - Rejects single-word repetitive spam (e.g. `lol lol lol lol`).
   - Rejects emoji-only messages.
3. **Burst Velocity Cap**: Maximum 6 awards per 10-minute sliding window.
4. **Daily XP Cap**: Maximum 2,500 XP per viewer per calendar day.

---

## Double-Entry Virtual Coin Ledger

All coins are virtual engagement tokens with zero cash value. No real-money gambling, cash conversions, or betting mechanisms are permitted.

### Accounting Balancing Principle
Every coin movement is encapsulated in an `EconomyTransaction` with balanced `EconomyLedgerEntry` records summing to zero:
$$\sum \text{Debits} + \sum \text{Credits} = 0$$

### Accounts & Directions
- **SYSTEM_MINT**: Used to mint rewards and grants. Debited when coins are awarded.
- **SYSTEM_SINK**: Sinks coins spent in the store. Credited when coins are spent.
- **VIEWER**: Scoped strictly by `(creator_id, viewer_channel_id)`.
  - **Credit**: Increases viewer balance ($+\text{amount}$).
  - **Debit**: Decreases viewer balance ($-\text{amount}$).

### Concurrency & Idempotency
- Row-level locks (`with_for_update`) ensure that concurrent requests cannot spend beyond available funds or produce negative balances.
- Unique constraint on `(creator_id, idempotency_key)` guarantees that duplicate chat events or replay attacks produce zero duplicate minting.
