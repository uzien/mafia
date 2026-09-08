import json
from pathlib import Path
from typing import Any, Dict

LOCALES_DIR = Path(__file__).parent

SUPPORTED_LANGUAGES = {
    "az": "🇦🇿 Azərbaycan",
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "tr": "🇹🇷 Türkçe"
}

class Localization:
    def __init__(self):
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.default_lang = "uz"
        self._load_translations()

    def _load_translations(self):
        for code in SUPPORTED_LANGUAGES.keys():
            file_path = LOCALES_DIR / f"{code}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.translations[code] = json.load(f)
                except Exception as e:
                    print(f"Error loading {code}.json: {e}")
                    self.translations[code] = {}
            else:
                self.translations[code] = {}

    def get(self, key: str, lang: str = "uz", **kwargs) -> str:
        """Fetch localized string with fallback and string formatting."""
        if lang not in self.translations:
            lang = self.default_lang

        # Support dot-notation: e.g. "roles.doctor"
        keys = key.split(".")
        data = self.translations.get(lang, {})
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                data = None
                break

        # Fallback to default language if key missing in chosen lang
        if data is None and lang != self.default_lang:
            data = self.translations.get(self.default_lang, {})
            for k in keys:
                if isinstance(data, dict):
                    data = data.get(k)
                else:
                    data = None
                    break

        if data is None:
            return f"[{key}]"

        if isinstance(data, str) and kwargs:
            try:
                return data.format(**kwargs)
            except Exception:
                return data
        return str(data)

i18n = Localization()
