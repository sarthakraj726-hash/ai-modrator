"""Unit tests for Multilingual NLP, Hinglish detection, and slang normalization."""

from app.moderation.nlp.language import LanguageDetector
from app.moderation.nlp.normalizer import MultilingualNormalizer
from app.moderation.nlp.slang import SlangNormalizer


class TestLanguageDetector:
    def test_detect_english(self):
        assert LanguageDetector.detect_language("Great gameplay today streamer!") == "en"
        assert LanguageDetector.detect_language("Can you please play another game?") == "en"

    def test_detect_hindi_devanagari(self):
        assert LanguageDetector.detect_language("आज का गेम बहुत बढ़िया था") == "hi"

    def test_detect_hinglish_romanized(self):
        assert LanguageDetector.detect_language("bhai ye banda pagal hai") == "hinglish"
        assert LanguageDetector.detect_language("kya scene hai aaj ka?") == "hinglish"
        assert LanguageDetector.detect_language("tu bohot mast khel raha hai") == "hinglish"

    def test_detect_mixed(self):
        assert LanguageDetector.detect_language("OP clutch bhai बहुत मस्त") == "mixed"


class TestMultilingualNormalizer:
    def test_zero_width_character_stripping(self):
        # Text with hidden zero-width spaces (\u200b)
        obfuscated = "b\u200bh\u200ba\u200bi"
        normalized = MultilingualNormalizer.normalize_text(obfuscated)
        assert normalized == "bhai"

    def test_repetition_folding(self):
        # Folds 3+ repeated characters down to 2
        assert MultilingualNormalizer.normalize_text("nooooooob") == "noob"
        assert MultilingualNormalizer.normalize_text("bhaaaaaaai") == "bhaai"
        assert MultilingualNormalizer.normalize_text("hellooooo!!!!!!") == "helloo!!"

    def test_leet_deobfuscation(self):
        assert MultilingualNormalizer.deobfuscate_leet("h@ck3r") == "hacker"
        assert MultilingualNormalizer.deobfuscate_leet("$c@m") == "scam"


class TestSlangNormalizer:
    def test_playful_banter_recognition(self):
        # Banter paired with laugh emojis or gaming slang
        assert SlangNormalizer.is_likely_playful_banter("bhai ye banda pagal hai 😂") is True
        assert SlangNormalizer.is_likely_playful_banter("tu noob hai lol") is True
        assert SlangNormalizer.is_likely_playful_banter("kya bakchodi kar raha hai xd") is True

    def test_severe_slur_detection(self):
        # Severe profanity is never flagged as playful banter
        assert SlangNormalizer.has_severe_slur("chup madarchod") is True
        assert SlangNormalizer.has_severe_slur("teri ma ki chut") is True
        assert SlangNormalizer.is_likely_playful_banter("chup madarchod 😂") is False
