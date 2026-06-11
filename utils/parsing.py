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


def parse_destruction_line(text: str | None) -> tuple[str | None, str] | None:
    """Detecta una línea de "estructura destruida" en el log de tribu.

    Devuelve ``(map_abbrev | None, nombre_limpio)`` o ``None`` si no es una
    línea de destrucción. El nombre se limpia de los sufijos entre paréntesis
    que añade el juego (tipo de estructura, "(Unlocked)", etc.):
    ``"GLOWTAIL WALL (SS Storage Box) (Unlocked) "`` → ``"GLOWTAIL WALL"``.
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
    map_abbrev = m.group("map")
    return (map_abbrev.strip() if map_abbrev else None, clean_name)


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
        if "|" not in entry:
            continue
        parts = entry.split("|", 1)
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
