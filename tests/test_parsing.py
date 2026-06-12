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
    # Cluster realista (los nombres configurados en battlemetrics_urls).
    CLUSTER = [
        "Aberration",
        "Crystal Isles",
        "Extinction",
        "Fjordur",
        "Gen1",
        "Gen2",
        "Hub",
        "Lost Island",
        "Ragnarok",
        "Scorched Earth",
        "The Center",
        "The Island",
        "Valguero",
    ]

    @pytest.mark.parametrize(
        ("tag", "expected"),
        [
            # Tabla REAL de tags del cluster (confirmada por el usuario).
            ("Gn2", "Gen2"),
            ("Hub", "Hub"),
            ("Ext", "Extinction"),
            ("Gen", "Gen1"),
            ("Cen", "The Center"),
            ("Abr", "Aberration"),
            ("Fjo", "Fjordur"),
            ("Isl", "The Island"),
            ("Rag", "Ragnarok"),
            # Tags probables de los 3 mapas pendientes de confirmar.
            ("Sco", "Scorched Earth"),
            ("SE", "Scorched Earth"),
            ("Cry", "Crystal Isles"),
            ("CI", "Crystal Isles"),
            ("Los", "Lost Island"),
            ("LI", "Lost Island"),
            ("Val", "Valguero"),
        ],
    )
    def test_known_cluster_tags(self, tag, expected):
        assert resolve_map_from_tag(tag, self.CLUSTER) == expected

    def test_gen_does_not_match_gen2(self):
        """'Gen' es Genesis 1: la tabla evita que la heurística lo confunda con Gen2."""
        assert resolve_map_from_tag("Gen", self.CLUSTER) == "Gen1"

    def test_known_tag_without_configured_server_returns_canonical(self):
        """Tag conocido pero mapa no configurado → nombre canónico legible."""
        assert resolve_map_from_tag("Fjo", ["Ragnarok"]) == "Fjordur"

    def test_configured_name_extending_candidate_matches(self):
        """'Aberration PVP' configurado cuenta como 'Aberration'."""
        assert resolve_map_from_tag("Abr", ["Aberration PVP"]) == "Aberration PVP"

    def test_unknown_tag_uses_heuristic(self):
        """Tags fuera de la tabla caen a la heurística por prefijo/subsecuencia."""
        assert resolve_map_from_tag("Crys", self.CLUSTER) == "Crystal Isles"
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
