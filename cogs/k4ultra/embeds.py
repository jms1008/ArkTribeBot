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
        p_maps[row["player_name"]].append({"map": row["map_name"], "mins": row["total_minutes"]})

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
        pages = await _build_radar_pages(db, guild_id, p_totals, p_maps, aliases, top_player_names)
    elif mode == "tribus":
        pages = await _build_tribes_page(db, guild_id, aliases)

    return pages, top_player_names, aliases


def _format_playtime(total_m: int) -> str:
    """Devuelve ``999h 59m`` o ``59m`` con padding fijo a 8 chars para alineación."""
    h = total_m // 60
    m = total_m % 60
    return f"{h}h {m:>2}m" if h > 0 else f"{m:>5}m"


async def _build_radar_pages(
    db,
    guild_id: int,
    p_totals: dict[str, int],
    p_maps: dict[str, list[dict]],
    aliases: dict[str, str],
    top_player_names: list[str],
) -> list[discord.Embed]:
    """Construye las páginas del modo radar (en línea + ranking).

    Patrón visual unificado (Blacklist/Scouting):
    - Header con badges (📡 online · 🏆 total · 📄 paginación)
    - Secciones marcadas con ## EMOJI TÍTULO
    - Items con jerarquía: ``#NN nombre  ·  horas  ·  └ mapas%``
    """
    cursor = await db.execute(
        "SELECT player_name, map_name, start_time FROM k4ultra_sessions WHERE is_active = 1 AND guild_id = ?",
        (guild_id,),
    )
    active_sessions = await cursor.fetchall()
    active_players = {s["player_name"] for s in active_sessions}

    sorted_players = sorted(p_totals.items(), key=lambda x: x[1], reverse=True)[:50]
    n_total = len(sorted_players)
    n_online = len(active_sessions)

    # Cabecera común a todas las páginas.
    def _header(page_idx: int, total_pages: int) -> list[str]:
        return [
            f"📡 `{n_online:02d}` Online  ·  🏆 `{n_total:02d}` En ranking  ·  📄 Página `{page_idx + 1}/{total_pages}`",
            "",
        ]

    # Sección "EN LÍNEA AHORA" (solo en la primera página).
    online_block: list[str] = ["## 📡 EN LÍNEA AHORA"]
    if active_sessions:
        for s in active_sessions:
            p_name = s["player_name"]
            alias_tag = f" [{aliases[p_name]}]" if p_name in aliases else ""
            since = s["start_time"][11:16] if s["start_time"] else "?"
            online_block.append(f"🟢 **{p_name}**{alias_tag}  ·  🗺️ {s['map_name']}  ·  ⏱️ desde {since}")
    else:
        online_block.append("*Ningún jugador conectado ahora mismo.*")
    online_block.append("")

    # Sección "TOP JUGADORES".
    top_lines: list[str] = []
    for idx, (p_name, total_m) in enumerate(sorted_players, start=1):
        top_player_names.append(p_name)
        time_str = _format_playtime(total_m)

        maps_for_p = sorted(p_maps[p_name], key=lambda x: x["mins"], reverse=True)
        map_str_list = []
        for mm in maps_for_p:
            pct = int((mm["mins"] / total_m) * 100) if total_m > 0 else 0
            if pct > 0:
                raw_map = mm["map"]
                acronym = MAP_ACRONYMS.get(raw_map, raw_map.replace(" ", "")[:4].capitalize())
                map_str_list.append(f"{pct}% {acronym}")

        map_joined = " · ".join(map_str_list)
        online_marker = "🟢 " if p_name in active_players else "⚫ "
        alias_tag = f" [{aliases[p_name]}]" if p_name in aliases else ""
        top_lines.append(f"`#{idx:02d}` {online_marker}**{p_name}**{alias_tag}  ·  ⏱️ `{time_str}`")
        top_lines.append(f"  └ 🗺️ *{map_joined}*" if map_joined else "  └ *(sin actividad reciente)*")

    # Paginar el top por NÚMERO de jugadores (no por chars). La primera página
    # comparte espacio con "EN LÍNEA AHORA" así que va más corta; las siguientes
    # son más largas porque solo llevan ranking.
    # Cada jugador ocupa 2 líneas (encabezado + mapas), así que 12 jugadores ≈
    # 24 líneas, lo que cabe sin scroll en un monitor estándar.
    TOP_PER_PAGE_FIRST = 12
    TOP_PER_PAGE_REST = 18
    LINES_PER_PLAYER = 2

    chunks: list[list[str]] = []
    if top_lines:
        first_chunk_size = TOP_PER_PAGE_FIRST * LINES_PER_PLAYER
        first = top_lines[:first_chunk_size]
        chunks.append(first)

        remaining = top_lines[first_chunk_size:]
        rest_chunk_size = TOP_PER_PAGE_REST * LINES_PER_PLAYER
        while remaining:
            chunks.append(remaining[:rest_chunk_size])
            remaining = remaining[rest_chunk_size:]

    pages: list[discord.Embed] = []

    if not chunks:
        # No hay jugadores en ranking — una sola página con solo online + mensaje.
        page = discord.Embed(
            title="🌐 TRACKER K4ULTRA — Radar en Vivo",
            color=discord.Color.from_rgb(128, 0, 255),
        )
        body = _header(0, 1) + online_block + ["## 🏆 TOP JUGADORES", "*No hay datos suficientes.*"]
        page.description = "\n".join(body).strip()
        page.set_footer(text="Radar  •  Página 1/1  •  Usa el selector para ver detalle de un jugador")
        pages.append(page)
        return pages

    total_pages = len(chunks)
    for i, chunk in enumerate(chunks):
        page = discord.Embed(
            title="🌐 TRACKER K4ULTRA — Radar en Vivo",
            color=discord.Color.from_rgb(128, 0, 255),
        )
        body = _header(i, total_pages)
        # El bloque de "online" solo aparece en la primera página.
        if i == 0:
            body += online_block
        section_title = "## 🏆 TOP JUGADORES" if i == 0 else "## 🏆 TOP JUGADORES (Cont.)"
        body.append(section_title)
        body.extend(chunk)
        page.description = "\n".join(body).strip()
        page.set_footer(
            text=f"Radar  •  Página {i + 1}/{total_pages}  •  Usa ◀️ ▶️ para navegar o el selector para ver detalle"
        )
        pages.append(page)

    return pages


async def _build_tribes_page(db, guild_id: int, aliases: dict[str, str]) -> list[discord.Embed]:
    """Construye la única página del modo tribus (fijadas + dinámicas)."""
    page_t = discord.Embed(
        title="🌐 TRACKER K4ULTRA — Tribus y Grupos",
        color=discord.Color.from_rgb(90, 0, 180),
    )

    # Carga miembros activos para mostrar quién está online de cada tribu.
    cursor = await db.execute(
        "SELECT player_name FROM k4ultra_sessions WHERE is_active = 1 AND guild_id = ?",
        (guild_id,),
    )
    online_set = {r["player_name"] for r in await cursor.fetchall()}

    def _format_member(name: str) -> str:
        """Renderiza un miembro con icono online + alias si lo tiene."""
        # Filtrar nombres vacíos o placeholders inconsistentes (ej. "(—)").
        clean = name.strip().strip("()").strip("—").strip()
        if not clean:
            return ""
        marker = "🟢" if name in online_set else "⚫"
        alias_tag = f" [{aliases[name]}]" if name in aliases else ""
        return f"{marker} {clean}{alias_tag}"

    async def _top_map(members: list[str]) -> str | None:
        """Mapa donde la tribu acumula más tiempo."""
        if not members:
            return None
        placeholders = ", ".join(["?"] * len(members))
        cursor2 = await db.execute(
            f"""
            SELECT map_name FROM k4ultra_playtime
            WHERE player_name IN ({placeholders}) AND guild_id = ?
            GROUP BY map_name ORDER BY SUM(total_minutes) DESC LIMIT 1
            """,
            list(members) + [guild_id],
        )
        row = await cursor2.fetchone()
        return row["map_name"] if row else None

    cursor = await db.execute(
        "SELECT name, members_json, is_own FROM k4ultra_fixed_tribes WHERE guild_id = ?",
        (guild_id,),
    )
    fixed_rows = await cursor.fetchall()

    fixed_players: set[str] = set()
    own_blocks: list[str] = []
    fixed_blocks: list[str] = []

    for fr in fixed_rows:
        members = json.loads(fr["members_json"])
        if not members:
            continue
        for m in members:
            fixed_players.add(m)

        n_online = sum(1 for m in members if m in online_set)
        top_map = await _top_map(members)
        map_info = f"  ·  🗺️ {top_map}" if top_map else ""

        members_lines = [line for line in (_format_member(m) for m in members) if line]
        members_text = "  ".join(members_lines)
        header = f"**{fr['name']}**  ·  👥 `{len(members):02d}`  ·  🟢 `{n_online:02d}` online{map_info}"
        block = f"{header}\n  └ {members_text}"

        if fr["is_own"]:
            own_blocks.append(block)
        else:
            fixed_blocks.append(block)

    # Cálculo de tribus dinámicas vía BFS sobre relaciones.
    cursor = await db.execute(
        "SELECT player1, player2, probability_score FROM k4ultra_relationships "
        "WHERE ((probability_score >= 25 AND shared_minutes >= 60) OR is_manual = 1) "
        "AND guild_id = ?",
        (guild_id,),
    )
    rels = await cursor.fetchall()

    adjacency: dict[str, set[str]] = {}
    score_by_pair: dict[tuple[str, str], int] = {}
    for r in rels:
        p1, p2 = r["player1"], r["player2"]
        if p1 in fixed_players or p2 in fixed_players:
            continue
        adjacency.setdefault(p1, set()).add(p2)
        adjacency.setdefault(p2, set()).add(p1)
        score_by_pair[(p1, p2)] = r["probability_score"]
        score_by_pair[(p2, p1)] = r["probability_score"]

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

    dyn_blocks: list[str] = []
    for i, tribe in enumerate(dynamic_tribes[:8], start=1):
        n_online = sum(1 for m in tribe if m in online_set)
        top_map = await _top_map(tribe)
        map_info = f"  ·  🗺️ {top_map}" if top_map else ""

        # Confianza media del cluster.
        scores = [score_by_pair[(a, b)] for a in tribe for b in tribe if a != b and (a, b) in score_by_pair]
        avg_score = sum(scores) // len(scores) if scores else 0
        bars = min(10, max(0, avg_score // 10))
        confidence_bar = "█" * bars + "░" * (10 - bars)

        members_lines = [line for line in (_format_member(m) for m in tribe) if line]
        if len(", ".join(members_lines)) > 200:
            shown = members_lines[:5]
            members_text = "  ".join(shown) + f"  …(+{len(members_lines) - 5})"
        else:
            members_text = "  ".join(members_lines)

        header = (
            f"**Grupo {i}**  ·  👥 `{len(tribe):02d}`  ·  🟢 `{n_online:02d}` online"
            f"{map_info}  ·  📊 `{confidence_bar}` {avg_score}%"
        )
        dyn_blocks.append(f"{header}\n  └ {members_text}")

    # Construcción del embed final con secciones tipo Blacklist/Scouting.
    n_total_known = sum(len(json.loads(fr["members_json"])) for fr in fixed_rows)
    n_total_dyn = sum(len(t) for t in dynamic_tribes)
    n_online_known = sum(1 for fr in fixed_rows for m in json.loads(fr["members_json"]) if m in online_set)

    lines: list[str] = [
        f"🏰 `{len(own_blocks):02d}` Nuestras  ·  🛡️ `{len(fixed_blocks):02d}` Fijadas  ·  "
        f"🔗 `{len(dynamic_tribes):02d}` Predichas  ·  🟢 `{n_online_known:02d}` online",
        "",
    ]

    if own_blocks:
        lines.append("## 🏰 NUESTRA TRIBU")
        lines.extend(own_blocks)
        lines.append("")

    if fixed_blocks:
        lines.append("## 🛡️ TRIBUS FIJADAS")
        lines.extend(fixed_blocks)
        lines.append("")

    if dyn_blocks:
        lines.append("## 🔗 GRUPOS PREDICHOS")
        lines.extend(dyn_blocks)
        if len(dynamic_tribes) > 8:
            lines.append(f"*… y {len(dynamic_tribes) - 8} grupos más con menor confianza.*")

    if not (own_blocks or fixed_blocks or dyn_blocks):
        lines.append("📭 No hay tribus registradas ni grupos predecidos aún.")
        lines.append("")
        lines.append("💡 Usa `/tribu_propia crear` para marcar tu base, o `/fijar_tribu` para conocidas.")

    page_t.description = "\n".join(lines).strip()
    page_t.set_footer(
        text=(
            f"Total jugadores conocidos: {n_total_known + n_total_dyn}  "
            f"•  ⚫ Offline · 🟢 Online  "
            f"•  /tribu_propia · /fijar_tribu"
        )
    )
    return [page_t]
