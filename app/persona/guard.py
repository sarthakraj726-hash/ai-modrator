"""Output guard ensuring conciseness, safety, and prompt leakage defense."""

import re


class OutputGuard:
    """
    Sanitizes and enforces production output guardrails for all AI-generated text:
    1. Brevity: Caps length to at most 1-2 short sentences (<= 200 chars).
    2. Prompt Leakage Defense: Strips system instructions, role markers, and internal delimiters.
    3. Secret Protection: Strips inadvertent API keys, tokens, and authorization headers.
    4. Code/JSON Strip: Prevents accidental raw JSON or markdown code blocks from spilling into live chat.
    """

    # Secret / Key patterns
    KEY_PATTERNS = [
        re.compile(r"(AIza[0-9A-Za-z-_]{35})"),
        re.compile(r"(sk-or-v1-[0-9a-f]{64})"),
        re.compile(r"(Bearer\s+[A-Za-z0-9-_.]+)"),
    ]

    # Delimiter and leakage patterns
    LEAKAGE_PATTERNS = [
        re.compile(r"System prompt:.*", re.IGNORECASE),
        re.compile(r"As an AI co-host,.*", re.IGNORECASE),
        re.compile(r"\[Internal Rule:.*\]", re.IGNORECASE),
        re.compile(r"```[a-z]*[\s\S]*?```"),  # Code blocks
    ]

    @classmethod
    def sanitize(cls, text: str, max_chars: int = 200) -> str:
        """Sanitize AI response before dispatching to live chat."""
        if not text:
            return ""

        cleaned = text.strip()

        # 1. Remove markdown code blocks and internal instruction markers
        for pat in cls.LEAKAGE_PATTERNS:
            cleaned = pat.sub("", cleaned).strip()

        # 2. Redact any leaked API keys or secrets
        for pat in cls.KEY_PATTERNS:
            cleaned = pat.sub("[REDACTED]", cleaned)

        # 3. Strip extra quotes wrapping the output
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1].strip()

        # 4. Enforce max character limit (truncate at last sentence or word boundary)
        if len(cleaned) > max_chars:
            sentences = re.split(r"(?<=[.!?]) +", cleaned)
            accumulated = ""
            for s in sentences:
                if len(accumulated) + len(s) + 1 <= max_chars:
                    accumulated = f"{accumulated} {s}".strip()
                else:
                    break
            if accumulated:
                cleaned = accumulated
            else:
                cleaned = cleaned[: max_chars - 3].rstrip() + "..."

        return cleaned
