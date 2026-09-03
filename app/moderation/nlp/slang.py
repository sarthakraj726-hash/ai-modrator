"""Slang normalizer and contextual intent classifier for Indian internet and gaming vocabulary."""

import re


class SlangNormalizer:
    """
    Distinguishes playful banter, gaming trash talk, and friendly roasts
    from genuine targeted harassment and hate speech.
    """

    # Innocent gaming slang & hype terms (NEVER punish by default)
    GAMING_HYPE_SLANG = {
        "op",
        "gg",
        "mast",
        "badhiya",
        "khatarnak",
        "scene",
        "bhai",
        "bro",
        "clutch",
        "headshot",
        "bot",
        "noob",
        "legend",
        "pro",
        "level",
    }

    # Playful banter keywords often paired with humor emojis
    PLAYFUL_BANTER_WORDS = {
        "pagal",
        "chup",
        "bakchodi",
        "abe",
        "sala",
        "saale",
        "gadha",
        "ullu",
        "dhakkan",
        "nalla",
        "tatti",
        "fek",
        "phenk",
        "nautanki",
    }

    # Severe abusive roots that constitute harassment or hate
    SEVERE_ABUSIVE_ROOTS = [
        r"\bchutiya\b",
        r"\bgandu\b",
        r"\brnd[iey]\b",
        r"\brandi\b",
        r"\bmadarchod\b",
        r"\bmc\b",
        r"\bbehenchod\b",
        r"\bbc\b",
        r"\bbhosd[iey]\b",
        r"\blund\b",
        r"\bloda\b",
        r"\blouda\b",
        r"\bch[ou]+t\b",
        r"\bgaand\b",
        r"\bkamina\b",
        r"\bharami\b",
    ]

    SEVERE_REGEX = re.compile("|".join(SEVERE_ABUSIVE_ROOTS), re.IGNORECASE)

    # Positive and laughing emojis signaling playful banter
    LAUGH_EMOJIS = {"😂", "🤣", "😆", "😅", "😹", "xd", "lol", "lmao", "rofl"}

    @classmethod
    def has_severe_slur(cls, text: str) -> bool:
        """Check if text contains unambiguous profanity or slurs."""
        return bool(cls.SEVERE_REGEX.search(text))

    @classmethod
    def is_likely_playful_banter(cls, text: str) -> bool:
        """
        Check if message shows strong signals of playful banter/friendly roast:
        - Contains friendly banter terms ('pagal', 'noob', 'bot')
        - Has laughing emojis or 'lol'/'lmao'
        - Lacks severe hate slurs or violent threats
        """
        lower = text.lower()

        # Severe slurs are never categorized as innocent banter
        if cls.has_severe_slur(lower):
            return False

        has_laugh = any(em in lower for em in cls.LAUGH_EMOJIS)
        words = set(re.findall(r"\b[a-zA-Z]+\b", lower))

        has_banter_word = bool(words.intersection(cls.PLAYFUL_BANTER_WORDS))
        has_hype_word = bool(words.intersection(cls.GAMING_HYPE_SLANG))

        # "bhai ye banda pagal hai 😂" or "tu noob hai lol"
        if (has_banter_word or has_hype_word) and has_laugh:
            return True

        # Short friendly gaming teasing: "noob lol", "bot hai kya"
        if "noob" in words or "bot" in words:
            if "mar ja" not in lower and "uninstall" not in lower:
                return True

        return False
