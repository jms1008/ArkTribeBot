"""Smoke tests: los builders de dashboards renderizan en ES y EN sin romper."""

import pytest

from cogs.management import build_todo_embed_view
from cogs.warfare import build_blacklist_embed


class TestTodoBuilderBilingual:
    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_empty_renders(self, lang):
        embed, page, view = build_todo_embed_view(None, [], 0, lang=lang)
        assert embed.title
        assert embed.footer.text
        assert page == 0

    def test_titles_differ_between_languages(self):
        es, _, _ = build_todo_embed_view(None, [], 0, lang="es")
        en, _, _ = build_todo_embed_view(None, [], 0, lang="en")
        assert es.title != en.title
        assert "TAREAS" in es.title
        assert "TASK" in en.title

    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_with_rows_renders(self, lang):
        rows = [
            {"id": 1, "tarea": "Foo", "asignado_a": "123", "estado": "Pendiente"},
            {"id": 2, "tarea": "Bar", "asignado_a": None, "estado": "En Progreso"},
        ]
        embed, _, _ = build_todo_embed_view(None, rows, 0, lang=lang)
        assert "Foo" in embed.description
        # La página se refleja en el footer en formato N/N (language-agnostic).
        assert "1/1" in embed.footer.text


class TestBlacklistBuilderBilingual:
    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_empty_renders(self, lang):
        embed, page, total_pages = build_blacklist_embed([], 0, lang=lang)
        assert embed.title
        assert embed.description
        assert total_pages == 1

    def test_titles_differ_between_languages(self):
        es, _, _ = build_blacklist_embed([], 0, lang="es")
        en, _, _ = build_blacklist_embed([], 0, lang="en")
        assert "BLACKLIST" in es.title and "TRIBU" in es.title
        assert "BLACKLIST" in en.title and "TRIBE" in en.title

    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_with_rows_sections_and_footer(self, lang):
        rows = [
            {"id": 1, "player": "Enemy1", "tribe": "Bad", "map": "Fjordur", "notes": "", "is_enemy": 1},
            {"id": 2, "player": "Neutral1", "tribe": "Mid", "map": "Ragnarok", "notes": "", "is_enemy": 0},
        ]
        embed, page, total_pages = build_blacklist_embed(rows, 0, lang=lang)
        assert "Enemy1" in embed.description
        assert "Neutral1" in embed.description
        assert "1/1" in embed.footer.text
