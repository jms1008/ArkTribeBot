"""Tests de los regex y heurísticas de cogs/log_processor.py.

Los regex en log_processor.py son los que detectan muertes en los logs del
servidor de juego. Si rompen, dejamos de contar muertes / actualizar KDA.
"""
import re

import pytest


# Patrones reproducidos del cog para test aislado (cualquier cambio aquí debe
# acompañarse del mismo cambio en cogs/log_processor.py — son la "fuente de verdad"
# y deben mantenerse en sync).
PLAYER_DEATH_RE = re.compile(
    r"Tribemember (.*?) - Lvl.*?fue 🔪 por (.*?) - Lvl",
    re.IGNORECASE,
)
GENERIC_DEATH_RE = re.compile(
    r"Tribemember (.*?) - Lvl.*?(?:ha muerto 🔪|was 🔪)",
    re.IGNORECASE,
)


def normalize(raw: str) -> str:
    """Replica la normalización que hace LogProcessor antes de aplicar regex."""
    return (
        raw.replace(":knife:", "🔪")
        .replace("was 🔪 by", "fue 🔪 por")
        .replace("was 🔪", "ha muerto 🔪")
    )


class TestPlayerDeathRegex:
    """Detección de muertes con asesino identificado."""

    def test_basic_pvp_kill(self):
        text = normalize("Day 5, 10:30:00: Your Tribemember Alice - Lvl 100 was :knife: by Bob - Lvl 95")
        m = PLAYER_DEATH_RE.search(text)
        assert m is not None
        assert m.group(1).strip() == "Alice"
        assert m.group(2).strip() == "Bob"

    def test_spanish_localization(self):
        text = "Día 5, 10:30:00: Your Tribemember Alice - Lvl 100 fue 🔪 por Bob - Lvl 95"
        m = PLAYER_DEATH_RE.search(text)
        assert m is not None
        assert m.group(1).strip() == "Alice"
        assert m.group(2).strip() == "Bob"

    def test_case_insensitive(self):
        text = "TRIBEMEMBER alice - LVL 100 FUE 🔪 POR bob - LVL 95"
        m = PLAYER_DEATH_RE.search(text)
        assert m is not None

    def test_names_with_spaces(self):
        text = "Tribemember Alice Smith - Lvl 100 fue 🔪 por Bob The Big - Lvl 95"
        m = PLAYER_DEATH_RE.search(text)
        assert m is not None
        assert m.group(1).strip() == "Alice Smith"
        assert m.group(2).strip() == "Bob The Big"

    def test_does_not_match_generic_death(self):
        """Sin '🔪 por X' no debe matchear este regex (es para generic)."""
        text = normalize("Tribemember Alice - Lvl 100 was :knife:")
        assert PLAYER_DEATH_RE.search(text) is None


class TestGenericDeathRegex:
    """Detección de muertes sin asesino (dino, hambre, fall damage, etc)."""

    def test_generic_death_without_killer(self):
        text = normalize("Tribemember Alice - Lvl 100 was :knife:")
        m = GENERIC_DEATH_RE.search(text)
        assert m is not None
        assert m.group(1).strip() == "Alice"

    def test_spanish_generic_death(self):
        text = "Tribemember Alice - Lvl 100 ha muerto 🔪"
        m = GENERIC_DEATH_RE.search(text)
        assert m is not None
        assert m.group(1).strip() == "Alice"

    def test_also_matches_pvp_killed_format(self):
        """generic_death_match es más permisivo: detecta también el caso PvP.
        El cog distingue priorizando PLAYER_DEATH_RE primero."""
        text = "Tribemember Alice - Lvl 100 was 🔪 by Bob - Lvl 95"
        # generic_death se queda con 'was 🔪' aunque haya 'by ...'
        m = GENERIC_DEATH_RE.search(text)
        assert m is not None


class TestNormalization:
    """La capa de normalización debe consolidar variantes ES/EN de los logs."""

    def test_knife_emoji_token(self):
        assert normalize("foo :knife: bar") == "foo 🔪 bar"

    def test_english_killed_by_becomes_spanish(self):
        assert "fue 🔪 por" in normalize("Player was :knife: by Killer")

    def test_english_generic_death_becomes_spanish(self):
        assert "ha muerto 🔪" in normalize("Player was :knife:")


class TestPoliciaDetection:
    """La detección de @policia se hace sobre el contenido en minúsculas."""

    @pytest.mark.parametrize("text,expected", [
        ("Atacaron a @policia en el server", True),
        ("@POLICIA mira el log", True),
        ("Mensaje sin tag", False),
        ("<@&1234567890> mira esto", True),  # mención por ID de rol
    ])
    def test_contains_policia_mention(self, text, expected):
        content_lower = text.lower()
        contains_policia = "@policia" in content_lower or "<@&" in content_lower
        assert contains_policia is expected

    @pytest.mark.parametrize("text,expected", [
        ("Algo was :knife: por otro", True),
        ("Algo fue :knife: por otro", True),
        ("Algo was 🔪 por otro", True),
        ("Algo fue 🔪 por otro", True),
        ("Sin emoji aquí", False),
    ])
    def test_contains_knife_marker(self, text, expected):
        content_lower = text.lower()
        contains_knife = (
            "was :knife:" in content_lower
            or "fue :knife:" in content_lower
            or "was 🔪" in content_lower
            or "fue 🔪" in content_lower
        )
        assert contains_knife is expected


class TestMapExtraction:
    """El nombre del mapa se extrae con re.search(r'\\((.*?)\\)', ...)"""

    def test_extracts_map_from_parentheses(self):
        text = "Tribemember Alice (Ragnarok) was killed"
        m = re.search(r"\((.*?)\)", text)
        assert m and m.group(1) == "Ragnarok"

    def test_no_parens_returns_none(self):
        m = re.search(r"\((.*?)\)", "Tribemember Alice was killed")
        assert m is None
