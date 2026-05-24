import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
import json
from cogs.k4ultra.ui import K4UltraView
from utils import bus

logger = logging.getLogger("ArkTribeBot")


class K4Ultra(commands.Cog, name="K4Ultra"):
    def __init__(self, bot):
        self.bot = bot
        self.gather_player_data.start()

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard interactivo de K4Ultra."""
        import aiosqlite
        import asyncio
        from cogs.management import INFO_TEXTS
        from cogs.k4ultra.ui import K4UltraView
        
        info_embed = discord.Embed(
            description=INFO_TEXTS["k4ultra"],
            color=discord.Color.from_rgb(43, 45, 49),
        )
        await channel.send(embed=info_embed)

        pages_k, top_players_k, k4_aliases_k = await self.generate_k4ultra_embed(guild_id)
        view_k = K4UltraView(self.bot, guild_id, top_players_k, k4_aliases_k)
        msg = await channel.send(embed=pages_k[0], view=view_k)
        await asyncio.sleep(0.5)

        db = self.bot.db
        await db.execute(
            "INSERT INTO k4ultra_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (guild_id, channel.id, msg.id),
        )
        await db.commit()
        self.calculate_relationships.start()

    def cog_unload(self):
        self.gather_player_data.cancel()
        self.calculate_relationships.cancel()

    @tasks.loop(minutes=1)
    async def gather_player_data(self):
        """Tarea en segundo plano que recopila datos de los jugadores en base a su update_interval configurado.

        Programación basada en ``guild_loop_state.last_a2s_run`` (en lugar de
        ``current_minute % interval``) para que un reinicio del bot no haga saltar
        un ciclo entero por mala suerte de timing.
        """
        await self.bot.wait_until_ready()

        from datetime import datetime, timedelta

        from cogs.server_status import get_guild_servers, query_all_servers

        now = datetime.utcnow()
        db = self.bot.db
        guild_rows = await db.fetchall(
            """
            SELECT gc.guild_id, gc.update_interval, gls.last_a2s_run
            FROM guild_config gc
            LEFT JOIN guild_loop_state gls ON gls.guild_id = gc.guild_id
            """
        )

        # Determinar qué guilds toca actualizar según el tiempo transcurrido.
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

        # Marcar antes de consultar para evitar dobles ejecuciones si el loop se solapa.
        now_iso = now.isoformat(timespec="seconds")
        for g_id in guilds_to_update:
            await db.execute(
                "INSERT INTO guild_loop_state (guild_id, last_a2s_run) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET last_a2s_run = excluded.last_a2s_run",
                (g_id, now_iso),
            )
        await db.commit()

        # Consulta A2S centralizada (compartida con server_status via caché de 90s).
        all_fetched_raw = []
        all_guild_servers_set = []
        for guild_id in guilds_to_update:
            g_servers = await get_guild_servers(self.bot, guild_id)
            if not g_servers:
                continue
            results = await query_all_servers(self.bot, guild_id, g_servers)
            for map_name, data in results.items():
                all_guild_servers_set.append((guild_id, map_name))
                if data.get("error"):
                    continue
                for p in data["players"]:
                    all_fetched_raw.append({
                        "guild_id": guild_id,
                        "map": map_name,
                        "raw_name": p["name"],
                        "duration": p["duration"],
                    })

        # Registro de qué servidores (guild, mapa) fueron consultados con éxito
        successfully_queried = set(all_guild_servers_set)

        now = datetime.now()

        # Diccionario para reemplazo en tiempo real (secondary -> primary).
        identities = {}
        for g_id in guilds_to_update:
            rows = await self.bot.db.fetchall(
                "SELECT secondary_name, primary_name FROM player_identities_link WHERE guild_id = ?",
                (g_id,),
            )
            identities[g_id] = {row["secondary_name"].lower(): row["primary_name"] for row in rows}

        db = self.bot.db

        all_fetched = []
        for fp in all_fetched_raw:
            g_identities = identities.get(fp["guild_id"], {})
            raw_name = fp["raw_name"]
            if not raw_name:
                continue
            # Verificamos si este nombre fue fusionado alguna vez a otra cuenta principal
            true_name = g_identities.get(raw_name.lower(), raw_name)
            
            all_fetched.append({
                "guild_id": fp["guild_id"], 
                "map": fp["map"], 
                "raw_name": true_name, 
                "duration": fp["duration"]
            })

        db = self.bot.db


        cursor = await db.execute(
            "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 1"
        )
        active_pool = [dict(s) for s in await cursor.fetchall()]

        # Migración de last_duration delegada a db/schema.py.

        ten_mins_ago = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND end_time >= ? ORDER BY end_time DESC",
            (ten_mins_ago,),
        )
        recent_closed_pool = [dict(s) for s in await cursor.fetchall()]

        seen_identities = set()
        active_pool_dict = {s["id"]: s for s in active_pool}  # helpful tracker

        def extract_base(ident):
            parts = ident.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                return parts[0]
            return ident

        for fp in all_fetched:
            map_m = fp["map"]
            raw_name = fp["raw_name"]

            # Pasada 1: Búsqueda de sesiones activas coincidentes en el mismo mapa
            true_identity = None
            for sid, s in active_pool_dict.items():
                if sid not in seen_identities and s["map_name"] == map_m and s["guild_id"] == fp["guild_id"]:
                    if extract_base(s["player_name"]) == raw_name:
                        true_identity = s["player_name"]
                        fp["true_identity"] = true_identity
                        seen_identities.add(sid)
                        await db.execute(
                            "UPDATE k4ultra_sessions SET end_time = ?, last_duration = ? WHERE id = ?",
                            (now.strftime("%Y-%m-%d %H:%M:%S"), fp.get("duration", 0), sid),
                        )
                        fp["matched"] = True
                        break

        # Pasada 2: Resolución de reconexiones, transferencias o nuevas sesiones
        for fp in all_fetched:
            if fp.get("matched"):
                continue

            map_m = fp["map"]
            raw_name = fp["raw_name"]
            true_identity = None

            # Verificación de desconexiones recientes (transferencias o reconexiones)
            # Exclusión de identidades ya procesadas en este ciclo (multicuenta rápida)
            identities_already_online = [
                active_pool_dict[sid]["player_name"]
                for sid in seen_identities
                if sid in active_pool_dict
            ]

            generic_names = {"123", "human", "humano", "survivor", "player", "bob"}
            is_generic = raw_name.lower() in generic_names

            # Reutilización de ID para nombres genéricos en cualquier sesión inactiva
            # Uso de transferencias recientes (últimos 10 min) para nombres únicos
            pool_to_check = recent_closed_pool
            if is_generic:
                # Recuperación de sesiones inactivas bajo el mismo nombre base
                cursor = await db.execute(
                    "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND player_name LIKE ? AND guild_id = ? ORDER BY end_time DESC",
                    (f"{raw_name}_%", fp["guild_id"]),
                )
                # Inclusión del propio nombre base si constaba inactivo
                cursor2 = await db.execute(
                    "SELECT id, player_name, map_name, guild_id, start_time, end_time, last_duration FROM k4ultra_sessions WHERE is_active = 0 AND player_name = ? AND guild_id = ? ORDER BY end_time DESC",
                    (raw_name, fp["guild_id"]),
                )

                generic_inactive = [dict(s) for s in await cursor.fetchall()]
                generic_inactive.extend([dict(s) for s in await cursor2.fetchall()])

                # Inclusión de reconexiones instantáneas en el mismo ciclo (tick)
                for sid, sinfo in active_pool_dict.items():
                    if (
                        sid not in seen_identities
                        and extract_base(sinfo["player_name"]) == raw_name
                        and sinfo["guild_id"] == fp["guild_id"]
                    ):
                        # Simulación de sesión inactiva reciente
                        dummy_inactive = {
                            "id": sinfo["id"],
                            "player_name": sinfo["player_name"],
                            "map_name": sinfo["map_name"],
                            "guild_id": sinfo["guild_id"],
                            "start_time": sinfo.get("start_time", ""),
                            "end_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        generic_inactive.append(dummy_inactive)

                # --- Heurística de duración A2S para desambiguación ---
                # A2S reporta cuántos segundos lleva el jugador en el servidor.
                # Si la duración A2S es corta (<15 min) y una sesión cerró hace poco,
                # es probable que sea el MISMO jugador reconectando.
                # Si la duración A2S es larga pero no coincide con ningún historial,
                # probablemente es un jugador DIFERENTE.
                a2s_duration = fp.get("duration", 0)  # segundos

                def duration_score(session):
                    """Puntuación de compatibilidad entre duración A2S y sesión histórica."""
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
                    # Si A2S reporta <15 min y la sesión cerró hace poco (<15 min),
                    # es muy probable que sea reconexion del mismo jugador
                    if a2s_duration < 900 and gap_secs < 900:
                        score += 10
                    # Si A2S reporta duración larga y la sesión tenía duración similar,
                    # probablemente es el mismo jugador (A2S mantiene el timer)
                    elif last_dur > 0 and a2s_duration > 900:
                        diff_ratio = abs(a2s_duration - last_dur) / max(last_dur, 1)
                        if diff_ratio < 0.3:  # Menos del 30% de diferencia
                            score += 8
                    # Bonificación por cierre reciente (indica reconexion)
                    if gap_secs < 600:
                        score += 3
                    return score

                generic_inactive.sort(
                    key=lambda x: (duration_score(x), x["end_time"]),
                    reverse=True,
                )

                pool_to_check = generic_inactive

            for s in pool_to_check:
                if (
                    extract_base(s["player_name"]) == raw_name
                    and s["player_name"] not in identities_already_online
                    and s["guild_id"] == fp["guild_id"]
                ):
                    true_identity = s["player_name"]
                    # Creación de nueva sesión tras salto o reconexión
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
                        "guild_id": fp["guild_id"]
                    }
                    fp["true_identity"] = true_identity
                    break

            if not true_identity:
                # Procesamiento de nuevo usuario recurrente absoluto
                if is_generic:
                    # Generación de un nuevo sufijo (si los anteriores están ocupados)
                    cursor = await db.execute(
                        "SELECT player_name FROM k4ultra_sessions WHERE player_name LIKE ? AND guild_id = ?",
                        (f"{raw_name}_%", fp["guild_id"]),
                    )
                    existing = await cursor.fetchall()
                    max_suffix = 0
                    for e in existing:
                        parts = e["player_name"].rsplit("_", 1)
                        if (
                            len(parts) == 2
                            and parts[1].isdigit()
                            and parts[0] == raw_name
                        ):
                            val = int(parts[1])
                            if val > max_suffix:
                                max_suffix = val

                    # Si el inicial y la BD inactiva no coinciden...
                    # ...comprobación sobre el nombre base online para asignar siguiente sufijo
                    if raw_name not in identities_already_online and not any(
                        e["player_name"] == raw_name for e in existing
                    ):
                        true_identity = raw_name
                    else:
                        true_identity = f"{raw_name}_{max_suffix + 1}"
                else:
                    # Asignación de nombre original a jugadores no genéricos
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
                    "guild_id": fp["guild_id"]
                }
                fp["true_identity"] = true_identity

        # --- Actualización Global de Tiempo (Playtime y Blacklist) ---
        # Se aplica a TODOS los jugadores detectados en este ciclo
        for fp in all_fetched:
            t_identity = fp.get("true_identity")
            t_map = fp.get("map")
            if not t_identity:
                continue

            # 1. k4ultra_playtime (Estadísticas por mapa)
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

            # 2. blacklist (Estadísticas globales de horas por servidor)
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

        # Identidades confirmadas como online en este ciclo (para detectar transfers)
        identities_online_now = set(
            (fp["guild_id"], fp["true_identity"]) 
            for fp in all_fetched if fp.get("true_identity")
        )

        # Marcado de inactividad de sesiones cerradas
        # SOLO para servidores que han sido consultados con éxito en este ciclo
        for sid, s in active_pool_dict.items():
            if sid not in seen_identities and sid in [a["id"] for a in active_pool]:
                if (s["guild_id"], s["map_name"]) in successfully_queried:
                    # Si el jugador ha sido visto en OTRO mapa este mismo ciclo (Transfer)
                    # cerramos la sesión antigua inmediatamente sin margen de gracia.
                    is_transfer = (s["guild_id"], s["player_name"]) in identities_online_now
                        
                    if is_transfer:
                        await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))
                    else:
                        # Margen de gracia: No cerrar si se vio por última vez hace menos de 10 min
                        # Esto protege contra fallos de red o A2S temporalmente vacío.
                        try:
                            last_seen = datetime.strptime(s["end_time"], "%Y-%m-%d %H:%M:%S")
                            if (now - last_seen).total_seconds() > 600:
                                await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))
                        except Exception:
                            # Fallback si el tiempo está corrupto
                            await db.execute("UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,))

        await db.commit()

        # --- Lógica de Auto-Blacklist ---
        try:
            # El auto-blacklist ahora se gestiona por gremio correctamente
            for guild_id in [gr[0] for gr in guild_rows]:
                cursor = await db.execute(
                    "SELECT members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?",
                    (guild_id,)
                )
                unnamed_row = await cursor.fetchone()
                    
                if unnamed_row:
                    import json
                    import datetime as dt

                    unnamed_members = {m.lower() for m in json.loads(unnamed_row["members_json"])}

                    blacklisted = set()
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

                            if (
                                t_name.lower() not in unnamed_members
                                and t_name.lower() not in blacklisted
                            ):
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
                                    pass  # Continuamos (posible ignorado)

                    if new_blacklist_count > 0:
                        await db.commit()
                        # Aviso al cog Warfare (que escucha el evento y refresca).
                        self.bot.dispatch(bus.BLACKLIST_UPDATED, guild_id)
        except Exception as e:
            logger.error(f"[K4Ultra] Auto-blacklist check failed: {e}")

        # --- Actualización de Dashboards K4Ultra ---
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, guild_id, channel_id, message_id, mode FROM k4ultra_messages"
        )
        rows = await cursor.fetchall()

        if rows:
            messages_to_remove = []

            for row in rows:
                row_id = row["id"]
                guild_id = row["guild_id"]
                channel_id = row["channel_id"]
                message_id = row["message_id"]
                mode = row["mode"] if "mode" in row.keys() else "radar"

                pages, top_players, k4_aliases = await self.generate_k4ultra_embed(guild_id, mode)

                try:
                    channel = self.bot.get_channel(
                        channel_id
                    ) or await self.bot.fetch_channel(channel_id)
                    if not channel:
                        messages_to_remove.append(row_id)
                        continue

                    message = await channel.fetch_message(message_id)

                    # Al actualizar los dashboards en segundo plano, forzamos la página 1 (índice 0)
                    # como solicita el usuario para evitar cuelgues de interfaz por despoblamiento de servidores.
                    use_page_index = 0
                    if mode == "tribus":
                        await message.edit(embed=pages[0], view=None)
                    else:
                        # Reconexión de la vista interactiva (View) del Embed
                        view = K4UltraView(self.bot, guild_id, top_players, k4_aliases, pages=pages, current_page=use_page_index, mode=mode)
                        await message.edit(embed=pages[use_page_index], view=view)
                except discord.NotFound:
                    messages_to_remove.append(row_id)
                except discord.Forbidden:
                    pass
                except discord.HTTPException as e:
                    logger.error(
                        f"[K4Ultra Debug] Error actualizando mensaje persistente {row_id}: {e}"
                    )
                except Exception as e:
                    logger.error(
                        f"[K4Ultra] Error actualizando mensaje persistente {row_id}: {e}"
                    )

            if messages_to_remove:
                for msg_id in messages_to_remove:
                    await db.execute(
                        "DELETE FROM k4ultra_messages WHERE id = ?", (msg_id,)
                    )
                await db.commit()

    @gather_player_data.error
    async def gather_player_data_error(self, error):
        logger.error(
            f"[K4Ultra] Error CRÍTICO en task gather_player_data: {error}",
            exc_info=True,
        )

    @tasks.loop(hours=24)
    async def calculate_relationships(self):
        """Calcula las relaciones cada 24 horas usando el sistema de puntos."""
        await self.bot.wait_until_ready()

        now = datetime.now()
        yesterday_start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_end = yesterday_start + timedelta(days=1)
        ys_str = yesterday_start.strftime("%Y-%m-%d %H:%M:%S")
        ye_str = yesterday_end.strftime("%Y-%m-%d %H:%M:%S")

        db = self.bot.db

        # Migración de shared_minutes delegada a db/schema.py.

        # --- Decaimiento diario de relaciones (5% por día) ---
        # Aplicar ANTES de calcular nuevos puntos para que relaciones inactivas pierdan fuerza
        await db.execute(
            "UPDATE k4ultra_relationships SET probability_score = CAST(probability_score * 0.95 AS INTEGER) WHERE is_manual = 0"
        )
        # Limpieza de relaciones residuales con puntuación insignificante
        await db.execute(
            "DELETE FROM k4ultra_relationships WHERE probability_score < 2 AND is_manual = 0"
        )

        # Extracción de todos los gremios configurados
        cursor = await db.execute("SELECT guild_id FROM guild_config")
        guild_rows = await cursor.fetchall()
            
        for g_row in guild_rows:
            guild_id = g_row["guild_id"]
                
            # Prevención de doble ejecución tras reinicios bruscos (Aislado por gremio)
            await db.execute(
                "CREATE TABLE IF NOT EXISTS k4ultra_config (guild_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (guild_id, key))"
            )
            cursor = await db.execute(
                "SELECT value FROM k4ultra_config WHERE key = 'last_calc_date' AND guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            today_str = now.strftime("%Y-%m-%d")
            if row and row["value"] == today_str:
                continue  # Cálculo previo del día finalizado con éxito para este gremio

            # Extracción de sesiones con actividad en la víspera ("Ayer") para este gremio
            cursor = await db.execute(
                "SELECT player_name, map_name, start_time, end_time FROM k4ultra_sessions WHERE start_time >= ? AND start_time < ? AND guild_id = ?",
                (ys_str, ye_str, guild_id),
            )
            sessions = await cursor.fetchall()
            if not sessions:
                continue

            points_to_add = {}
            shared_mins_to_add = {}

            def add_points(a, b, pts):
                if a > b:
                    a, b = b, a
                points_to_add[(a, b)] = points_to_add.get((a, b), 0) + pts

            def add_mins(a, b, m):
                if a > b:
                    a, b = b, a
                shared_mins_to_add[(a, b)] = shared_mins_to_add.get((a, b), 0) + m

            parsed_sessions = []
            for s in sessions:
                st = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
                # Restricción (cap) del end_time al día correspondiente si excede
                end_str = s["end_time"]
                if end_str > ye_str:
                    end_str = ye_str
                et = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
                parsed_sessions.append(
                    {"p": s["player_name"], "m": s["map_name"], "st": st, "et": et}
                )

            from collections import defaultdict

            player_sessions = defaultdict(list)
            for s in parsed_sessions:
                player_sessions[s["p"]].append(s)

            for p in player_sessions:
                player_sessions[p].sort(key=lambda x: x["st"])

            players = list(player_sessions.keys())

            for i in range(len(players)):
                for j in range(i + 1, len(players)):
                    p1 = players[i]
                    p2 = players[j]

                    s1_list = player_sessions[p1]
                    s2_list = player_sessions[p2]

                    # Regla A: Acumulación de minutos superpuestos (mismo mapa)
                    for s1 in s1_list:
                        for s2 in s2_list:
                            if s1["m"] == s2["m"]:
                                overlap_start = max(s1["st"], s2["st"])
                                overlap_end = min(s1["et"], s2["et"])
                                if overlap_end > overlap_start:
                                    mins = int(
                                        (overlap_end - overlap_start).total_seconds()
                                        / 60
                                    )
                                    add_mins(p1, p2, mins)

                    # Regla C: Sincronía en Login Y Logout (margen <= 3 mins, ambas condiciones)
                    login_sync = (
                        abs((s1_list[0]["st"] - s2_list[0]["st"]).total_seconds())
                        <= 180
                    )
                    logout_sync = (
                        abs((s1_list[-1]["et"] - s2_list[-1]["et"]).total_seconds())
                        <= 180
                    )
                    if login_sync and logout_sync:
                        add_points(p1, p2, 2)

                    # Regla B: Transferencias simultáneas (margen <= 5 mins)
                    for k1 in range(len(s1_list) - 1):
                        t1_end = s1_list[k1]["et"]
                        t1_map1 = s1_list[k1]["m"]
                        t1_start2 = s1_list[k1 + 1]["st"]
                        t1_map2 = s1_list[k1 + 1]["m"]

                        if (
                            t1_map1 != t1_map2
                        ):  # Confirmación de transferencia de mapa aislada
                            for k2 in range(len(s2_list) - 1):
                                t2_end = s2_list[k2]["et"]
                                t2_map1 = s2_list[k2]["m"]
                                t2_start2 = s2_list[k2 + 1]["st"]
                                t2_map2 = s2_list[k2 + 1]["m"]

                                if t2_map1 == t1_map1 and t2_map2 == t1_map2:
                                    if (
                                        abs((t1_end - t2_end).total_seconds()) <= 300
                                        and abs((t1_start2 - t2_start2).total_seconds())
                                        <= 300
                                    ):
                                        add_points(p1, p2, 5)

                # Volcado de puntuación de relaciones a SQL (Aislado por gremio)
                for (p1, p2), mins in shared_mins_to_add.items():
                    cursor = await db.execute(
                        "SELECT probability_score, shared_minutes, is_manual FROM k4ultra_relationships WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                        (p1, p2, guild_id),
                    )
                    row = await cursor.fetchone()
                    pts_to_add = points_to_add.get((p1, p2), 0)

                    if row:
                        old_mins = (
                            row["shared_minutes"] if "shared_minutes" in row.keys() else 0
                        )
                        new_mins = old_mins + mins
                        # Cálculo de puntos adicionales derivados de Regla A
                        pts_to_add += (new_mins // 180) - (old_mins // 180)

                        if row["is_manual"] == 0:
                            await db.execute(
                                "UPDATE k4ultra_relationships SET probability_score = probability_score + ?, shared_minutes = ? WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                                (pts_to_add, new_mins, p1, p2, guild_id),
                            )
                    else:
                        pts_to_add += mins // 180
                        if pts_to_add > 0:
                            await db.execute(
                                "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, shared_minutes, is_manual) VALUES (?, ?, ?, ?, ?, 0)",
                                (guild_id, p1, p2, pts_to_add, mins),
                            )

                # Aplicación de puntos exclusivos de Reglas B y C (sin Regla A combinada)
                for (p1, p2), pts in points_to_add.items():
                    if (p1, p2) not in shared_mins_to_add:
                        cursor = await db.execute(
                            "SELECT probability_score, is_manual FROM k4ultra_relationships WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                            (p1, p2, guild_id),
                        )
                        row = await cursor.fetchone()
                        if row:
                            if row["is_manual"] == 0:
                                await db.execute(
                                    "UPDATE k4ultra_relationships SET probability_score = probability_score + ? WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                                    (pts, p1, p2, guild_id),
                                )
                        else:
                            if pts > 0:
                                await db.execute(
                                    "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, shared_minutes, is_manual) VALUES (?, ?, ?, ?, 0, 0)",
                                    (guild_id, p1, p2, pts),
                                )

            # Marcar cálculo del día como finalizado para este gremio
            await db.execute(
                "INSERT OR REPLACE INTO k4ultra_config (guild_id, key, value) VALUES (?, 'last_calc_date', ?)",
                (guild_id, today_str),
            )
        # Limpieza mensual de registros crudos (Logs) para preservación de DB
        await db.execute(
            "DELETE FROM k4ultra_players_log WHERE timestamp < datetime('now', '-30 days')"
        )

        await db.commit()

        # Captura de Snapshot semanal (Lunes)
        if now.weekday() == 0:  # Lunes
            current_week = now.isocalendar()[1]
                
            # Fetch all guilds that have K4Ultra active (by checking playtime)
            cursor = await db.execute("SELECT DISTINCT guild_id FROM k4ultra_playtime")
            guilds = await cursor.fetchall()
                
            for guild_row in guilds:
                g_id = guild_row["guild_id"]
                cursor = await db.execute(
                    "SELECT id FROM k4ultra_snapshots WHERE week_number = ? AND guild_id = ?",
                    (current_week, g_id),
                )
                if not await cursor.fetchone():
                    # Generación de Embed para guardado en Snapshot
                    pages, _ , _a = await self.generate_k4ultra_embed(g_id)
                    embed = pages[0]
                    embed.title = (
                        f"🌐 Tracker de Jugadores K4Ultra - Semana {current_week}"
                    )
                    embed.description = "Registro inmutable de la semana."
                    embed.set_footer(
                        text=f"Guardado automáticamente: {now.strftime('%Y-%m-%d')}"
                    )

                    embed_json = json.dumps(embed.to_dict())
                    await db.execute(
                        "INSERT INTO k4ultra_snapshots (week_number, guild_id, embed_json) VALUES (?, ?, ?)",
                        (current_week, g_id, embed_json),
                    )
                    await db.commit()

    async def generate_k4ultra_embed(self, guild_id: int, mode: str = "radar") -> tuple[list, list, dict]:
        """Wrapper compatible. La implementación vive en ``cogs.k4ultra.embeds``."""
        from cogs.k4ultra.embeds import generate_k4ultra_embed

        return await generate_k4ultra_embed(self.bot, guild_id, mode)


    @app_commands.command(
        name="k4ultra",
        description="Muestra información detallada de jugadores, tiempos y relaciones.",
    )
    @app_commands.describe(
        semana="Opcional. Número de semana para ver el histórico de esa semana.",
        modo="Opcional. Selecciona si ver radar o tribus (por defecto radar)."
    )
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="Radar y Ranking", value="radar"),
            app_commands.Choice(name="Explorador de Tribus", value="tribus")
        ]
    )
    async def k4ultra_command(
        self, interaction: discord.Interaction, semana: int = None, modo: str = "radar"
    ):

        # Validación de permisos (Admin o ID autorizado)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.**", ephemeral=True
            )
            return

        if semana:
            # Consulta de Snapshot histórico
            await interaction.response.defer(ephemeral=True)
            db = self.bot.db
            cursor = await db.execute(
                "SELECT embed_json FROM k4ultra_snapshots WHERE week_number = ? AND guild_id = ?",
                (semana, interaction.guild_id),
            )
            row = await cursor.fetchone()

            if row:
                embed_dict = json.loads(row[0])
                snap_embed = discord.Embed.from_dict(embed_dict)
                await interaction.followup.send(embed=snap_embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ No se encontró un snapshot para la semana {semana}.",
                    ephemeral=True,
                )
        else:
            # Visualización de estadísticas en vivo y guardado como mensaje persistente
            await interaction.response.defer(ephemeral=False)
            pages, top_players, k4_aliases = await self.generate_k4ultra_embed(interaction.guild_id, modo)
            view = K4UltraView(self.bot, interaction.guild_id, top_players, k4_aliases, pages=pages) if modo != "tribus" else None

            try:
                if view:
                    message = await interaction.followup.send(embed=pages[0], view=view)
                else:
                    message = await interaction.followup.send(embed=pages[0])
            except discord.HTTPException as e:
                logger.error(f"[K4Ultra Debug] HTTPException on send: {e}")
                logger.error(f"[K4Ultra Debug] Embed payload: {pages[0].to_dict()}")
                raise e

            db = self.bot.db
            await db.execute(
                """
                INSERT INTO k4ultra_messages (guild_id, channel_id, message_id, mode)
                VALUES (?, ?, ?, ?)
            """,
                (interaction.guild_id, interaction.channel_id, message.id, modo),
            )
            await db.commit()

    @app_commands.command(
        name="k4ultra_cleanup",
        description="[Admin] Limpia y fusiona perfiles duplicados (_1, _2) con su nombre base.",
    )
    async def k4ultra_cleanup(self, interaction: discord.Interaction):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Búsqueda de jugadores con sufijos numéricos (ej. _1, _2)
        import re

        cursor = await db.execute(
            "SELECT DISTINCT player_name FROM k4ultra_playtime WHERE guild_id = ?",
            (interaction.guild_id,)
        )
        all_players = [r["player_name"] for r in await cursor.fetchall()]

        # Identificación de nombres base y copias asociadas
        duplicates_to_merge = []
        generic_names = {"123", "human", "humano", "survivor", "player", "bob"}

        for p in all_players:
            match = re.search(r"^(.*)_(\d+)$", p)
            if match:
                base_name = match.group(1)
                # Exclusión de nombres genéricos en la fusión (comparten base de forma legítima)
                if base_name.lower() not in generic_names:
                    duplicates_to_merge.append((p, base_name))

        if not duplicates_to_merge:
            await interaction.followup.send(
                "✅ No se encontraron perfiles duplicados para fusionar.",
                ephemeral=True,
            )
            return

        merged_count = 0
        for dup_name, base_name in duplicates_to_merge:
            # 1. Fusión de Playtime (Minutos jugados)
            cursor = await db.execute(
                "SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
                (dup_name, interaction.guild_id),
            )
            dup_maps = await cursor.fetchall()

            for dm in dup_maps:
                # Comprobación de existencia de Playtime previo para el nombre base en ese mapa
                c2 = await db.execute(
                    "SELECT total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (base_name, dm["map_name"], interaction.guild_id),
                )
                base_map = await c2.fetchone()

                if base_map:
                    # Suma de minutos reteniendo la última conexión ("last_seen")
                    new_mins = base_map["total_minutes"] + dm["total_minutes"]
                    new_last_seen = max(base_map["last_seen"], dm["last_seen"])
                    await db.execute(
                        "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = ? WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                        (new_mins, new_last_seen, base_name, dm["map_name"], interaction.guild_id),
                    )
                else:
                    # Inserción de registro nuevo bajo el nombre base
                    await db.execute(
                        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                        (
                            interaction.guild_id,
                            base_name,
                            dm["map_name"],
                            dm["total_minutes"],
                            dm["last_seen"],
                        ),
                    )

            await db.execute(
                "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (dup_name, interaction.guild_id)
            )

            # 2. Actualización de Sesiones
            await db.execute(
                "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            # 3. Actualización de Relaciones
            # Modificación cuidadosa de pares para evitar pérdida de datos
            await db.execute(
                "UPDATE k4ultra_relationships SET player1 = ? WHERE player1 = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )
            await db.execute(
                "UPDATE k4ultra_relationships SET player2 = ? WHERE player2 = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            # Limpieza de auto-relaciones generadas por la fusión
            await db.execute(
                "DELETE FROM k4ultra_relationships WHERE player1 = player2 AND guild_id = ?",
                (interaction.guild_id,)
            )

            # 4. Limpieza en Blacklist y Alias
            await db.execute("DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (dup_name, interaction.guild_id))
            await db.execute(
                "DELETE FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?", (dup_name, interaction.guild_id)
            )
            await db.execute(
                "UPDATE k4ultra_players_log SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            merged_count += 1

        await db.commit()

        await interaction.followup.send(
            f"✅ Limpieza completada. Se han fusionado **{merged_count}** perfiles duplicados con sus nombres base.",
            ephemeral=True,
        )

    @app_commands.command(
        name="fijar_tribu",
        description="[Admin] Fija una tribu para que el algoritmo no añada jugadores externos.",
    )
    @app_commands.describe(
        nombre="Nombre de la tribu",
        jugadores="Nombres de los jugadores separados por coma",
        propia="Opcional. Marca True si esta es tu tribu (aparecerá destacada)."
    )
    async def fijar_tribu(
        self, interaction: discord.Interaction, nombre: str, jugadores: str, propia: bool = False
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        # Saneamiento de comillas accidentales y espacios
        nombre = nombre.strip().strip("'\"")
        miembros = [
            m.strip().strip("'\"")
            for m in jugadores.split(",")
            if m.strip().strip("'\"")
        ]

        if len(miembros) < 2:
            await interaction.response.send_message(
                "❌ Debes especificar al menos 2 jugadores válidos separados por comas.",
                ephemeral=True,
            )
            return

        db = self.bot.db
        import json

        is_own = 1 if propia else 0
        if is_own == 1:
            # Quitar is_own a todas las de la guild para que solo haya 1 propia
            await db.execute("UPDATE k4ultra_fixed_tribes SET is_own = 0 WHERE guild_id = ?", (interaction.guild_id,))

        await db.execute(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, nombre, json.dumps(miembros), is_own),
        )
        await db.commit()

        tag_propia = "\n🌟 Ha sido marcada como TU TRIBU PROPIA." if propia else ""
        await interaction.response.send_message(
            f"✅ Tribu fijada: **{nombre}** con los jugadores: {', '.join(miembros)}.\nEl algoritmo no añadirá jugadores externos a este bloque.{tag_propia}",
            ephemeral=True,
        )

    tribu_propia_group = app_commands.Group(
        name="tribu_propia",
        description="Gestión de la tribu principal del servidor.",
    )

    @tribu_propia_group.command(
        name="crear",
        description="[Admin] Crea y establece la tribu propia predeterminada.",
    )
    @app_commands.describe(
        nombre="Nombre de tu Tribu",
        jugadores="Jugadores de tu tribu (separados por comas)",
    )
    async def tribu_propia_crear(self, interaction: discord.Interaction, nombre: str, jugadores: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        nombre = nombre.strip().strip("'\"")
        miembros = [m.strip().strip("'\"") for m in jugadores.split(",") if m.strip().strip("'\"")]

        if len(miembros) < 2:
            await interaction.response.send_message(
                "❌ Debes especificar al menos 2 jugadores válidos separados por comas.", ephemeral=True
            )
            return

        db = self.bot.db
        import json
        # Desmarcar las anteriores para evitar conflictos
        await db.execute("UPDATE k4ultra_fixed_tribes SET is_own = 0 WHERE guild_id = ?", (interaction.guild_id,))
            
        # Buscamos si existía una con el mismo nombre para sobrescribirla limpiamente
        await db.execute("DELETE FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?", (nombre, interaction.guild_id))
            
        await db.execute(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, 1)",
            (interaction.guild_id, nombre, json.dumps(miembros)),
        )
        await db.commit()

        await interaction.response.send_message(
            f"✅ Se ha configurado **{nombre}** como tribu propia con los jugadores: {', '.join(miembros)}.",
            ephemeral=True,
        )

    @tribu_propia_group.command(
        name="modificar", description="[Admin] Modifica parámetros de la tribu propia."
    )
    @app_commands.describe(
        opcion="Qué tipo de modificación deseas aplicar",
        valor="El nuevo nombre o el miembro a alterar",
    )
    @app_commands.choices(
        opcion=[
            app_commands.Choice(name="Cambiar Nombre de Tribu", value="nombre"),
            app_commands.Choice(name="Añadir Miembro", value="add"),
            app_commands.Choice(name="Eliminar Miembro", value="remove"),
        ]
    )
    async def tribu_propia_modificar(
        self, interaction: discord.Interaction, opcion: app_commands.Choice[str], valor: str
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        valor = valor.strip().strip("'\"")

        db = self.bot.db
        import json
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name, members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?", (interaction.guild_id,))
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message("❌ No hay tribu propia configurada. Usa `/tribu_propia crear` primero.", ephemeral=True)
            return

        if opcion.value == "nombre":
            await db.execute("UPDATE k4ultra_fixed_tribes SET name = ? WHERE id = ?", (valor, row["id"]))
            await db.commit()
            await interaction.response.send_message(f"✅ Se cambió el nombre de la tribu propia a **{valor}**.", ephemeral=True)
            return
            
        miembros: list = json.loads(row["members_json"])
            
        if opcion.value == "add":
            if [m.lower() for m in miembros].count(valor.lower()) > 0:
                await interaction.response.send_message(f"⚠️ **{valor}** ya está en la tribu propia (**{row['name']}**).", ephemeral=True)
                return
            miembros.append(valor)
            await db.execute("UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?", (json.dumps(miembros), row["id"]))
            await db.commit()
            await interaction.response.send_message(f"✅ Se añadió a **{valor}** a la tribu propia (**{row['name']}**).", ephemeral=True)

        elif opcion.value == "remove":
            original_len = len(miembros)
            miembros = [m for m in miembros if m.lower() != valor.lower()]
            if len(miembros) == original_len:
                await interaction.response.send_message(f"❌ **{valor}** no fue encontrado en la tribu propia (**{row['name']}**).", ephemeral=True)
                return
            await db.execute("UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?", (json.dumps(miembros), row["id"]))
            await db.commit()
            await interaction.response.send_message(f"✅ Se eliminó a **{valor}** de la tribu propia (**{row['name']}**).", ephemeral=True)

    @tribu_propia_group.command(
        name="borrar", description="[Admin] Elimina la tribu propia del registro."
    )
    @app_commands.describe(seguro="True si estás seguro de que deseas borrarla por completo.")
    async def tribu_propia_borrar(self, interaction: discord.Interaction, seguro: bool):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        if not seguro:
            await interaction.response.send_message("❌ Debes seleccionar `seguro: True` para borrar la tribu propia definitivamente.", ephemeral=True)
            return

        db = self.bot.db
        cursor = await db.execute("DELETE FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?", (interaction.guild_id,))
        if cursor.rowcount == 0:
            await interaction.response.send_message("❌ No hay tribu propia registrada actualmente.", ephemeral=True)
            return
        await db.commit()

        await interaction.response.send_message("✅ Has borrado permanentemente la tribu propia del servidor.", ephemeral=True)


    @app_commands.command(
        name="unfijar_tribu",
        description="[Admin] Elimina una tribu fijada por su nombre exacto.",
    )
    @app_commands.describe(nombre="Nombre exacto de la tribu a eliminar")
    async def unfijar_tribu(self, interaction: discord.Interaction, nombre: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        nombre = nombre.strip()

        db = self.bot.db
        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?", (nombre, interaction.guild_id)
        )
        deleted = cursor.rowcount
        await db.commit()

        if deleted > 0:
            await interaction.response.send_message(
                f"✅ Tribu **{nombre}** ha sido eliminada de las fijadas. Sus miembros volverán a agruparse automáticamente.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ninguna tribu fijada con el nombre **{nombre}**.",
                ephemeral=True,
            )


    @app_commands.command(
        name="k4ultra_merge",
        description="[Admin] Fusiona MANUALMENTE un perfil duplicado (origen) hacia un perfil base (destino).",
    )
    @app_commands.describe(
        origen="Perfil a eliminar y fusionar (ej: 123_1)",
        destino="Perfil base que absorberá las horas (ej: 123)",
    )
    async def k4ultra_merge(
        self, interaction: discord.Interaction, origen: str, destino: str
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        origen = origen.strip()
        destino = destino.strip()

        if origen == destino:
            await interaction.response.send_message(
                "❌ El origen y el destino no pueden ser el mismo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Verificación de existencia del perfil de origen
        cursor = await db.execute(
            "SELECT * FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (origen, interaction.guild_id),
        )
        origen_maps = await cursor.fetchall()
        if not origen_maps:
            await interaction.followup.send(
                f"❌ El jugador origen **{origen}** no tiene registros de tiempo, o no existe.",
                ephemeral=True,
            )
            return

        # 1. Merge Playtime
        for dm in origen_maps:
            c2 = await db.execute(
                "SELECT total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                (destino, dm["map_name"], interaction.guild_id),
            )
            base_map = await c2.fetchone()

            if base_map:
                new_mins = base_map["total_minutes"] + dm["total_minutes"]
                new_last_seen = max(base_map["last_seen"], dm["last_seen"])
                await db.execute(
                    "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = ? WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (new_mins, new_last_seen, destino, dm["map_name"], interaction.guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (interaction.guild_id, destino, dm["map_name"], dm["total_minutes"], dm["last_seen"]),
                )

        await db.execute(
            "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (origen, interaction.guild_id)
        )

        # 2. Update Sessions
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )

        # 3. Update Relationships
        await db.execute(
            "UPDATE k4ultra_relationships SET player1 = ? WHERE player1 = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )
        await db.execute(
            "UPDATE k4ultra_relationships SET player2 = ? WHERE player2 = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )
        await db.execute(
            "DELETE FROM k4ultra_relationships WHERE player1 = player2 AND guild_id = ?",
            (interaction.guild_id,)
        )

        # 4. Cleanup Blacklist and Aliases
        await db.execute("DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (origen, interaction.guild_id))
        await db.execute(
            "DELETE FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?", (origen, interaction.guild_id)
        )
        await db.execute(
            "UPDATE k4ultra_players_log SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )

        await db.commit()

        await interaction.followup.send(
            f"✅ ¡Fusión manual completada con éxito!\nTodas las horas e información de **{origen}** han sido traspasadas a **{destino}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="k4ultra_split",
        description="[Admin] Separa la SESIÓN ACTUAL de un jugador (origen) hacia un nuevo perfil (destino).",
    )
    @app_commands.describe(
        origen="Jugador que está conectado AHORA (ej: 123_1)",
        destino="Nuevo perfil donde moverlo (ej: 123_2)",
    )
    async def k4ultra_split(
        self, interaction: discord.Interaction, origen: str, destino: str
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        origen = origen.strip()
        destino = destino.strip()

        if origen == destino:
            await interaction.response.send_message(
                "❌ El origen y el destino no pueden ser el mismo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Comprobación de existencia de sesión activa para el perfil de origen
        cursor = await db.execute(
            "SELECT id, map_name FROM k4ultra_sessions WHERE player_name = ? AND is_active = 1 AND guild_id = ?",
            (origen, interaction.guild_id),
        )
        active_sessions = await cursor.fetchall()

        if not active_sessions:
            await interaction.followup.send(
                f"❌ El jugador **{origen}** NO tiene ninguna sesión activa en este momento. Este comando solo sirve para separar a un impostor mientras está conectado.",
                ephemeral=True,
            )
            return

        if len(active_sessions) > 1:
            await interaction.followup.send(
                f"⚠️ **{origen}** tiene múltiples sesiones activas extrañas. Contacta al soporte técnico.",
                ephemeral=True,
            )
            return

        session_id = active_sessions[0]["id"]
        map_name = active_sessions[0]["map_name"]

        # 1. Modificación de identidad en la sesión activa
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE id = ? AND guild_id = ?",
            (destino, session_id, interaction.guild_id),
        )

        # 2. Garantía de existencia del destino en Playtime (prevención de errores visuales)
        cursor = await db.execute(
            "SELECT total_minutes FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
            (destino, map_name, interaction.guild_id),
        )
        if not await cursor.fetchone():
            import datetime as dt

            now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, 0, ?)",
                (interaction.guild_id, destino, map_name, now_str),
            )

        await db.commit()

        await interaction.followup.send(
            f"✅ ¡Sesión separada!\nEl impostor que estaba usando **{origen}** ahora es rastreado como **{destino}**.\nLa sesión actual ya ha sido purgada del historial de **{origen}**.",
            ephemeral=True,
        )


async def setup(bot):
    # La tabla player_identities_link se crea en db/schema.py (init_db).
    await bot.add_cog(K4Ultra(bot))
