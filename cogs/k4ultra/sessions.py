"""Ciclo de recogida de datos de jugadores conectados (gather_player_data).

Extraído de ``cogs.k4ultra.cog`` para reducir el tamaño del cog y facilitar
tests. Se invoca cada minuto desde el loop del cog vía ``run(bot)``.

Responsabilidades:
- Determinar qué guilds toca actualizar (basado en ``guild_loop_state``).
- Marcar ``last_a2s_run`` antes de consultar A2S (evita dobles ejecuciones).
- Consultar A2S vía ``cogs.server_status.query_all_servers`` (caché compartida).
- Resolver identidades (alias, transferencias, sesiones recientes, genéricos
  con sufijo).
- Actualizar ``k4ultra_playtime`` y enriquecer ``blacklist`` con horas/last_seen.
- Cerrar sesiones inactivas con margen de gracia.
- Auto-blacklist de jugadores no-tribales.
- Actualizar todos los dashboards K4Ultra registrados.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from datetime import datetime, timedelta

import aiosqlite
import discord

from cogs.k4ultra.embeds import generate_k4ultra_embed
from cogs.k4ultra.ui import K4UltraView
from utils import bus

logger = logging.getLogger("ArkTribeBot")


# Conjunto de nombres "tipo genéricos" que ARK reporta por defecto cuando un
# jugador no ha personalizado el de Steam. Se tratan especialmente para evitar
# colisiones de identidad.
GENERIC_NAMES: frozenset[str] = frozenset({"123", "human", "humano", "survivor", "player", "bob"})


def _extract_base(ident: str) -> str:
    """Quita el sufijo numérico ``_NN`` del identificador (ej. ``123_5`` → ``123``)."""
    parts = ident.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return ident


def _duration_score(session: dict, a2s_duration: float, now: datetime) -> int:
    """Puntuación de compatibilidad entre la duración A2S y una sesión cerrada.

    Sustituye al closure que provocaba el warning B023 — ahora ``a2s_duration``
    y ``now`` son parámetros explícitos en vez de capturarse del entorno.
    """
    last_dur = session.get("last_duration", 0) or 0
    end_t = session.get("end_time", "")
    if not end_t:
        return 0
    try:
        end_dt = datetime.strptime(end_t, "%Y-%m-%d %H:%M:%S")
        gap_secs = (now - end_dt).total_seconds()
    except (ValueError, TypeError):
        gap_secs = 9999

    score = 0
    # A2S corta (<15 min) + sesión cerrada hace poco → mismo jugador reconectando.
    if a2s_duration < 900 and gap_secs < 900:
        score += 10
    # A2S larga con duración similar a la histórica → A2S manteniendo timer del mismo jugador.
    elif last_dur > 0 and a2s_duration > 900:
        diff_ratio = abs(a2s_duration - last_dur) / max(last_dur, 1)
        if diff_ratio < 0.3:
            score += 8
    # Bonificación por cierre reciente (indica reconexión).
    if gap_secs < 600:
        score += 3
    return score


async def run(bot) -> None:  # noqa: C901 - lógica de identidad densa pero coherente
    """Ejecuta un ciclo completo de recolección y actualización de sesiones."""
    from cogs.server_status import get_guild_servers, query_all_servers

    now = datetime.utcnow()
    db = bot.db
    guild_rows = await db.fetchall(
        """
        SELECT gc.guild_id, gc.update_interval, gls.last_a2s_run
        FROM guild_config gc
        LEFT JOIN guild_loop_state gls ON gls.guild_id = gc.guild_id
        """
    )

    # 1. Determinar qué guilds toca actualizar según el tiempo transcurrido.
    guilds_to_update: list[int] = []
    for row in guild_rows:
        intrvl = row["update_interval"] if row["update_interval"] else 5
        last_run_raw = row["last_a2s_run"]
        if last_run_raw is None:
            guilds_to_update.append(row["guild_id"])
            continue
        try:
            last_run = datetime.fromisoformat(last_run_raw)
        except (TypeError, ValueError):
            guilds_to_update.append(row["guild_id"])
            continue
        if now - last_run >= timedelta(minutes=intrvl):
            guilds_to_update.append(row["guild_id"])

    if not guilds_to_update:
        return

    # 2. Marcar antes de consultar (evita dobles ejecuciones si el loop se solapa).
    now_iso = now.isoformat(timespec="seconds")
    for g_id in guilds_to_update:
        await db.execute(
            "INSERT INTO guild_loop_state (guild_id, last_a2s_run) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET last_a2s_run = excluded.last_a2s_run",
            (g_id, now_iso),
        )
    await db.commit()

    # 3. Consulta A2S centralizada (compartida con server_status via caché de 90s).
    all_fetched_raw = []
    all_guild_servers_set = []
    for guild_id in guilds_to_update:
        g_servers = await get_guild_servers(bot, guild_id)
        if not g_servers:
            continue
        results = await query_all_servers(bot, guild_id, g_servers)
        for map_name, data in results.items():
            all_guild_servers_set.append((guild_id, map_name))
            if data.get("error"):
                continue
            for p in data["players"]:
                all_fetched_raw.append(
                    {
                        "guild_id": guild_id,
                        "map": map_name,
                        "raw_name": p["name"],
                        "duration": p["duration"],
                    }
                )

    successfully_queried = set(all_guild_servers_set)

    now = datetime.now()

    # 4. Aplicar tabla de identidades (secondary → primary).
    identities: dict[int, dict[str, str]] = {}
    for g_id in guilds_to_update:
        rows = await db.fetchall(
            "SELECT secondary_name, primary_name FROM player_identities_link WHERE guild_id = ?",
            (g_id,),
        )
        identities[g_id] = {row["secondary_name"].lower(): row["primary_name"] for row in rows}

    all_fetched = []
    for fp in all_fetched_raw:
        g_identities = identities.get(fp["guild_id"], {})
        raw_name = fp["raw_name"]
        if not raw_name:
            continue
        true_name = g_identities.get(raw_name.lower(), raw_name)
        all_fetched.append(
            {
                "guild_id": fp["guild_id"],
                "map": fp["map"],
                "raw_name": true_name,
                "duration": fp["duration"],
            }
        )

    # 5. Cargar pools de sesiones activas y recientes-cerradas.
    cursor = await db.execute(
        "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 1"
    )
    active_pool = [dict(s) for s in await cursor.fetchall()]

    ten_mins_ago = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    cursor = await db.execute(
        "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND end_time >= ? ORDER BY end_time DESC",
        (ten_mins_ago,),
    )
    recent_closed_pool = [dict(s) for s in await cursor.fetchall()]

    seen_identities: set[int] = set()
    active_pool_dict: dict[int, dict] = {s["id"]: s for s in active_pool}

    # 6. Pasada 1: Matching directo contra sesiones activas en mismo mapa.
    for fp in all_fetched:
        map_m = fp["map"]
        raw_name = fp["raw_name"]
        true_identity = None
        for sid, s in active_pool_dict.items():
            if sid not in seen_identities and s["map_name"] == map_m and s["guild_id"] == fp["guild_id"]:
                if _extract_base(s["player_name"]) == raw_name:
                    true_identity = s["player_name"]
                    fp["true_identity"] = true_identity
                    seen_identities.add(sid)
                    await db.execute(
                        "UPDATE k4ultra_sessions SET end_time = ?, last_duration = ? WHERE id = ?",
                        (now.strftime("%Y-%m-%d %H:%M:%S"), fp.get("duration", 0), sid),
                    )
                    fp["matched"] = True
                    break

    # 7. Pasada 2: reconexiones / transferencias / nuevas sesiones.
    for fp in all_fetched:
        if fp.get("matched"):
            continue

        map_m = fp["map"]
        raw_name = fp["raw_name"]
        true_identity = None

        identities_already_online = [
            active_pool_dict[sid]["player_name"] for sid in seen_identities if sid in active_pool_dict
        ]

        is_generic = raw_name.lower() in GENERIC_NAMES

        # Para nombres únicos basta con mirar transferencias recientes.
        # Para genéricos hay que considerar todo el histórico inactivo.
        pool_to_check = recent_closed_pool
        if is_generic:
            cursor = await db.execute(
                "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND player_name LIKE ? AND guild_id = ? ORDER BY end_time DESC",
                (f"{raw_name}_%", fp["guild_id"]),
            )
            cursor2 = await db.execute(
                "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND player_name = ? AND guild_id = ? ORDER BY end_time DESC",
                (raw_name, fp["guild_id"]),
            )
            generic_inactive = [dict(s) for s in await cursor.fetchall()]
            generic_inactive.extend([dict(s) for s in await cursor2.fetchall()])

            # Reconexiones instantáneas en el mismo tick.
            for sid, sinfo in active_pool_dict.items():
                if (
                    sid not in seen_identities
                    and _extract_base(sinfo["player_name"]) == raw_name
                    and sinfo["guild_id"] == fp["guild_id"]
                ):
                    generic_inactive.append(
                        {
                            "id": sinfo["id"],
                            "player_name": sinfo["player_name"],
                            "map_name": sinfo["map_name"],
                            "guild_id": sinfo["guild_id"],
                            "start_time": sinfo.get("start_time", ""),
                            "end_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

            # Ordenar por compatibilidad (mayor score primero, después end_time).
            a2s_duration = fp.get("duration", 0)
            generic_inactive.sort(
                key=lambda s: (_duration_score(s, a2s_duration, now), s["end_time"]),
                reverse=True,
            )
            pool_to_check = generic_inactive

        for s in pool_to_check:
            if (
                _extract_base(s["player_name"]) == raw_name
                and s["player_name"] not in identities_already_online
                and s["guild_id"] == fp["guild_id"]
            ):
                true_identity = s["player_name"]
                cursor = await db.execute(
                    "INSERT INTO k4ultra_sessions (player_name, map_name, guild_id, start_time, end_time, is_active, last_duration) VALUES (?, ?, ?, ?, ?, 1, ?)",
                    (
                        true_identity,
                        map_m,
                        fp["guild_id"],
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        fp.get("duration", 0),
                    ),
                )
                new_id = cursor.lastrowid
                seen_identities.add(new_id)
                active_pool_dict[new_id] = {
                    "id": new_id,
                    "player_name": true_identity,
                    "map_name": map_m,
                    "guild_id": fp["guild_id"],
                }
                fp["true_identity"] = true_identity
                break

        if not true_identity:
            # Jugador nuevo absoluto.
            if is_generic:
                cursor = await db.execute(
                    "SELECT player_name FROM k4ultra_sessions WHERE player_name LIKE ? AND guild_id = ?",
                    (f"{raw_name}_%", fp["guild_id"]),
                )
                existing = await cursor.fetchall()
                max_suffix = 0
                for e in existing:
                    parts = e["player_name"].rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit() and parts[0] == raw_name:
                        val = int(parts[1])
                        if val > max_suffix:
                            max_suffix = val

                # Usar el nombre base si está libre, si no añadir sufijo.
                if raw_name not in identities_already_online and not any(
                    e["player_name"] == raw_name for e in existing
                ):
                    true_identity = raw_name
                else:
                    true_identity = f"{raw_name}_{max_suffix + 1}"
            else:
                true_identity = raw_name

            cursor = await db.execute(
                "INSERT INTO k4ultra_sessions (player_name, map_name, guild_id, start_time, end_time, is_active, last_duration) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (
                    true_identity,
                    map_m,
                    fp["guild_id"],
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                    fp.get("duration", 0),
                ),
            )
            new_id = cursor.lastrowid
            seen_identities.add(new_id)
            active_pool_dict[new_id] = {
                "id": new_id,
                "player_name": true_identity,
                "map_name": map_m,
                "guild_id": fp["guild_id"],
            }
            fp["true_identity"] = true_identity

    # 8. Acumular tiempo en k4ultra_playtime y blacklist.
    for fp in all_fetched:
        t_identity = fp.get("true_identity")
        t_map = fp.get("map")
        if not t_identity:
            continue

        cursor = await db.execute(
            "SELECT id FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
            (t_identity, t_map, fp["guild_id"]),
        )
        pt_row = await cursor.fetchone()
        if pt_row:
            await db.execute(
                "UPDATE k4ultra_playtime SET total_minutes = total_minutes + 5, last_seen = ? WHERE id = ?",
                (now.strftime("%Y-%m-%d %H:%M:%S"), pt_row["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO k4ultra_playtime (player_name, map_name, guild_id, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                (t_identity, t_map, fp["guild_id"], 5, now.strftime("%Y-%m-%d %H:%M:%S")),
            )

        try:
            cursor = await db.execute(
                "SELECT id, total_hours FROM blacklist WHERE player = ? AND guild_id = ?",
                (t_identity, fp["guild_id"]),
            )
            bl_row = await cursor.fetchone()
            if bl_row:
                new_total = (bl_row["total_hours"] or 0.0) + (5 / 60.0)
                await db.execute(
                    "UPDATE blacklist SET last_seen = ?, map = ?, total_hours = ? WHERE id = ?",
                    (now.strftime("%Y-%m-%d %H:%M:%S"), t_map, new_total, bl_row["id"]),
                )
        except Exception as e:
            logger.error(f"[K4Ultra] Error enriqueciendo blacklist para {t_identity}: {e}")

    # 9. Cerrar sesiones inactivas (con margen de gracia + detección de transfers).
    identities_online_now = {
        (fp["guild_id"], fp["true_identity"]) for fp in all_fetched if fp.get("true_identity")
    }

    for sid, s in active_pool_dict.items():
        if sid not in seen_identities and sid in [a["id"] for a in active_pool]:
            if (s["guild_id"], s["map_name"]) in successfully_queried:
                # Si el jugador apareció en OTRO mapa este ciclo → transfer → cierre inmediato.
                is_transfer = (s["guild_id"], s["player_name"]) in identities_online_now
                if is_transfer:
                    await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))
                else:
                    # Margen de gracia 10 min ante fallos de red.
                    try:
                        last_seen = datetime.strptime(s["end_time"], "%Y-%m-%d %H:%M:%S")
                        if (now - last_seen).total_seconds() > 600:
                            await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))
                    except Exception:
                        await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))

    await db.commit()

    # 10. Auto-blacklist de jugadores no-tribales.
    try:
        for guild_id in [gr["guild_id"] for gr in guild_rows]:
            cursor = await db.execute(
                "SELECT members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?",
                (guild_id,),
            )
            unnamed_row = await cursor.fetchone()
            if not unnamed_row:
                continue

            unnamed_members = {m.lower() for m in json.loads(unnamed_row["members_json"])}

            blacklisted: set[str] = set()
            try:
                cursor = await db.execute("SELECT player FROM blacklist WHERE guild_id = ?", (guild_id,))
                blacklisted = {r["player"].lower() for r in await cursor.fetchall()}
            except aiosqlite.OperationalError:
                pass

            new_blacklist_count = 0
            created_at = dt.date.today().isoformat()

            for sid in seen_identities:
                if sid in active_pool_dict:
                    s_info = active_pool_dict[sid]
                    if s_info["guild_id"] != guild_id:
                        continue
                    t_name = s_info["player_name"]
                    t_map = s_info["map_name"]
                    if t_name.lower() not in unnamed_members and t_name.lower() not in blacklisted:
                        try:
                            await db.execute(
                                "INSERT INTO blacklist (guild_id, player, tribe, map, notes, created_at, is_enemy) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (
                                    guild_id,
                                    t_name,
                                    "Desconocido",
                                    t_map,
                                    "Pasaporte registrado (K4Ultra)",
                                    created_at,
                                    0,
                                ),
                            )
                            blacklisted.add(t_name.lower())
                            new_blacklist_count += 1
                        except aiosqlite.OperationalError:
                            pass

            if new_blacklist_count > 0:
                await db.commit()
                bot.dispatch(bus.BLACKLIST_UPDATED, guild_id)
    except Exception as e:
        logger.error(f"[K4Ultra] Auto-blacklist check failed: {e}")

    # 11. Actualización de los dashboards K4Ultra.
    db.conn.row_factory = aiosqlite.Row
    rows = await db.fetchall("SELECT id, guild_id, channel_id, message_id, mode FROM k4ultra_messages")
    if not rows:
        return

    messages_to_remove: list[int] = []
    for row in rows:
        row_id = row["id"]
        guild_id = row["guild_id"]
        channel_id = row["channel_id"]
        message_id = row["message_id"]
        mode = row["mode"] if "mode" in row.keys() else "radar"

        pages, top_players, k4_aliases = await generate_k4ultra_embed(bot, guild_id, mode)

        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            if not channel:
                messages_to_remove.append(row_id)
                continue

            message = await channel.fetch_message(message_id)

            # En refresh automático forzamos página 0 para evitar quedar en una página
            # vacía si el ranking se acorta entre ticks.
            if mode == "tribus":
                await message.edit(embed=pages[0], view=None)
            else:
                view = K4UltraView(
                    bot,
                    guild_id,
                    top_players,
                    k4_aliases,
                    pages=pages,
                    current_page=0,
                    mode=mode,
                )
                await message.edit(embed=pages[0], view=view)
        except discord.NotFound:
            messages_to_remove.append(row_id)
        except discord.Forbidden as e:
            logger.debug(f"[K4Ultra] Sin permiso para editar {row_id}: {e}")
        except discord.HTTPException as e:
            logger.error(f"[K4Ultra] HTTPException actualizando {row_id}: {e}")
        except Exception as e:
            logger.error(f"[K4Ultra] Error actualizando dashboard {row_id}: {e}")

    if messages_to_remove:
        for msg_id in messages_to_remove:
            await db.execute("DELETE FROM k4ultra_messages WHERE id = ?", (msg_id,))
        await db.commit()
