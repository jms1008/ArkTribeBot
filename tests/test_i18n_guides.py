"""Tests de las guías de /info y /help: paridad de claves ES/EN y selector."""

from cogs.management import get_info_texts
from locales.guides_en import INFO_TEXTS_EN
from locales.guides_es import INFO_TEXTS


def test_es_and_en_guides_have_same_keys():
    """Ambos idiomas deben cubrir exactamente los mismos módulos."""
    assert set(INFO_TEXTS.keys()) == set(INFO_TEXTS_EN.keys())


def test_no_empty_guides():
    for key, text in {**INFO_TEXTS, **INFO_TEXTS_EN}.items():
        assert text.strip(), f"Guía vacía: {key}"


def test_get_info_texts_picks_language():
    assert get_info_texts("en") is INFO_TEXTS_EN
    assert get_info_texts("es") is INFO_TEXTS
    # Idioma desconocido cae a español.
    assert get_info_texts("fr") is INFO_TEXTS


def test_en_guides_actually_translated():
    """Verificación ligera de que el inglés no es un copia-pega del español."""
    assert INFO_TEXTS_EN["todo_list"] != INFO_TEXTS["todo_list"]
    assert "TASK" in INFO_TEXTS_EN["todo_list"].upper()
