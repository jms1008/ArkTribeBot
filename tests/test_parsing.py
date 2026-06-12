"""Tests unitarios del módulo utils.parsing — funciones puras."""

import pytest

from utils.parsing import (
    ALLOWED_BLACKLIST_FIELDS,
    ALLOWED_DINO_STATS,
    parse_battlemetrics,
    parse_destruction_line,
    resolve_map_from_tag,
)


class TestParseDestructionLine:
    def test_real_example_with_map_tag(self):
        """El ejemplo real del usuario: tag de mapa + tipo + estado."""
        line = "(Abr) Day 1, 09:47: Your 'GLOWTAIL WALL (SS Storage Box) (Unlocked) ' was destroyed!"
        assert parse_destruction_line(line) == ("Abr", "GLOWTAIL WALL", "SS Storage Box")

    def test_without_map_tag(self):
        line = "Day 312, 22:03: Your 'Puerta Norte (Stone Dinosaur Gateway)' was destroyed!"
        assert parse_destruction_line(line) == (None, "Puerta Norte", "Stone Dinosaur Gateway")

    def test_name_without_parenthesized_suffix(self):
        """Sin sufijo de tipo → tipo None (el caller la descartará por filtro)."""
        line = "(Rag) Day 5, 11:11: Your 'Torre Vigia' was destroyed!"
        assert parse_destruction_line(line) == ("Rag", "Torre Vigia", None)

    def test_spanish_variant(self):
        line = "(Isla) Day 2, 03:30: Your 'Muro Este (Metal Wall)' fue destruido!"
        assert parse_destruction_line(line) == ("Isla", "Muro Este", "Metal Wall")

    def test_non_destruction_lines_return_none(self):
        assert parse_destruction_line("(Abr) Day 1, 09:47: Tribemember Bob - Lvl 100 was killed!") is None
        assert parse_destruction_line("hola mundo") is None
        assert parse_destruction_line("") is None
        assert parse_destruction_line(None) is None

    def test_case_insensitive(self):
        line = "(abr) day 9, 01:00: your 'wall sur (Wooden Wall)' WAS DESTROYED!"
        assert parse_destruction_line(line) == ("abr", "wall sur", "Wooden Wall")


class TestResolveMapFromTag:
    CLUSTER = ["Aberration", "Crystal Isles", "The Island", "The Center", "Ragnarok", "Lost Island"]

    def test_full_name_prefix(self):
        assert resolve_map_from_tag("Abr", self.CLUSTER) == "Aberration"
        assert resolve_map_from_tag("Rag", self.CLUSTER) == "Ragnarok"

    def test_isl_resolves_to_the_island_not_crystal_isles(self):
        """Regresión: '(Isl)' casaba con Crystal ISLes por prefijo de palabra.
        La primera palabra significativa de The Island es 'island' → gana."""
        assert resolve_map_from_tag("Isl", self.CLUSTER) == "The Island"

    def test_article_skipping_for_the_center(self):
        assert resolve_map_from_tag("Cen", self.CLUSTER) == "The Center"

    def test_crystal_isles_via_first_word(self):
        assert resolve_map_from_tag("Crys", self.CLUSTER) == "Crystal Isles"

    def test_second_word_only_match_falls_to_pass3(self):
        """'Isles' no es primera palabra significativa de nada que empiece así
        salvo... The Island ('island' NO empieza por 'isles'), Crystal Isles sí
        la contiene como segunda palabra → pase 3."""
        assert resolve_map_from_tag("Isles", self.CLUSTER) == "Crystal Isles"

    def test_unknown_tag_returned_verbatim(self):
        assert resolve_map_from_tag("Xyz", self.CLUSTER) == "Xyz"

    def test_empty_or_none(self):
        assert resolve_map_from_tag(None, self.CLUSTER) == "?"
        assert resolve_map_from_tag("  ", self.CLUSTER) == "?"


class TestParseBattlemetrics:
    def test_empty_returns_empty_dict(self):
        assert parse_battlemetrics("") == {}
        assert parse_battlemetrics(None) == {}

    def test_single_entry(self):
        assert parse_battlemetrics("Ragnarok|192.168.1.1:27015") == {"Ragnarok": ("192.168.1.1", 27015)}

    def test_multiple_entries(self):
        result = parse_battlemetrics("Ragnarok|192.168.1.1:27015,TheIsland|10.0.0.5:27020")
        assert result == {
            "Ragnarok": ("192.168.1.1", 27015),
            "TheIsland": ("10.0.0.5", 27020),
        }

    def test_handles_whitespace(self):
        assert parse_battlemetrics("  Rag  |  1.2.3.4 : 1000  ") == {"Rag": ("1.2.3.4", 1000)}

    def test_skips_malformed_entries(self):
        # Falta '|', falta ':', puerto no numérico, mapa vacío
        result = parse_battlemetrics(
            "BadOne,Good|1.1.1.1:1234,NoPort|1.1.1.1,NoNumber|1.1.1.1:abc,|1.1.1.1:1234"
        )
        assert result == {"Good": ("1.1.1.1", 1234)}

    def test_ipv6_like_uses_rsplit(self):
        # rsplit con maxsplit=1 → puerto al final
        assert parse_battlemetrics("V6|::1:27015") == {"V6": ("::1", 27015)}


class TestWhitelists:
    def test_blacklist_fields_contains_expected_columns(self):
        expected = {"player", "tribe", "map", "notes", "is_enemy", "last_seen", "total_hours"}
        assert expected == ALLOWED_BLACKLIST_FIELDS

    def test_dino_stats_contains_expected_columns(self):
        expected = {"hp", "melee", "stam", "weight", "oxy", "food", "speed", "mutaciones"}
        assert expected == ALLOWED_DINO_STATS

    @pytest.mark.parametrize(
        "malicious",
        [
            "1=1; DROP TABLE blacklist",
            "id, player",
            "player; --",
        ],
    )
    def test_blacklist_rejects_injection_attempts(self, malicious):
        assert malicious not in ALLOWED_BLACKLIST_FIELDS

    @pytest.mark.parametrize(
        "malicious",
        [
            "hp; DROP TABLE dinos",
            "stam, hp",
            "*",
        ],
    )
    def test_dino_stats_rejects_injection_attempts(self, malicious):
        assert malicious not in ALLOWED_DINO_STATS
