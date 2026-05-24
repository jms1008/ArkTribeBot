"""Cálculo diario de relaciones entre jugadores (calculate_relationships).

Extraído de ``cogs.k4ultra.cog`` para reducir el tamaño del cog.
Se invoca cada 24 h desde el loop del cog vía ``run(bot)``.

Reglas que aplica (por guild, sobre las sesiones del día anterior):
- **Regla A**: minutos superpuestos en el mismo mapa → ``shared_minutes``.
  Cada 180 min compartidos suman 1 punto.
- **Regla B**: transferencias simultáneas (mismo mapa A→B en ≤5 min) → +5 puntos.
- **Regla C**: login Y logout sincronizados (≤3 min) → +2 puntos.

Decaimiento: relaciones no manuales pierden el 5 % diario, las que caen por
debajo de 2 se purgan.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from cogs.k4ultra.embeds import generate_k4ultra_embed

logger = logging.getLogger("ArkTribeBot")


def _add(dict_: dict[tuple[str, str], int], a: str, b: str, val: int) -> None:
    """Suma ``val`` a ``dict_[(min(a,b), max(a,b))]``.

    Sustituye a las closures ``add_points`` / ``add_mins`` que capturaban el dict
    desde el scope del bucle (warning B023). Aquí el dict es parámetro explícito.
    """
    if a > b:
        a, b = b, a
    dict_[(a, b)] = dict_.get((a, b), 0) + val


async def run(bot) -> None:
    """Ejecuta un ciclo completo de cálculo de relaciones."""
    now = datetime.now()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)
    ys_str = yesterday_start.strftime("%Y-%m-%d %H:%M:%S")
    ye_str = yesterday_end.strftime("%Y-%m-%d %H:%M:%S")

    db = bot.db

    # Decaimiento del 5 % diario en relaciones no manuales + purga de residuos.
    await db.execute(
        "UPDATE k4ultra_relationships SET probability_score = CAST(probability_score * 0.95 AS INTEGER) WHERE is_manual = 0"
    )
    await db.execute("DELETE FROM k4ultra_relationships WHERE probability_score < 2 AND is_manual = 0")

    guild_rows = await db.fetchall("SELECT guild_id FROM guild_config")

    for g_row in guild_rows:
        guild_id = g_row["guild_id"]

        # Tabla auxiliar para idempotencia (1 cálculo por día y guild).
        await db.execute(
            "CREATE TABLE IF NOT EXISTS k4ultra_config (guild_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (guild_id, key))"
        )
        prev = await db.fetchone(
            "SELECT value FROM k4ultra_config WHERE key = 'last_calc_date' AND guild_id = ?",
            (guild_id,),
        )
        today_str = now.strftime("%Y-%m-%d")
        if prev and prev["value"] == today_str:
            continue  # Ya calculado hoy.

        sessions = await db.fetchall(
            "SELECT player_name, map_name, start_time, end_time FROM k4ultra_sessions "
            "WHERE start_time >= ? AND start_time < ? AND guild_id = ?",
            (ys_str, ye_str, guild_id),
        )
        if not sessions:
            continue

        points_to_add: dict[tuple[str, str], int] = {}
        shared_mins_to_add: dict[tuple[str, str], int] = {}

        # Parsear sesiones (cap del end al fin del día).
        parsed_sessions = []
        for s in sessions:
            st = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
            end_str = s["end_time"]
            if end_str > ye_str:
                end_str = ye_str
            et = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            parsed_sessions.append({"p": s["player_name"], "m": s["map_name"], "st": st, "et": et})

        player_sessions: dict[str, list[dict]] = defaultdict(list)
        for s in parsed_sessions:
            player_sessions[s["p"]].append(s)
        for p in player_sessions:
            player_sessions[p].sort(key=lambda x: x["st"])

        players = list(player_sessions.keys())

        # Aplicar las 3 reglas a cada par no ordenado.
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                p1 = players[i]
                p2 = players[j]
                s1_list = player_sessions[p1]
                s2_list = player_sessions[p2]

                # Regla A: minutos superpuestos en el mismo mapa.
                for s1 in s1_list:
                    for s2 in s2_list:
                        if s1["m"] == s2["m"]:
                            overlap_start = max(s1["st"], s2["st"])
                            overlap_end = min(s1["et"], s2["et"])
                            if overlap_end > overlap_start:
                                mins = int((overlap_end - overlap_start).total_seconds() / 60)
                                _add(shared_mins_to_add, p1, p2, mins)

                # Regla C: sincronía total (login + logout).
                login_sync = abs((s1_list[0]["st"] - s2_list[0]["st"]).total_seconds()) <= 180
                logout_sync = abs((s1_list[-1]["et"] - s2_list[-1]["et"]).total_seconds()) <= 180
                if login_sync and logout_sync:
                    _add(points_to_add, p1, p2, 2)

                # Regla B: transferencias simultáneas mismo mapa-a-mismo mapa.
                for k1 in range(len(s1_list) - 1):
                    t1_end = s1_list[k1]["et"]
                    t1_map1 = s1_list[k1]["m"]
                    t1_start2 = s1_list[k1 + 1]["st"]
                    t1_map2 = s1_list[k1 + 1]["m"]

                    if t1_map1 == t1_map2:
                        continue

                    for k2 in range(len(s2_list) - 1):
                        t2_end = s2_list[k2]["et"]
                        t2_map1 = s2_list[k2]["m"]
                        t2_start2 = s2_list[k2 + 1]["st"]
                        t2_map2 = s2_list[k2 + 1]["m"]

                        if (
                            t2_map1 == t1_map1
                            and t2_map2 == t1_map2
                            and abs((t1_end - t2_end).total_seconds()) <= 300
                            and abs((t1_start2 - t2_start2).total_seconds()) <= 300
                        ):
                            _add(points_to_add, p1, p2, 5)

            # Volcado de minutos compartidos + puntos derivados de Regla A.
            for (p1, p2), mins in shared_mins_to_add.items():
                row = await db.fetchone(
                    "SELECT probability_score, shared_minutes, is_manual FROM k4ultra_relationships "
                    "WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                    (p1, p2, guild_id),
                )
                pts_to_add = points_to_add.get((p1, p2), 0)

                if row:
                    old_mins = row["shared_minutes"] if "shared_minutes" in row.keys() else 0
                    new_mins = old_mins + mins
                    # Cada 180 min de overlap suman 1 punto (delta sobre el bucket anterior).
                    pts_to_add += (new_mins // 180) - (old_mins // 180)
                    if row["is_manual"] == 0:
                        await db.execute(
                            "UPDATE k4ultra_relationships SET probability_score = probability_score + ?, shared_minutes = ? "
                            "WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                            (pts_to_add, new_mins, p1, p2, guild_id),
                        )
                else:
                    pts_to_add += mins // 180
                    if pts_to_add > 0:
                        await db.execute(
                            "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, shared_minutes, is_manual) "
                            "VALUES (?, ?, ?, ?, ?, 0)",
                            (guild_id, p1, p2, pts_to_add, mins),
                        )

            # Aplicar puntos exclusivos de Reglas B y C (sin overlap → sin Regla A).
            for (p1, p2), pts in points_to_add.items():
                if (p1, p2) in shared_mins_to_add:
                    continue
                row = await db.fetchone(
                    "SELECT probability_score, is_manual FROM k4ultra_relationships "
                    "WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                    (p1, p2, guild_id),
                )
                if row:
                    if row["is_manual"] == 0:
                        await db.execute(
                            "UPDATE k4ultra_relationships SET probability_score = probability_score + ? "
                            "WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                            (pts, p1, p2, guild_id),
                        )
                elif pts > 0:
                    await db.execute(
                        "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, shared_minutes, is_manual) "
                        "VALUES (?, ?, ?, ?, 0, 0)",
                        (guild_id, p1, p2, pts),
                    )

        # Marcar cálculo del día como completado.
        await db.execute(
            "INSERT OR REPLACE INTO k4ultra_config (guild_id, key, value) VALUES (?, 'last_calc_date', ?)",
            (guild_id, today_str),
        )

    # Limpieza mensual de logs crudos.
    await db.execute("DELETE FROM k4ultra_players_log WHERE timestamp < datetime('now', '-30 days')")
    await db.commit()

    # Snapshot semanal (lunes).
    if now.weekday() == 0:
        current_week = now.isocalendar()[1]
        guilds = await db.fetchall("SELECT DISTINCT guild_id FROM k4ultra_playtime")
        for guild_row in guilds:
            g_id = guild_row["guild_id"]
            existing = await db.fetchone(
                "SELECT id FROM k4ultra_snapshots WHERE week_number = ? AND guild_id = ?",
                (current_week, g_id),
            )
            if existing:
                continue

            pages, _, _aliases = await generate_k4ultra_embed(bot, g_id)
            embed = pages[0]
            embed.title = f"🌐 Tracker de Jugadores K4Ultra - Semana {current_week}"
            embed.description = "Registro inmutable de la semana."
            embed.set_footer(text=f"Guardado automáticamente: {now.strftime('%Y-%m-%d')}")

            embed_json = json.dumps(embed.to_dict())
            await db.execute(
                "INSERT INTO k4ultra_snapshots (week_number, guild_id, embed_json) VALUES (?, ?, ?)",
                (current_week, g_id, embed_json),
            )
            await db.commit()
