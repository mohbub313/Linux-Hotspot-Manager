"""
Internationalization (i18n) module for Linux Hotspot Manager.
Supports 12 languages matching MyPublicWiFi:
English (en), Spanish (es), French (fr), German (de), Italian (it),
Portuguese (pt), Russian (ru), Arabic (ar), Turkish (tr), Chinese (zh),
Hindi (hi), Bengali (bn).
"""
import json
import os
from pathlib import Path

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "it": "Italiano (Italian)",
    "pt": "Português (Portuguese)",
    "ru": "Русский (Russian)",
    "ar": "العربية (Arabic)",
    "tr": "Türkçe (Turkish)",
    "zh": "中文 (Chinese)",
    "hi": "हिन्दी (Hindi)",
    "bn": "বাংলা (Bengali)",
}

class I18n:
    def __init__(self, current_lang="en"):
        self.current_lang = current_lang
        self.translations = {}
        self._listeners = []
        self._find_lang_dir()
        self.load_language(current_lang)

    def _find_lang_dir(self):
        candidates = [
            Path(__file__).parent.parent / "data" / "lang",
            Path("/usr/share/linux-hotspot-manager/lang"),
            Path("/usr/local/share/linux-hotspot-manager/lang"),
        ]
        for p in candidates:
            if p.is_dir():
                self.lang_dir = p
                return
        self.lang_dir = candidates[0]

    def load_language(self, lang_code):
        if lang_code not in SUPPORTED_LANGUAGES:
            lang_code = "en"
        self.current_lang = lang_code
        file_path = self.lang_dir / f"{lang_code}.json"
        if file_path.exists():
            try:
                self.translations = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                self.translations = {}
        else:
            self.translations = {}

        # Notify listeners
        for listener in self._listeners:
            try:
                listener()
            except Exception:
                pass

    def add_listener(self, callback):
        self._listeners.append(callback)

    def t(self, key, default=None):
        return self.translations.get(key, default or key)

    def __call__(self, key, default=None):
        return self.t(key, default)

# Global singleton
i18n = I18n("en")
_ = i18n
