"""Tests unitarios del módulo utils.parsing — funciones puras."""

import pytest

from utils.parsing import (
    ALLOWED_BLACKLIST_FIELDS,
    ALLOWED_DINO_STATS,
    parse_battlemetrics,
    parse_destruction_line,
)


class TestParseDestructionLine:
    def test_real_example_with_map_tag(self):
        """El ejemplo real del usuario: tag de mapa + sufijos de tipo/estado."""
        line = "(Abr) Day 1, 09:47: Your 'GLOWTAIL WALL (SS Storage Box) (Unlocked) ' was destroyed!"
        assert parse_destruction_line(line) == ("Abr", "GLOWTAIL WALL")

    def test_without_map_tag(self):
        line = "Day 312, 22:03: Your 'Puerta Norte (Stone Dinosaur Gateway)' was destroyed!"
        assert parse_destruction_line(line) == (None, "Puerta Norte")

    def test_name_without_parenthesized_suffix(self):
        line = "(Rag) Day 5, 11:11: Your 'Torre Vigia' was destroyed!"
        assert parse_destruction_line(line) == ("Rag", "Torre Vigia")

    def test_spanish_variant(self):
        line = "(Isla) Day 2, 03:30: Your 'Muro Este (Metal Wall)' fue destruido!"
        assert parse_destruction_line(line) == ("Isla", "Muro Este")

    def test_non_destruction_lines_return_none(self):
        assert parse_destruction_line("(Abr) Day 1, 09:47: Tribemember Bob - Lvl 100 was killed!") is None
        assert parse_destruction_line("hola mundo") is None
        assert parse_destruction_line("") is None
        assert parse_destruction_line(None) is None

    def test_case_insensitive(self):
        line = "(abr) day 9, 01:00: your 'wall sur (Wooden Wall)' WAS DESTROYED!"
        assert parse_destruction_line(line) == ("abr", "wall sur")


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
