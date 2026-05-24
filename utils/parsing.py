"""Utilidades de parsing puras (sin estado, sin I/O).

Aisladas en módulo propio para facilitar tests unitarios.
"""

from __future__ import annotations


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
