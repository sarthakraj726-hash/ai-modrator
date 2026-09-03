"""Multilingual language detection for English, Hindi, Hinglish, and mixed chat."""

import re
import unicodedata


class LanguageDetector:
    """
    Fast, deterministic language classifier distinguishing English,
    Devanagari Hindi, Hinglish (Romanized Hindi), and mixed scripts.
    """

    # Common Hinglish marker words and particles
    HINGLISH_MARKERS = {
        "bhai",
        "bhaiya",
        "bro",
        "kya",
        "kyu",
        "kyun",
        "kaise",
        "kaha",
        "kahan",
        "haan",
        "nahi",
        "nhi",
        "nahin",
        "mat",
        "kar",
        "karo",
        "karna",
        "raha",
        "rahi",
        "rahe",
        "hai",
        "hain",
        "ho",
        "tha",
        "thi",
        "the",
        "aaj",
        "kal",
        "ab",
        "yeh",
        "ye",
        "woh",
        "wo",
        "kuch",
        "sab",
        "apna",
        "apne",
        "meri",
        "mera",
        "mere",
        "tera",
        "teri",
        "tere",
        "tum",
        "aap",
        "hum",
        "mast",
        "badhiya",
        "ekdum",
        "scene",
        "bakchodi",
        "chup",
        "pagal",
        "sahi",
        "bol",
        "dekh",
        "sun",
        "ruk",
        "chal",
        "jaa",
        "aaja",
        "le",
        "de",
        "do",
        "yaar",
        "dost",
        "aisa",
        "waisa",
        "toh",
        "to",
        "bhi",
        "sirf",
        "bas",
    }

    # Devanagari Unicode range
    DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")

    @classmethod
    def detect_language(cls, text: str) -> str:
        """
        Detect language of chat message: 'en', 'hi', 'hinglish', or 'mixed'.
        """
        if not text or not text.strip():
            return "en"

        cleaned = unicodedata.normalize("NFKC", text).strip()

        # Check for Devanagari script
        devanagari_chars = len(cls.DEVANAGARI_REGEX.findall(cleaned))
        total_letters = sum(1 for c in cleaned if c.isalpha())

        if total_letters == 0:
            return "en"

        # If significant Devanagari content
        if devanagari_chars / total_letters > 0.4:
            if devanagari_chars / total_letters < 0.8:
                return "mixed"
            return "hi"

        # Check Romanized Hinglish vocabulary
        words = re.findall(r"\b[a-zA-Z]+\b", cleaned.lower())
        if not words:
            return "en"

        hinglish_hits = sum(1 for w in words if w in cls.HINGLISH_MARKERS)
        hinglish_ratio = hinglish_hits / len(words)

        if hinglish_hits >= 1 and (hinglish_ratio >= 0.2 or len(words) <= 3):
            return "hinglish"

        return "en"

    @classmethod
    def is_hinglish_or_hindi(cls, text: str) -> bool:
        """Helper to check if content contains Indian linguistic patterns."""
        lang = cls.detect_language(text)
        return lang in ("hi", "hinglish", "mixed")
