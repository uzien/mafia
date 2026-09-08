import pytest
from locales.i18n import SUPPORTED_LANGUAGES, i18n

def test_locales_loaded():
    for lang in SUPPORTED_LANGUAGES.keys():
        assert lang in i18n.translations, f"Language {lang} is not loaded in i18n"
        assert len(i18n.translations[lang]) > 0, f"Language {lang} has no keys"

def test_essential_keys_exist_in_all_languages():
    essential_keys = [
        "welcome",
        "help",
        "choose_lang",
        "lobby_created",
        "night_started",
        "voting_started",
        "victory_town",
        "victory_mafia",
        "victory_maniac",
        "profile_card",
        "shop_title",
        "roles.citizen",
        "roles.doctor",
        "roles.detective",
        "roles.don",
        "roles.mafia",
        "roles.maniac"
    ]
    for lang in SUPPORTED_LANGUAGES.keys():
        for key in essential_keys:
            val = i18n.get(key, lang)
            assert not val.startswith("[") or not val.endswith("]"), f"Key '{key}' missing in '{lang}'"

def test_parameter_formatting():
    # Test formatting on Azerbaijani
    formatted_az = i18n.get("player_joined", "az", name="Elvin", count=3, min=4)
    assert "Elvin" in formatted_az
    assert "3/4" in formatted_az

    # Test formatting on Uzbek
    formatted_uz = i18n.get("player_joined", "uz", name="Anvar", count=2, min=4)
    assert "Anvar" in formatted_uz
    assert "2/4" in formatted_uz
