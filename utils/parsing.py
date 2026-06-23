"""Utilidades de parsing puras (sin estado, sin I/O).

Aisladas en módulo propio para facilitar tests unitarios.
"""

from __future__ import annotations

import re

# Línea de tribu de "estructura destruida". Ejemplo real:
#   (Abr) Day 1, 09:47: Your 'GLOWTAIL WALL (SS Storage Box) (Unlocked) ' was destroyed!
# El prefijo "(Abr)" es el tag del servidor/mapa que añade el webhook (opcional).
_DESTRUCTION_RE = re.compile(
    r"(?:\((?P<map>[^)]{1,20})\)\s*)?"  # tag de mapa opcional al inicio
    r"Day\s+\d+,\s*[\d:]+:\s*"  # "Day 1, 09:47:"
    r"Your\s+'(?P<name>.+?)'\s+"  # nombre entre comillas simples
    r"(?:was destroyed|fue destruid[oa])!",  # EN / ES
    re.IGNORECASE,
)


def parse_destruction_line(text: str | None) -> tuple[str | None, str, str | None] | None:
    """Detecta una línea de "estructura destruida" en el log de tribu.

    Devuelve ``(map_abbrev | None, nombre_limpio, tipo | None)`` o ``None`` si
    no es una línea de destrucción. El nombre se limpia de los sufijos entre
    paréntesis que añade el juego; el primer paréntesis es el TIPO de
    estructura: ``"GLOWTAIL WALL (SS Storage Box) (Unlocked) "`` →
    ``("...", "GLOWTAIL WALL", "SS Storage Box")``.
    """
    if not text:
        return None
    m = _DESTRUCTION_RE.search(text)
    if not m:
        return None
    raw_name = m.group("name")
    clean_name = raw_name.split(" (", 1)[0].strip()
    if not clean_name:
        clean_name = raw_name.strip()
    type_match = re.search(r"\(([^)]+)\)", raw_name)
    structure_type = type_match.group(1).strip() if type_match else None
    map_abbrev = m.group("map")
    return (map_abbrev.strip() if map_abbrev else None, clean_name, structure_type)


# Artículos a ignorar al casar tags de mapa contra nombres de servidor.
_MAP_ARTICLES = frozenset({"the", "la", "el", "los", "las"})

# Tags de mapa CONOCIDOS del log del cluster → candidatos de nombre canónico.
# Se consulta ANTES que la heurística: los tags del juego son arbitrarios
# ("Gn2" para Genesis 2, "Gen" para Genesis 1) y la heurística no puede
# desambiguarlos. Cada tag lista varias formas posibles del nombre configurado.
KNOWN_MAP_TAGS: dict[str, tuple[str, ...]] = {
    "abr": ("Aberration",),
    "cen": ("The Center", "Center"),
    "ci": ("Crystal Isles",),
    "cry": ("Crystal Isles",),
    "ext": ("Extinction",),
    "fjo": ("Fjordur",),
    "gen": ("Gen1", "Genesis 1", "Genesis"),
    "gn2": ("Gen2", "Genesis 2"),
    "hub": ("Hub",),
    "isl": ("The Island", "Island"),
    "li": ("Lost Island",),
    "los": ("Lost Island",),
    "rag": ("Ragnarok",),
    "sco": ("Scorched Earth",),
    "se": ("Scorched Earth",),
    "val": ("Valguero",),
}


def _is_subsequence(needle: str, haystack: str) -> bool:
    """True si los caracteres de ``needle`` aparecen en ``haystack`` en orden
    (no necesariamente contiguos). Ej.: "abr" ⊂ "aberration" (A-B-e-R)."""
    it = iter(haystack)
    return all(ch in it for ch in needle)


def resolve_map_from_tag(tag: str | None, server_names: list[str]) -> str:
    """Resuelve el tag de mapa de un log ("Isl", "Abr", "Gn2") al nombre del
    servidor configurado.

    Primero consulta la tabla de tags conocidos del cluster (KNOWN_MAP_TAGS):
    "Gn2" → Gen2, "Gen" → Gen1, "Isl" → The Island, etc. Si el tag es conocido
    pero ese mapa no figura en la config, devuelve el nombre canónico igualmente.

    Para tags desconocidos cae a una heurística con prioridad:
    1. Prefijo del nombre completo.
    2. Prefijo de la primera palabra significativa, saltando artículos.
    3. Prefijo de cualquier palabra.
    4. Subsecuencia de la primera palabra significativa.
    5. Subsecuencia de cualquier palabra.

    Si nada casa, devuelve el tag tal cual.
    """
    if not tag:
        return "?"
    ab = tag.strip().lower()
    if not ab:
        return "?"

    # Pase 0: tabla de tags conocidos.
    if ab in KNOWN_MAP_TAGS:

        def _norm(s: str) -> str:
            return s.lower().replace(" ", "")

        for cand in KNOWN_MAP_TAGS[ab]:
            for name in server_names:
                # Igualdad normalizada o el nombre configurado extiende al
                # candidato ("Aberration PVP" cuenta como "Aberration").
                if _norm(name) == _norm(cand) or _norm(name).startswith(_norm(cand)):
                    return name
        # Tag conocido sin servidor configurado: nombre canónico legible.
        return KNOWN_MAP_TAGS[ab][0]

    # Pase 1: prefijo del nombre completo.
    for name in server_names:
        if name.lower().startswith(ab):
            return name

    # Pase 2: prefijo de la primera palabra significativa (sin artículos).
    def _significant_words(name: str) -> list[str]:
        return [w for w in name.lower().split() if w not in _MAP_ARTICLES]

    for name in server_names:
        words = _significant_words(name)
        if words and words[0].startswith(ab):
            return name

    # Pase 3: prefijo de cualquier palabra.
    for name in server_names:
        if any(word.startswith(ab) for word in name.lower().split()):
            return name

    # Pase 4: subsecuencia de la primera palabra significativa.
    for name in server_names:
        words = _significant_words(name)
        if words and _is_subsequence(ab, words[0]):
            return name

    # Pase 5: subsecuencia de cualquier palabra.
    for name in server_names:
        if any(_is_subsequence(ab, word) for word in name.lower().split()):
            return name

    return tag.strip()


def parse_battlemetrics(bm_string: str | None) -> dict[str, tuple[str, int]]:
    """Parsea el campo `battlemetrics_urls` de `guild_config`.

    Formato esperado: ``MapName|IP:PORT,Map2|IP:PORT2``.
    Devuelve un dict ``{nombre_mapa: (ip, puerto)}`` ignorando entradas malformadas.
    """
    servers: dict[str, tuple[str, int]] = {}
    if not bm_string:
        return servers
    for entry in bm_string.split(","):
        entry = entry.strip()
        if "|" in entry:
            parts = entry.split("|", 1)
        elif ";" in entry:
            parts = entry.split(";", 1)
        else:
            continue
        if len(parts) != 2:
            continue
        map_name = parts[0].strip()
        address_str = parts[1].strip()
        if ":" not in address_str or not map_name:
            continue
        addr_parts = address_str.rsplit(":", 1)
        try:
            ip = addr_parts[0].strip()
            port = int(addr_parts[1].strip())
            if not ip:
                continue
            servers[map_name] = (ip, port)
        except (ValueError, IndexError):
            continue
    return servers


# Campos permitidos en UPDATE dinámico de blacklist (whitelist anti-inyección).
ALLOWED_BLACKLIST_FIELDS: frozenset[str] = frozenset(
    {"player", "tribe", "map", "notes", "is_enemy", "last_seen", "total_hours"}
)

# Stats permitidas en UPDATE/INSERT dinámico de dinos.
ALLOWED_DINO_STATS: frozenset[str] = frozenset(
    {"hp", "melee", "stam", "weight", "oxy", "food", "speed", "mutaciones"}
)
