"""Multilingual text normalizer for Unicode, leet-speak, and repetition folding."""

import re
import unicodedata


class MultilingualNormalizer:
    """
    Normalizes chat messages to standard forms for reliable rule matching
    and adversarial evasion detection without destroying natural emotional emphasis.
    """

    # Zero-width and invisible character regex
    ZERO_WIDTH_REGEX = re.compile(r"[\u200B-\u200D\uFEFF\u200E\u200F\u00AD]")

    # Leet substitutions mapping
    LEET_MAP = {
        "@": "a",
        "$": "s",
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
    }

    # Regex for 3 or more repeated letters
    REPEATED_CHARS_REGEX = re.compile(r"(.)\1{2,}", re.IGNORECASE)

    # Regex for excessive repeated punctuation
    REPEATED_PUNCT_REGEX = re.compile(r"([!?.,~])\1{2,}")

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Full normalization pipeline:
        1. Unicode NFKC canonicalization
        2. Zero-width character removal
        3. Folding 3+ character repetitions to 2 chars (e.g. 'nooooob' -> 'noob')
        4. Trimming and space normalization
        """
        if not text:
            return ""

        # 1. NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Strip zero-width invisible characters
        normalized = cls.ZERO_WIDTH_REGEX.sub("", normalized)

        # 3. Fold excessive character repetitions (leave at most 2)
        normalized = cls.REPEATED_CHARS_REGEX.sub(r"\1\1", normalized)

        # 4. Fold excessive punctuation (e.g. '?????' -> '??')
        normalized = cls.REPEATED_PUNCT_REGEX.sub(r"\1\1", normalized)

        # 5. Clean whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    @classmethod
    def deobfuscate_leet(cls, text: str) -> str:
        """
        Translates common leet substitutions for rule checks (e.g. 'h@ck3r' -> 'hacker').
        """
        res = []
        for char in text:
            res.append(cls.LEET_MAP.get(char, char))
        return "".join(res)
