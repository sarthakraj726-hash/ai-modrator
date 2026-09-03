# Goddess AI — 5-Layer Progressive Moderation, Hinglish NLP & HITL Review Contract

## 1. Five-Layer Progressive Moderation Hierarchy

Rather than punishing users with immediate bans or arbitrary timeouts, Goddess AI implements a 5-layer progressive moderation model:

```
[Layer 0 / 1] Light Warning (Public friendly nudge or silent warning flag)
      ↓
[Layer 2]     Warning + Delete offending message from YouTube Live Chat
      ↓
[Layer 3]     Short Timeout (300 seconds) + Strong Warning
      ↓
[Layer 4]     Extended Timeout (1800-3600 seconds)
      ↓
[Layer 5]     Hide User from Channel (Permanent YouTube Live Chat Shadowban)
```

---

## 2. 2D Policy Decision Matrix (Confidence × Severity)

Enforcement actions are decided using a two-dimensional matrix combining model confidence and offense severity:

| Confidence Score | Violation Severity | Decision | Action Route |
| :--- | :--- | :--- | :--- |
| `< 40%` | Any | **ALLOW** | Benign / Uncertain; do not punish |
| `40% – 89%` | Mild / Moderate / Severe | **FLAG_FOR_REVIEW** | Dispatched to Human-In-The-Loop Review queue |
| `>= 90%` | Low (`1 – 35`) | **WARN** | Layer 1: Friendly warning |
| `>= 90%` | Moderate (`36 – 65`) | **DELETE** | Layer 2: Warning + Delete |
| `>= 90%` | High (`66 – 85`) | **TIMEOUT** | Layer 3: Short Timeout (300s) |
| `>= 90%` | Extreme (`86 – 100`)| **BAN** | Layer 5: Hide User from Channel |

---

## 3. Multilingual & Hinglish NLP Engine

Indian gaming and live-streaming chats feature extensive code-mixing between English, Devanagari Hindi, transliterated Roman Hindi, and local gaming slang.

### Text Normalization Pipeline
1. **Unicode NFKC & Zero-Width Stripping**: Strips zero-width joiners, soft hyphens, and RTL overrides commonly used to bypass regex filters.
2. **Repetition Folding**: Folds character elongations (e.g., `bhaaaaaai` -> `bhai`, `nooooooob` -> `noob`).
3. **Leet Deobfuscation**: Resolves digit and symbol leet replacements (e.g., `m@d@rch0d` -> `madarchod`, `b!tch` -> `bitch`).

### Slang & Banter Classification
- **Playful Banter**: Friendly ribbing such as *"bhai ye banda pagal hai 😂"*, *"abe noob khelna sikh"*, or *"kya fek raha hai lol"* accompanied by laugh emojis or gaming context is explicitly detected as banter and allowed immediately via local Layer 0 fast-path.
- **Severe Abuse**: Slurs targeting religion, caste, sexual violence, or family harassment trigger direct progressive enforcement or HITL review.

---

## 4. Human-In-The-Loop (HITL) Review Contract

Borderline cases (confidence `40-89%`) are converted into pending `ModerationReview` records and published to notification sinks:

1. **Discord Review Sink**: Webhook embed with rich details (author, message, context summary, confidence %, recommended action) and interactive buttons/commands.
2. **Chat Moderation Command**:
   - Approve: `!uk punish <review_id_prefix> yes [override_action]`
   - Deny: `!uk punish <review_id_prefix> no`

### Expiration TTL & Safe Fallback Invariant
- Every review has a strict TTL expiration (default 60s, configurable 30-120s).
- **Invariant**: If a review item expires before a moderator responds, it transitions to `EXPIRED`. **NO DESTRUCTIVE ACTIONS ARE EVER EXECUTED ON EXPIRED REVIEWS**. The application errs on the side of safety.
- **Race Condition Prevention**: State transitions are atomic (`PENDING` -> `APPROVED`/`DENIED`). Simultaneous moderator decisions result in `REVIEW_ALREADY_RESOLVED` for the second requester.

---

## 5. Viewer Trust Scoring

- Scored between `0` and `100` (initial default: `50`).
- Positive interactions, chat longevity, and clean moderation records reward trust increments (`+1` per clean interval).
- Violations decrement trust (`-10` to `-25`).
- **Trust Modification**: High-trust viewers (`trust >= 80`) receive benefit of the doubt—infractions are downgraded by 1 layer.
- **Strict Invariant**: High trust **NEVER** softens or overrides Layer 5 permanent bans for severe hate speech or threats.
