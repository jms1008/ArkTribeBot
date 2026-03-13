import discord
from discord.ext import commands, tasks
from discord import app_commands
import a2s
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger("ArkTribeBot")

# Reutilización de constantes y dependencias de server_status


class AddRelationshipModal(discord.ui.Modal, title="Añadir Relación"):
    jugador1 = discord.ui.TextInput(
        label="Jugador 1", placeholder="Nombre exacto del jugador 1...", max_length=100
    )
    jugador2 = discord.ui.TextInput(
        label="Jugador 2", placeholder="Nombre exacto del jugador 2...", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        p1 = self.jugador1.value.strip()
        p2 = self.jugador2.value.strip()

        # Normalización de orden alfabético
        if p1 > p2:
            p1, p2 = p2, p1

        async with aiosqlite.connect(self.bot.db_name) as db:
            # Verificación de existencia previa
            cursor = await db.execute(
                "SELECT id FROM k4ultra_relationships WHERE player1 = ? AND player2 = ?",
                (p1, p2),
            )
            if await cursor.fetchone():
                await db.execute(
                    "UPDATE k4ultra_relationships SET is_manual = 1, probability_score = 100 WHERE player1 = ? AND player2 = ?",
                    (p1, p2),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_relationships (player1, player2, probability_score, is_manual) VALUES (?, ?, 100, 1)",
                    (p1, p2),
                )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Relación manual añadida entre **{p1}** y **{p2}**.", ephemeral=True
        )


class RemoveRelationshipModal(discord.ui.Modal, title="Eliminar Relación"):
    jugador1 = discord.ui.TextInput(
        label="Jugador 1", placeholder="Nombre exacto del jugador 1...", max_length=100
    )
    jugador2 = discord.ui.TextInput(
        label="Jugador 2", placeholder="Nombre exacto del jugador 2...", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        p1 = self.jugador1.value.strip()
        p2 = self.jugador2.value.strip()

        # Normalización de orden alfabético
        if p1 > p2:
            p1, p2 = p2, p1

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM k4ultra_relationships WHERE player1 = ? AND player2 = ?",
                (p1, p2),
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Relación eliminada entre **{p1}** y **{p2}**.", ephemeral=True
        )


class RenameTribeModal(discord.ui.Modal, title="Asignar Nombre a Tribu"):
    miembro_ref = discord.ui.TextInput(
        label="Miembro de Referencia",
        placeholder="Nombre exacto de un jugador de la tribu...",
        max_length=100,
    )
    nuevo_nombre = discord.ui.TextInput(
        label="Nuevo Nombre", placeholder="Ej: Los Alfas", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        miembro = self.miembro_ref.value.strip()
        nuevo_nombre = self.nuevo_nombre.value.strip()

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            # Identificación de tribu mediante miembro de referencia
            # Almacenamiento regla de renombrado (basada en el grafo de relaciones subyacente)
            # Método de asignación de nombre personalizado

            cursor = await db.execute(
                "SELECT id FROM k4ultra_tribe_names WHERE tribe_signature = ?",
                (miembro,),
            )
            if await cursor.fetchone():
                await db.execute(
                    "UPDATE k4ultra_tribe_names SET custom_name = ? WHERE tribe_signature = ?",
                    (nuevo_nombre, miembro),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_tribe_names (tribe_signature, custom_name) VALUES (?, ?)",
                    (miembro, nuevo_nombre),
                )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Tribu de **{miembro}** renombrada a **{nuevo_nombre}**. Se aplicará en el próximo refresco.",
            ephemeral=True,
        )


class PlayerSelectMenu(discord.ui.Select):
    def __init__(self, bot, guild_id: int, players):
        self.bot = bot
        self.guild_id = guild_id
        options = []
        for i, p in enumerate(players[:25]):
            options.append(
                discord.SelectOption(
                    label=p, description="Ver detalles y horarios", value=p
                )
            )
        if not options:
            options.append(discord.SelectOption(label="Sin datos", value="none"))
        super().__init__(
            custom_id="k4ultra_player_select",
            placeholder="Selecciona un jugador para ver su perfil detallado...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player_name = self.values[0]
        if player_name == "none":
            await interaction.followup.send("No hay datos.", ephemeral=True)
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT map_name, sum(total_minutes) as m FROM k4ultra_playtime WHERE player_name = ? GROUP BY map_name ORDER BY m DESC",
                (player_name,),
            )
            maps = await cursor.fetchall()

            total_mins = sum(m["m"] for m in maps) if maps else 0
            if total_mins == 0:
                await interaction.followup.send(
                    "No hay datos suficientes de este jugador.", ephemeral=True
                )
                return

            main_map = maps[0]["map_name"]

            cursor = await db.execute(
                "SELECT start_time FROM k4ultra_sessions WHERE player_name = ?",
                (player_name,),
            )
            sessions = await cursor.fetchall()

            hours_played = {i: 0 for i in range(24)}
            for s in sessions:
                try:
                    st = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
                    hours_played[st.hour] += 1
                except Exception:
                    pass

            best_hour = max(hours_played, key=hours_played.get) if sessions else "N/A"

            embed = discord.Embed(
                title=f"👤 Perfil Detallado: {player_name}", color=discord.Color.blue()
            )

            # Adición de alias (si consta en el registro)
            try:
                cursor = await db.execute(
                    "SELECT alias FROM k4ultra_aliases WHERE player_name = ?",
                    (player_name,),
                )
                alias_row = await cursor.fetchone()
                if alias_row:
                    embed.title += f" [{alias_row['alias']}]"
            except aiosqlite.OperationalError:
                pass

            # Búsqueda de Estado Online Actual
            try:
                cursor = await db.execute(
                    "SELECT map_name FROM k4ultra_sessions WHERE player_name = ? AND is_active = 1 LIMIT 1",
                    (player_name,)
                )
                online_row = await cursor.fetchone()
                if online_row:
                    embed.description = f"🟢 **Online Ahora** (Jugando en {online_row['map_name']})"
                else:
                    embed.description = "🔴 **Offline**"
            except aiosqlite.OperationalError:
                embed.description = "🔴 **Offline**"

            # Formateo de tiempos básicos
            hours = total_mins // 60
            mins = total_mins % 60
            
            # Búsqueda de "Primera vez visto"
            first_seen_str = "Desconocido"
            if sessions:
                try:
                    first_date = min([datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S") for s in sessions if s["start_time"]])
                    first_seen_str = first_date.strftime("%d/%m/%Y")
                except Exception:
                    pass

            embed.add_field(
                name="⏱️ Tiempo Total", value=f"{hours}h {mins}m", inline=True
            )
            embed.add_field(name="🗺️ Main Map", value=f"{main_map}", inline=True)
            embed.add_field(
                name="⏰ Hora Frecuente", value=f"{best_hour}:00", inline=True
            )
            
            # Adición de KDA y Stats PvP
            try:
                cursor = await db.execute(
                    "SELECT kills, deaths FROM tribe_kda WHERE player_name = ? AND guild_id = ?",
                    (player_name, self.guild_id)
                )
                kda_row = await cursor.fetchone()
                if kda_row:
                    kills = kda_row["kills"]
                    deaths = kda_row["deaths"]
                    ratio = round(kills / deaths, 2) if deaths > 0 else kills
                    embed.add_field(
                        name="⚔️ Historial PvP", 
                        value=f"**Kills:** {kills} | **Deaths:** {deaths}\n**K/D Ratio:** {ratio}", 
                        inline=False
                    )
            except aiosqlite.OperationalError:
                pass
            
            # Adición de Personajes (Alts) conocidos
            try:
                cursor = await db.execute(
                    "SELECT character_name FROM tribe_characters WHERE player_name = ? AND guild_id = ?",
                    (player_name, self.guild_id)
                )
                char_rows = await cursor.fetchall()
                if char_rows:
                    chars = ", ".join([f"`{c['character_name']}`" for c in char_rows])
                    embed.add_field(
                        name="🧑‍🤝‍🧑 Personajes Conocidos", 
                        value=chars, 
                        inline=False
                    )
            except aiosqlite.OperationalError:
                pass

            # Extracción de datos de Blacklist manual
            try:
                cursor = await db.execute(
                    "SELECT tribe, notes FROM blacklist WHERE player = ? AND guild_id = ?",
                    (player_name, self.guild_id),
                )
                bl_row = await cursor.fetchone()
                if bl_row:
                    embed.add_field(
                        name="🏠 Tribu (Manual)",
                        value=f"**{bl_row['tribe']}**",
                        inline=True,
                    )
                    embed.add_field(
                        name="📓 Extra (Notas)",
                        value=bl_row["notes"] or "Ninguna",
                        inline=True,
                    )
            except aiosqlite.OperationalError:
                pass
                
            embed.set_footer(text=f"Primera vez visto: {first_seen_str}")

            map_str = ""
            for m in maps:
                pct = int((m["m"] / total_mins) * 100)
                map_str += f"**{m['map_name'][:4].upper()}** ({pct}%)\n"

            if len(map_str) > 1024:
                map_str = map_str[:1020] + "..."

            embed.add_field(
                name="Distribución de Servidores",
                value=map_str or "No data",
                inline=False,
            )

            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                logger.error(f"[K4Ultra] Error sending dropdown profile: {e}")


class K4UltraView(discord.ui.View):
    def __init__(self, bot, guild_id: int, top_players=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        if top_players is None:
            top_players = []
        self.add_item(PlayerSelectMenu(bot, guild_id, top_players))

    @discord.ui.button(
        label="Añadir Relación",
        style=discord.ButtonStyle.primary,
        emoji="➕",
        custom_id="k4ultra_add_rel",
        row=1,
    )
    async def add_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(AddRelationshipModal(self.bot))

    @discord.ui.button(
        label="Eliminar Relación",
        style=discord.ButtonStyle.danger,
        emoji="➖",
        custom_id="k4ultra_rem_rel",
        row=1,
    )
    async def rem_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(RemoveRelationshipModal(self.bot))

    @discord.ui.button(
        label="Renombrar Tribu",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id="k4ultra_ren_rel",
        row=1,
    )
    async def ren_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(RenameTribeModal(self.bot))


class K4Ultra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gather_player_data.start()
        self.calculate_relationships.start()

    def cog_unload(self):
        self.gather_player_data.cancel()
        self.calculate_relationships.cancel()

    async def fetch_server_players(self, guild_id, map_name, ip, port):
        """Obtiene jugadores mediante A2S, devolviendo nombres válidos y duraciones de sesión."""
        address = (ip, port)
        valid_players = []
        try:
            players = await asyncio.wait_for(
                asyncio.to_thread(a2s.players, address), timeout=5.0
            )
            for p in players:
                # Omisión de jugadores sin nombre (perfiles ocultos Steam/Epic)
                if not p.name:
                    continue
                valid_players.append({"name": p.name.strip(), "duration": p.duration})
            return guild_id, map_name, valid_players
        except Exception as e:
            logger.debug(f"[K4Ultra] Error fetching from {map_name} (Guild {guild_id}): {e}")
            return guild_id, map_name, []

    @tasks.loop(minutes=5)
    async def gather_player_data(self):
        """Tarea en segundo plano que recopila datos de los jugadores cada 5 minutos."""
        await self.bot.wait_until_ready()

        # Recorrido de todos los Guilds configurados para obtener sus servidores
        from cogs.server_status import get_guild_servers

        async with aiosqlite.connect(self.bot.db_name) as _cfg_db:
            cfg_cursor = await _cfg_db.execute("SELECT guild_id FROM guild_config")
            guild_rows = await cfg_cursor.fetchall()

        all_guild_servers = []
        for (guild_id,) in guild_rows:
            g_servers = await get_guild_servers(self.bot, guild_id)
            for name, (ip, port) in g_servers.items():
                all_guild_servers.append((guild_id, name, ip, port))

        tasks_list = [
            self.fetch_server_players(gid, name, ip, port)
            for gid, name, ip, port in all_guild_servers
        ]
        results = await asyncio.gather(*tasks_list)

        now = datetime.now()

        all_fetched = []
        for guild_id, map_name, players in results:
            for p in players:
                all_fetched.append({"guild_id": guild_id, "map": map_name, "raw_name": p["name"]})

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT id, player_name, map_name, guild_id, start_time, end_time FROM k4ultra_sessions WHERE is_active = 1"
            )
            active_pool = [dict(s) for s in await cursor.fetchall()]

            ten_mins_ago = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute(
                "SELECT id, player_name, map_name, guild_id, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND end_time >= ? ORDER BY end_time DESC",
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
                                "UPDATE k4ultra_sessions SET end_time = ? WHERE id = ?",
                                (now.strftime("%Y-%m-%d %H:%M:%S"), sid),
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
                        "SELECT id, player_name, map_name, guild_id, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND player_name LIKE ? AND guild_id = ? ORDER BY end_time DESC",
                        (f"{raw_name}_%", fp["guild_id"]),
                    )
                    # Inclusión del propio nombre base si constaba inactivo
                    cursor2 = await db.execute(
                        "SELECT id, player_name, map_name, guild_id, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND player_name = ? AND guild_id = ? ORDER BY end_time DESC",
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

                    # Ordenación descendente por tiempo límite para reutilización
                    generic_inactive.sort(key=lambda x: x["end_time"], reverse=True)

                    # Priorización del nombre base sobre los variantes ante colisiones
                    # Ordenación secundaria por menor longitud
                    generic_inactive.sort(
                        key=lambda x: (x["end_time"], -len(x["player_name"])),
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
                            "INSERT INTO k4ultra_sessions (player_name, map_name, guild_id, start_time, end_time, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                            (
                                true_identity,
                                map_m,
                                fp["guild_id"],
                                now.strftime("%Y-%m-%d %H:%M:%S"),
                                now.strftime("%Y-%m-%d %H:%M:%S"),
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
                        "INSERT INTO k4ultra_sessions (player_name, map_name, guild_id, start_time, end_time, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                        (
                            true_identity,
                            map_m,
                            fp["guild_id"],
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                            now.strftime("%Y-%m-%d %H:%M:%S"),
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


            # Marcado de inactividad de sesiones cerradas
            for sid, s in active_pool_dict.items():
                if sid not in seen_identities and sid in [
                    a["id"] for a in active_pool
                ]:  # Cierre exclusivo de sesiones previamente activas
                    await db.execute(
                        "UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,)
                    )

            await db.commit()

            # --- Lógica de Auto-Blacklist ---
            try:
                # El auto-blacklist ahora se gestiona por gremio correctamente
                for guild_id in [gr[0] for gr in guild_rows]:
                    cursor = await db.execute(
                        "SELECT members_json FROM k4ultra_fixed_tribes WHERE name = 'UNNAMED' AND guild_id = ?",
                        (guild_id,)
                    )
                    unnamed_row = await cursor.fetchone()
                if unnamed_row:
                    import json

                    unnamed_members = set(json.loads(unnamed_row["members_json"]))

                    blacklisted = set()
                    try:
                        cursor = await db.execute("SELECT player FROM blacklist WHERE guild_id = ?", (guild_id,))
                        blacklisted = {r["player"] for r in await cursor.fetchall()}
                    except aiosqlite.OperationalError:
                        pass

                    new_blacklist_count = 0
                    import datetime as dt

                    created_at = dt.date.today().isoformat()

                    for sid in seen_identities:
                        if sid in active_pool_dict:
                            s_info = active_pool_dict[sid]
                            if s_info["guild_id"] != guild_id:
                                continue
                                
                            t_name = s_info["player_name"]
                            t_map = s_info["map_name"]

                            if (
                                t_name not in unnamed_members
                                and t_name not in blacklisted
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
                                    blacklisted.add(t_name)
                                    new_blacklist_count += 1
                                except aiosqlite.OperationalError:
                                    pass  # Continuamos (posible ignorado)

                    if new_blacklist_count > 0:
                        await db.commit()
                        try:
                            from cogs.warfare import update_blacklist_dashboards
                            # Actualizamos los dashboards de todos los gremios afectados
                            cursor = await db.execute("SELECT DISTINCT guild_id FROM guild_config")
                            guild_rows = await cursor.fetchall()
                            for g_row in guild_rows:
                                await update_blacklist_dashboards(self.bot, g_row["guild_id"])
                        except Exception as e:
                            logger.error(
                                f"[K4Ultra] Error updating blacklist dashboards: {e}"
                            )
            except Exception as e:
                logger.error(f"[K4Ultra] Auto-blacklist check failed: {e}")

            # --- Actualización de Dashboards K4Ultra ---
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, guild_id, channel_id, message_id FROM k4ultra_messages"
            )
            rows = await cursor.fetchall()

            if rows:
                messages_to_remove = []

                for row in rows:
                    row_id = row["id"]
                    guild_id = row["guild_id"]
                    channel_id = row["channel_id"]
                    message_id = row["message_id"]

                    new_embed, top_players = await self.generate_k4ultra_embed(guild_id)

                    try:
                        channel = self.bot.get_channel(
                            channel_id
                        ) or await self.bot.fetch_channel(channel_id)
                        if not channel:
                            messages_to_remove.append(row_id)
                            continue

                        message = await channel.fetch_message(message_id)

                        # Reconexión de la vista interactiva (View) del Embed
                        view = K4UltraView(self.bot, guild_id, top_players)
                        await message.edit(embed=new_embed, view=view)
                    except discord.NotFound:
                        messages_to_remove.append(row_id)
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException as e:
                        logger.error(
                            f"[K4Ultra Debug] Error actualizando mensaje persistente {row_id}: {e}"
                        )
                        logger.error(
                            f"[K4Ultra Debug] Payload failed: {new_embed.to_dict()}"
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

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

            # Prevención de doble ejecución tras reinicios bruscos
            await db.execute(
                "CREATE TABLE IF NOT EXISTS k4ultra_config (key TEXT PRIMARY KEY, value TEXT)"
            )
            cursor = await db.execute(
                "SELECT value FROM k4ultra_config WHERE key = 'last_calc_date'"
            )
            row = await cursor.fetchone()
            today_str = now.strftime("%Y-%m-%d")
            if row and row["value"] == today_str:
                return  # Cálculo previo del día finalizado con éxito
            await db.execute(
                "INSERT OR REPLACE INTO k4ultra_config (key, value) VALUES ('last_calc_date', ?)",
                (today_str,),
            )

            # Preparación de la columna extra de minutos compartidos (Migración DB)
            try:
                await db.execute(
                    "ALTER TABLE k4ultra_relationships ADD COLUMN shared_minutes INTEGER DEFAULT 0"
                )
            except Exception:
                pass

            # Extracción de todos los gremios configurados
            cursor = await db.execute("SELECT guild_id FROM guild_config")
            guild_rows = await cursor.fetchall()
            
            for g_row in guild_rows:
                guild_id = g_row["guild_id"]
                
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

                    # Regla C: Sincronía en Login/Logout (margen <= 10 mins)
                    if (
                        abs((s1_list[0]["st"] - s2_list[0]["st"]).total_seconds())
                        <= 600
                    ):
                        add_points(p1, p2, 2)
                    if (
                        abs((s1_list[-1]["et"] - s2_list[-1]["et"]).total_seconds())
                        <= 600
                    ):
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
                        embed, _ = await self.generate_k4ultra_embed(g_id)
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

    async def generate_k4ultra_embed(self, guild_id: int) -> tuple[discord.Embed, list]:
        embed = discord.Embed(
            title="🌐 Tracker de Jugadores K4Ultra", color=discord.Color.purple()
        )
        top_player_names = []

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT player_name, map_name, total_minutes
                FROM k4ultra_playtime
                WHERE guild_id = ?
            """, (guild_id,))
            all_playtimes = await cursor.fetchall()

            from collections import defaultdict

            p_totals = defaultdict(int)
            p_maps = defaultdict(list)
            for row in all_playtimes:
                p_totals[row["player_name"]] += row["total_minutes"]
                p_maps[row["player_name"]].append(
                    {"map": row["map_name"], "mins": row["total_minutes"]}
                )

            # Aplicación de Alias y Nombres de Tribu Personalizados
            # Moved further down the code, logic is fine.

            # Obtención de jugadores conectados en este instante para este servidor
            cursor = await db.execute(
                "SELECT player_name FROM k4ultra_sessions WHERE is_active = 1 AND guild_id = ?",
                (guild_id,)
            )
            active_sessions = await cursor.fetchall()
            active_players = {s["player_name"] for s in active_sessions}

            # Obtención de alias (funcionalidad base)

            sorted_players = sorted(p_totals.items(), key=lambda x: x[1], reverse=True)[
                :25
            ]

            players_text = ""
            for p_name, total_m in sorted_players:
                top_player_names.append(p_name)
                # Límite visual de 15 jugadores (25 para Select Menu interactivo)
                if len(top_player_names) <= 15:
                    h = total_m // 60
                    m = total_m % 60
                    time_str = f"{h}h {m}m" if h > 0 else f"{m}m"

                    maps_for_p = p_maps[p_name]
                    maps_for_p.sort(key=lambda x: x["mins"], reverse=True)

                    map_str_list = []

                    map_acronyms = {
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

                    for mm in maps_for_p:
                        pct = int((mm["mins"] / total_m) * 100) if total_m > 0 else 0
                        if pct > 0:
                            # Búsqueda de acrónimo en diccionario o formateo por defecto
                            raw_map = mm["map"]
                            acronym = map_acronyms.get(
                                raw_map, raw_map.replace(" ", "")[:4].capitalize()
                            )
                            map_str_list.append(f"*{pct}% {acronym}*")

                    map_joined = ", ".join(map_str_list)
                    # Identificador visual de jugador en línea
                    online_marker = "🟢 " if p_name in active_players else ""
                    players_text += (
                        f"- **{online_marker}{p_name}** ⏱️ {time_str}: {map_joined}\n"
                    )

            if players_text:
                # Fragmentación segura de texto para evasión de límite de 1024 caracteres
                chunks = []
                while len(players_text) > 900:
                    # Localización de salto de línea ideal (límite de 900 caracteres)
                    break_point = players_text.rfind("\n", 0, 900)
                    if break_point == -1:
                        break_point = 900
                    else:
                        break_point += 1  # Inclusión del salto de línea
                    chunks.append(players_text[:break_point])
                    players_text = players_text[break_point:]

                if players_text:
                    chunks.append(players_text)

                for idx, chunk in enumerate(chunks):
                    name = (
                        "🏆 Top Jugadores (Global)"
                        if idx == 0
                        else f"🏆 Top Jugadores (v{idx + 1})"
                    )
                    embed.add_field(name=name, value=chunk, inline=False)
            else:
                embed.add_field(
                    name="🏆 Top Jugadores (Global)",
                    value="No hay datos suficientes aún.",
                    inline=False,
                )

            # Consulta de Tribus Fijas para este servidor
            cursor = await db.execute(
                "SELECT name, members_json FROM k4ultra_fixed_tribes WHERE guild_id = ?",
                (guild_id,)
            )
            fixed_rows = await cursor.fetchall()
            fixed_players = set()
            import json

            for fr in fixed_rows:
                members = json.loads(fr["members_json"])
                for m in members:
                    fixed_players.add(m)

            # Consulta de Relaciones Dinámicas Calculadas para este servidor
            cursor = await db.execute(
                "SELECT player1, player2 FROM k4ultra_relationships WHERE (probability_score >= 10 OR is_manual = 1) AND guild_id = ?",
                (guild_id,)
            )
            rels = await cursor.fetchall()

            adjacency = {}
            for r in rels:
                p1, p2 = r["player1"], r["player2"]
                # Exclusión de jugadores de Tribus Fijas en algoritmos dinámicos
                if p1 in fixed_players or p2 in fixed_players:
                    continue
                if p1 not in adjacency:
                    adjacency[p1] = set()
                if p2 not in adjacency:
                    adjacency[p2] = set()
                adjacency[p1].add(p2)
                adjacency[p2].add(p1)

            visited = set()
            dynamic_tribes = []

            for node in adjacency:
                if node not in visited:
                    cluster = set()
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

            rels_text = ""

            # Representación visual de Tribus Fijas (prioritario)
            for fr in fixed_rows:
                tribe_name = fr["name"]
                members = json.loads(fr["members_json"])
                if not members:
                    continue
                tribe_str = ", ".join(members)

                placeholders = ", ".join(["?"] * len(members))
                cursor = await db.execute(
                    f"""
                    SELECT map_name, SUM(total_minutes) as tribe_mins
                    FROM k4ultra_playtime
                    WHERE player_name IN ({placeholders})
                    GROUP BY map_name
                    ORDER BY tribe_mins DESC
                    LIMIT 1
                """,
                    list(members),
                )
                map_row = await cursor.fetchone()
                map_info = f" | 🗺️ {map_row['map_name']}" if map_row else ""

                rels_text += f"**{tribe_name}** [🛡️ Fijada] ({len(members)}){map_info}\n└ {tribe_str}\n"

            # Representación visual de Tribus Dinámicas calculadas
            for i, tribe in enumerate(dynamic_tribes[:8]):
                if not tribe:
                    continue
                custom_name = None
                for m in tribe:
                    cursor = await db.execute(
                        "SELECT custom_name FROM k4ultra_tribe_names WHERE tribe_signature = ? AND guild_id = ?",
                        (m, guild_id),
                    )
                    cname_row = await cursor.fetchone()
                    if cname_row:
                        custom_name = cname_row["custom_name"]
                        break

                tribe_label = custom_name if custom_name else f"Grupo {i + 1}"
                tribe_str = ", ".join(tribe)
                if len(tribe_str) > 100:
                    tribe_str = tribe_str[:97] + "..."

                placeholders = ", ".join(["?"] * len(tribe))
                cursor = await db.execute(
                    f"""
                    SELECT map_name, SUM(total_minutes) as tribe_mins
                    FROM k4ultra_playtime
                    WHERE player_name IN ({placeholders}) AND guild_id = ?
                    GROUP BY map_name
                    ORDER BY tribe_mins DESC
                    LIMIT 1
                """,
                    list(tribe) + [guild_id],
                )
                map_row = await cursor.fetchone()

                map_info = f" | 🗺️ {map_row['map_name']}" if map_row else ""
                rels_text += (
                    f"**{tribe_label}** ({len(tribe)}){map_info}\n└ {tribe_str}\n"
                )

            if len(dynamic_tribes) > 8:
                rels_text += f"*... y {len(dynamic_tribes) - 8} grupos más*\n"

            if rels_text:
                chunks = []
                while len(rels_text) > 900:
                    break_point = rels_text.rfind("\n", 0, 900)
                    if break_point == -1:
                        break_point = 900
                    else:
                        break_point += 1
                    chunks.append(rels_text[:break_point])
                    rels_text = rels_text[break_point:]

                if rels_text:
                    chunks.append(rels_text)

                for idx, chunk in enumerate(chunks):
                    name = (
                        "🔗 Posibles Tribus / Grupos"
                        if idx == 0
                        else f"🔗 Tribus / Grupos (v{idx + 1})"
                    )
                    embed.add_field(name=name, value=chunk, inline=False)
            else:
                embed.add_field(
                    name="🔗 Posibles Tribus / Grupos",
                    value="No se han detectado grupos de momento.",
                    inline=False,
                )

            embed.set_footer(text="Información y grupos calculados automáticamente.")

        return embed, top_player_names

    @app_commands.command(
        name="k4ultra",
        description="Muestra información detallada de jugadores, tiempos y relaciones.",
    )
    @app_commands.describe(
        semana="Opcional. Número de semana para ver el histórico de esa semana."
    )
    async def k4ultra_command(
        self, interaction: discord.Interaction, semana: int = None
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
            async with aiosqlite.connect(self.bot.db_name) as db:
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
            embed, top_players = await self.generate_k4ultra_embed(interaction.guild_id)
            view = K4UltraView(self.bot, interaction.guild_id, top_players)

            try:
                message = await interaction.followup.send(embed=embed, view=view)
            except discord.HTTPException as e:
                logger.error(f"[K4Ultra Debug] HTTPException on send: {e}")
                logger.error(f"[K4Ultra Debug] Embed payload: {embed.to_dict()}")
                raise e

            async with aiosqlite.connect(self.bot.db_name) as db:
                await db.execute(
                    """
                    INSERT INTO k4ultra_messages (guild_id, channel_id, message_id)
                    VALUES (?, ?, ?)
                """,
                    (interaction.guild_id, interaction.channel_id, message.id),
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

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

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
    )
    async def fijar_tribu(
        self, interaction: discord.Interaction, nombre: str, jugadores: str
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

        async with aiosqlite.connect(self.bot.db_name) as db:
            import json

            await db.execute(
                "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json) VALUES (?, ?, ?)",
                (interaction.guild_id, nombre, json.dumps(miembros)),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Tribu fijada: **{nombre}** con los jugadores: {', '.join(miembros)}.\nEl algoritmo no añadirá jugadores externos a este bloque.",
            ephemeral=True,
        )

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

        async with aiosqlite.connect(self.bot.db_name) as db:
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
        name="set_alias",
        description="[Admin] Añade un segundo nombre a un jugador en el tracker (ej. Discord, Steam).",
    )
    @app_commands.describe(
        jugador="Nombre original tal y como aparece en el tracker",
        alias="El apodo a añadir",
    )
    async def set_alias(
        self, interaction: discord.Interaction, jugador: str, alias: str
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, ?, ?) ON CONFLICT(guild_id, player_name) DO UPDATE SET alias=excluded.alias",
                (interaction.guild_id, jugador, alias),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Alias añadido: **{jugador}** ahora se mostrará como **{jugador} [{alias}]**.",
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

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

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

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

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
    await bot.add_cog(K4Ultra(bot))
