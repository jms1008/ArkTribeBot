"""Tests del sistema i18n: resolución de idioma por scope y fallback de t()."""

import pytest

from locales.strings import STRINGS
from utils import i18n


@pytest.fixture(autouse=True)
def _clear_i18n_cache():
    """Limpia la caché de modo entre tests para evitar fugas de estado."""
    i18n.invalidate_lang_cache()
    yield
    i18n.invalidate_lang_cache()


class TestT:
    """Función de traducción t(key, lang, **fmt)."""

    def test_returns_target_language_string(self, monkeypatch):
        monkeypatch.setitem(STRINGS["es"], "demo.hi", "Hola")
        monkeypatch.setitem(STRINGS["en"], "demo.hi", "Hello")
        assert i18n.t("demo.hi", "en") == "Hello"
        assert i18n.t("demo.hi", "es") == "Hola"

    def test_falls_back_to_spanish_when_key_missing_in_english(self, monkeypatch):
        monkeypatch.setitem(STRINGS["es"], "demo.only_es", "Solo ES")
        # No existe en inglés → cae a ES.
        assert i18n.t("demo.only_es", "en") == "Solo ES"

    def test_returns_key_when_absent_everywhere(self):
        assert i18n.t("demo.nonexistent_key", "en") == "demo.nonexistent_key"

    def test_applies_format_kwargs(self, monkeypatch):
        monkeypatch.setitem(STRINGS["en"], "demo.count", "{n} tasks")
        assert i18n.t("demo.count", "en", n=5) == "5 tasks"

    def test_unknown_language_falls_back_to_spanish(self, monkeypatch):
        monkeypatch.setitem(STRINGS["es"], "demo.x", "EsValue")
        assert i18n.t("demo.x", "fr") == "EsValue"

    def test_bad_format_returns_template_unformatted(self, monkeypatch):
        monkeypatch.setitem(STRINGS["en"], "demo.bad", "{missing}")
        # No pasamos 'missing' → no lanza, devuelve la plantilla.
        assert i18n.t("demo.bad", "en", other=1) == "{missing}"


class TestResolveLang:
    """resolve_lang depende del modo del guild y del scope."""

    @pytest.mark.asyncio
    async def test_default_is_spanish(self, mock_bot):
        await mock_bot.init_mock_db()
        # Sin fila en guild_config → modo 'es'.
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "es"
        assert await i18n.resolve_lang(mock_bot, 1, "command") == "es"

    @pytest.mark.asyncio
    async def test_en_periodic_mode(self, mock_bot):
        await mock_bot.init_mock_db()
        await mock_bot.db.execute(
            "INSERT INTO guild_config (guild_id, language) VALUES (?, ?)", (1, "en_periodic")
        )
        await mock_bot.db.commit()
        # Dashboards en inglés, comandos en español.
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "en"
        assert await i18n.resolve_lang(mock_bot, 1, "command") == "es"

    @pytest.mark.asyncio
    async def test_en_total_mode(self, mock_bot):
        await mock_bot.init_mock_db()
        await mock_bot.db.execute(
            "INSERT INTO guild_config (guild_id, language) VALUES (?, ?)", (1, "en_total")
        )
        await mock_bot.db.commit()
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "en"
        assert await i18n.resolve_lang(mock_bot, 1, "command") == "en"

    @pytest.mark.asyncio
    async def test_explicit_es_mode(self, mock_bot):
        await mock_bot.init_mock_db()
        await mock_bot.db.execute(
            "INSERT INTO guild_config (guild_id, language) VALUES (?, ?)", (1, "es")
        )
        await mock_bot.db.commit()
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "es"
        assert await i18n.resolve_lang(mock_bot, 1, "command") == "es"

    @pytest.mark.asyncio
    async def test_none_guild_is_spanish(self, mock_bot):
        await mock_bot.init_mock_db()
        assert await i18n.resolve_lang(mock_bot, None, "periodic") == "es"

    @pytest.mark.asyncio
    async def test_cache_invalidation_reflects_change(self, mock_bot):
        await mock_bot.init_mock_db()
        await mock_bot.db.execute(
            "INSERT INTO guild_config (guild_id, language) VALUES (?, ?)", (1, "es")
        )
        await mock_bot.db.commit()
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "es"

        # Cambiar el modo sin invalidar → la caché sigue devolviendo el viejo valor.
        await mock_bot.db.execute("UPDATE guild_config SET language = ? WHERE guild_id = ?", ("en_total", 1))
        await mock_bot.db.commit()
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "es"  # cacheado

        # Tras invalidar, refleja el cambio.
        i18n.invalidate_lang_cache(1)
        assert await i18n.resolve_lang(mock_bot, 1, "periodic") == "en"
