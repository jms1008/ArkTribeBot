"""Tests unitarios del módulo utils.parsing — funciones puras."""

import pytest

from utils.parsing import (
    ALLOWED_BLACKLIST_FIELDS,
    ALLOWED_DINO_STATS,
    parse_battlemetrics,
)


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
