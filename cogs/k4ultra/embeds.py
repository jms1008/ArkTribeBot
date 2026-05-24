"""Construcción de embeds del dashboard K4Ultra.

Aislado del cog principal para reducir cog.py y permitir tests granulares.
La función es standalone (recibe ``bot``) en lugar de método.

Constantes:
- ``MAP_ACRONYMS``: tabla de abreviaturas de mapas para el modo radar.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

import aiosqlite
import discord

logger = logging.getLogger("ArkTribeBot")


# Tabla de acrónimos para mostrar nombres de mapas compactos en el ranking.
MAP_ACRONYMS: dict[str, str] = {
    "Aberration": "Aber",
    "Crystal Isles": "Crys",
    "Extinction": "Exti",
    "Fjordur": "Fjor",
    "Gen1": "Gen1",
    "Gen2": "Gen2",
    "Hub": "Hub ",
    "Lost Island": "Lost",
    "Ragnarok": "Ragn",
    "Scorched Earth": "Scor",
    "The Center": "Cent",
    "The Island": "Isla",
    "Valguero": "Valg",
}


async def generate_k4ultra_embed(
    bot, guild_id: int, mode: str = "radar"
) -> tuple[list[discord.Embed], list[str], dict[str, str]]:
    """Genera las páginas de embeds del dashboard K4Ultra.

    Modos:
    - ``radar``: jugadores conectados + ranking global (multi-página).
    - ``tribus``: tribus fijadas + nuestra tribu + grupos dinámicos predichos.

    Returns:
        Tupla ``(pages, top_player_names, aliases)``.
    """
    top_player_names: list[str] = []
    db = bot.db

    cursor = await db.execute(
        """
        SELECT player_name, map_name, total_minutes
        FROM k4ultra_playtime
        WHERE guild_id = ?
        """,
        (guild_id,),
    )
    all_playtimes = await cursor.fetchall()

    p_totals: dict[str, int] = defaultdict(int)
    p_maps: dict[str, list[dict]] = defaultdict(list)
    for row in all_playtimes:
        p_totals[row["player_name"]] += row["total_minutes"]
        p_maps[row["player_name"]].append(
            {"map": row["map_name"], "mins": row["total_minutes"]}
        )

    # Obtención de alias para mostrar nombres legibles.
    aliases: dict[str, str] = {}
    try:
        cursor = await db.execute(
            "SELECT player_name, alias FROM k4ultra_aliases WHERE guild_id = ?",
            (guild_id,),
        )
        aliases = {r["player_name"]: r["alias"] for r in await cursor.fetchall()}
    except aiosqlite.OperationalError as e:
        logger.debug(f"[K4Ultra] Tabla k4ultra_aliases no disponible: {e}")

    pages: list[discord.Embed] = []

    if mode == "radar":
        pages = await _build_radar_pages(
            db, guild_id, p_totals, p_maps, aliases, top_player_names
        )
    elif mode == "tribus":
        pages = await _build_tribes_page(db, guild_id, aliases)

    return pages, top_player_names, aliases


async def _build_radar_pages(
    db,
    guild_id: int,
    p_totals: dict[str, int],
    p_maps: dict[str, list[dict]],
    aliases: dict[str, str],
    top_player_names: list[str],
) -> list[discord.Embed]:
    """Construye las páginas del modo radar (en línea + ranking)."""
    cursor = await db.execute(
        "SELECT player_name, map_name, start_time FROM k4ultra_sessions WHERE is_active = 1 AND guild_id = ?",
        (guild_id,),
    )
    active_sessions = await cursor.fetchall()
    active_players = {s["player_name"] for s in active_sessions}

    page1 = discord.Embed(
        title="🌐 TRACKER K4ULTRA — Radar en Vivo",
        color=discord.Color.from_rgb(128, 0, 255),
    )
    if active_sessions:
        online_lines = []
        for s in active_sessions:
            p_name = s["player_name"]
            alias_tag = f" [{aliases[p_name]}]" if p_name in aliases else ""
            since = s["start_time"][11:16] if s["start_time"] else "?"
            online_lines.append(
                f"🟢 **{p_name}{alias_tag}** — {s['map_name']} (desde {since})"
            )
        online_text = "\n".join(online_lines)
        if len(online_text) > 900:
            online_text = online_text[:897] + "..."
        page1.add_field(
            name=f"📡 En Línea Ahora ({len(active_sessions)})",
            value=online_text,
            inline=False,
        )
    else:
        page1.add_field(
            name="📡 En Línea Ahora",
            value="Ningún jugador conectado.",
            inline=False,
        )

    sorted_players = sorted(p_totals.items(), key=lambda x: x[1], reverse=True)[:50]

    players_text = ""
    for p_name, total_m in sorted_players:
        top_player_names.append(p_name)
        h = total_m // 60
        m = total_m % 60
        time_str = f"{h}h {m}m" if h > 0 else f"{m}m"

        maps_for_p = p_maps[p_name]
        maps_for_p.sort(key=lambda x: x["mins"], reverse=True)
        map_str_list = []
        for mm in maps_for_p:
            pct = int((mm["mins"] / total_m) * 100) if total_m > 0 else 0
            if pct > 0:
                raw_map = mm["map"]
                acronym = MAP_ACRONYMS.get(
                    raw_map, raw_map.replace(" ", "")[:4].capitalize()
                )
                map_str_list.append(f"*{pct}% {acronym}*")

        map_joined = ", ".join(map_str_list)
        online_marker = "🟢 " if p_name in active_players else ""
        alias_tag = f" [{aliases[p_name]}]" if p_name in aliases else ""
        players_text += (
            f"- **{online_marker}{p_name}{alias_tag}** ⏱️ {time_str}: {map_joined}\n"
        )

    chunks: list[str] = []
    if players_text:
        while len(players_text) > 900:
            break_point = players_text.rfind("\n", 0, 900)
            if break_point == -1:
                break_point = 900
            else:
                break_point += 1
            chunks.append(players_text[:break_point])
            players_text = players_text[break_point:]
        if players_text:
            chunks.append(players_text)

    pages: list[discord.Embed] = []
    if not chunks:
        page1.add_field(
            name="🏆 Top Jugadores",
            value="No hay datos suficientes.",
            inline=False,
        )
        pages.append(page1)
    else:
        page1.add_field(name="🏆 Top Jugadores", value=chunks[0], inline=False)
        pages.append(page1)

        for chunk in chunks[1:]:
            p_next = discord.Embed(
                title="🌐 TRACKER K4ULTRA — Radar en Vivo",
                color=discord.Color.from_rgb(128, 0, 255),
            )
            p_next.add_field(
                name="🏆 Top Jugadores (Cont.)",
                value=chunk,
                inline=False,
            )
            pages.append(p_next)

    for i, p in enumerate(pages):
        p.set_footer(
            text=f"Radar | Página {i + 1}/{len(pages)} — Usa ◀️ ▶️ para navegar"
        )

    return pages


async def _build_tribes_page(db, guild_id: int, aliases: dict[str, str]) -> list[discord.Embed]:
    """Construye la única página del modo tribus (fijadas + dinámicas)."""
    page_t = discord.Embed(
        title="🌐 TRACKER K4ULTRA — Tribus y Grupos",
        color=discord.Color.from_rgb(90, 0, 180),
    )

    cursor = await db.execute(
        "SELECT name, members_json, is_own FROM k4ultra_fixed_tribes WHERE guild_id = ?",
        (guild_id,),
    )
    fixed_rows = await cursor.fetchall()

    fixed_players: set[str] = set()
    own_tribe_text = ""
    fixed_tribes_text = ""

    for fr in fixed_rows:
        tribe_name = fr["name"]
        is_own = fr["is_own"]
        members = json.loads(fr["members_json"])
        if not members:
            continue
        for m in members:
            fixed_players.add(m)

        tribe_str = ", ".join(
            f"{m} [{aliases[m]}]" if m in aliases else m for m in members
        )
        placeholders = ", ".join(["?"] * len(members))
        cursor = await db.execute(
            f"""
            SELECT map_name, SUM(total_minutes) as tribe_mins
            FROM k4ultra_playtime WHERE player_name IN ({placeholders})
            GROUP BY map_name ORDER BY tribe_mins DESC LIMIT 1
            """,
            list(members),
        )
        map_row = await cursor.fetchone()
        map_info = f" | 🗺️ {map_row['map_name']}" if map_row else ""

        if is_own:
            own_tribe_text += (
                f"**{tribe_name}** [🏰 Nuestra Tribu] ({len(members)}){map_info}\n"
                f"└ {tribe_str}\n"
            )
        else:
            fixed_tribes_text += (
                f"**{tribe_name}** [🛡️ Fijada] ({len(members)}){map_info}\n"
                f"└ {tribe_str}\n"
            )

    cursor = await db.execute(
        "SELECT player1, player2 FROM k4ultra_relationships "
        "WHERE ((probability_score >= 25 AND shared_minutes >= 60) OR is_manual = 1) "
        "AND guild_id = ?",
        (guild_id,),
    )
    rels = await cursor.fetchall()

    adjacency: dict[str, set[str]] = {}
    for r in rels:
        p1, p2 = r["player1"], r["player2"]
        if p1 in fixed_players or p2 in fixed_players:
            continue
        adjacency.setdefault(p1, set()).add(p2)
        adjacency.setdefault(p2, set()).add(p1)

    # BFS para clusters conectados
    visited: set[str] = set()
    dynamic_tribes: list[list[str]] = []
    for node in adjacency:
        if node in visited:
            continue
        cluster: set[str] = set()
        queue = [node]
        visited.add(node)
        while queue:
            curr = queue.pop(0)
            cluster.add(curr)
            for neighbor in adjacency[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if len(cluster) > 1:
            dynamic_tribes.append(list(cluster))
    dynamic_tribes.sort(key=len, reverse=True)

    dyn_text = ""
    for i, tribe in enumerate(dynamic_tribes[:8]):
        tribe_label = f"Grupo {i + 1}"
        tribe_str = ", ".join(
            f"{m} [{aliases[m]}]" if m in aliases else m for m in tribe
        )
        if len(tribe_str) > 150:
            tribe_str = tribe_str[:147] + "..."
        placeholders = ", ".join(["?"] * len(tribe))
        cursor = await db.execute(
            f"""
            SELECT map_name, SUM(total_minutes) as tribe_mins
            FROM k4ultra_playtime WHERE player_name IN ({placeholders}) AND guild_id = ?
            GROUP BY map_name ORDER BY tribe_mins DESC LIMIT 1
            """,
            list(tribe) + [guild_id],
        )
        map_row = await cursor.fetchone()
        map_info = f" | 🗺️ {map_row['map_name']}" if map_row else ""
        dyn_text += f"**{tribe_label}** ({len(tribe)}){map_info}\n└ {tribe_str}\n"

    if len(dynamic_tribes) > 8:
        dyn_text += f"*... y {len(dynamic_tribes) - 8} grupos más*\n"

    if own_tribe_text:
        page_t.add_field(name="🏰 Nuestra Tribu", value=own_tribe_text, inline=False)
    if fixed_tribes_text:
        page_t.add_field(
            name="🛡️ Otras Tribus Fijadas",
            value=fixed_tribes_text,
            inline=False,
        )
    if dyn_text:
        page_t.add_field(
            name="🔗 Grupos / Predicciones",
            value=dyn_text,
            inline=False,
        )

    if not own_tribe_text and not fixed_tribes_text and not dyn_text:
        page_t.add_field(
            name="Tribus",
            value="No hay tribus registradas ni grupos predecidos aún.",
            inline=False,
        )

    page_t.set_footer(text="Explorador de Tribus — Página Única")
    return [page_t]
