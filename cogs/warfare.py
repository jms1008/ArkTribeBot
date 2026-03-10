import os
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import logging
from cogs.server_status import get_guild_servers

logger = logging.getLogger("ArkTribeBot")


PAGE_SIZE = 10  # Entradas por página en el dashboard de Blacklist


def build_blacklist_embed(rows: list, page: int = 0) -> discord.Embed:
    """Construye el embed de la Blacklist en formato compacto paginado."""
    total = len(rows)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = rows[start : start + PAGE_SIZE]

    embed = discord.Embed(
        title="☠️ Blacklist de Tribu",
        color=discord.Color.dark_grey(),
    )

    if not rows:
        embed.description = "No hay jugadores en la lista negra.\n💡 Usa el botón **Añadir** para registrar uno."
    else:
        lines = []
        for row in chunk:
            nota_corta = (
                (row["notes"][:30] + "...")
                if row["notes"] and len(row["notes"]) > 30
                else (row["notes"] or "")
            )
            lines.append(
                f"`#{row['id']}` **{row['player']}** | {row['tribe']} | {row['map']}\n"
                f"    📝 {nota_corta}"
            )
        embed.description = "\n\n".join(lines)
        embed.set_footer(
            text=f"Página {page + 1}/{total_pages} • {total} entradas totales"
        )

    return embed, page, total_pages


async def build_player_detail_embed(bot, player_name):
    """Construye un embed detallado de un jugador combinando Blacklist + K4Ultra."""
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row

        # 1. Datos de Blacklist
        cursor = await db.execute(
            "SELECT * FROM blacklist WHERE player = ?", (player_name,)
        )
        bl_row = await cursor.fetchone()

        if not bl_row:
            return discord.Embed(
                title="❌ Error",
                description=f"No se encontró a **{player_name}** en la blacklist.",
                color=discord.Color.red(),
            )

        # 2. Datos de K4Ultra - Playtime y Mapas
        cursor = await db.execute(
            "SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? ORDER BY total_minutes DESC",
            (player_name,),
        )
        pt_rows = await cursor.fetchall()

        total_mins = sum(r["total_minutes"] for r in pt_rows)
        total_hours = total_mins / 60

        maps_visited = []
        for r in pt_rows:
            h = r["total_minutes"] / 60
            maps_visited.append(f"• **{r['map_name']}**: {h:.1f}h")

        # 3. Datos de K4Ultra - Relaciones (Top 5)
        cursor = await db.execute(
            """
            SELECT player2 as ally, probability_score as prob FROM k4ultra_relationships WHERE player1 = ?
            UNION
            SELECT player1 as ally, probability_score as prob FROM k4ultra_relationships WHERE player2 = ?
            ORDER BY prob DESC LIMIT 5
            """,
            (player_name, player_name),
        )
        rel_rows = await cursor.fetchall()
        allies = [f"• **{r['ally']}** ({r['prob']}%)" for r in rel_rows]

        # Construcción del Embed
        embed = discord.Embed(
            title=f"💀 Ficha de Objetivo: {player_name}",
            description=f"**Tribu**: {bl_row['tribe']}\n**Notas**: {bl_row['notes']}",
            color=discord.Color.dark_red(),
        )

        embed.add_field(
            name="📅 Fecha de Registro", value=bl_row["created_at"], inline=True
        )
        embed.add_field(
            name="🕒 Tiempo Total (K4)", value=f"{total_hours:.1f} horas", inline=True
        )

        last_seen = bl_row["last_seen"] or "Desconocido"
        embed.add_field(name="📍 Último Avistamiento", value=last_seen, inline=False)

        if maps_visited:
            embed.add_field(
                name="🗺️ Actividad por Mapas",
                value="\n".join(maps_visited),
                inline=False,
            )

        if allies:
            embed.add_field(
                name="👥 Aliados Cercanos", value="\n".join(allies), inline=False
            )

        embed.set_footer(text="Datos cruzados con Radar K4Ultra")
        return embed


async def update_blacklist_dashboards(bot, page: int = 0):
    """Actualiza todos los mensajes de lista negra (dashboards)."""

    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM blacklist_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Recuperación de registros de la Blacklist
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM blacklist ORDER BY id DESC")
        rows = await cursor.fetchall()

    embed, current_page, total_pages = build_blacklist_embed(rows, page)
    view = BlacklistView(bot, rows, current_page)
    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                await message.edit(embed=embed, view=view)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            logger.error(f"Error actualizando blacklist dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos o inaccesibles
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM blacklist_messages WHERE id = ?", (mid,))
            await db.commit()


async def update_kda_dashboards(bot, guild_id=None):
    """Actualiza todos los mensajes persistentes del Ranking KDA (El Más Manco)."""
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        if guild_id:
            cursor = await db.execute(
                "SELECT * FROM kda_messages WHERE guild_id = ?", (guild_id,)
            )
        else:
            cursor = await db.execute("SELECT * FROM kda_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Generación del Leaderboard con cálculo dinámico de K/D
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        # Ordenación ascendente por K/D (Peor ratio = "El Más Manco").
        # Prevención de división por cero tratando muertes=0 como 1 lógicamente en la consulta.
        if guild_id:
            cursor = await db.execute(
                """
                SELECT player_name, kills, deaths,
                       CAST(kills AS FLOAT) / CASE WHEN deaths = 0 THEN 1 ELSE deaths END as kd_ratio
                FROM tribe_kda
                WHERE guild_id = ?
                ORDER BY kd_ratio ASC, deaths DESC
            """,
                (guild_id,),
            )
        else:
            cursor = await db.execute("""
                SELECT player_name, kills, deaths,
                       CAST(kills AS FLOAT) / CASE WHEN deaths = 0 THEN 1 ELSE deaths END as kd_ratio
                FROM tribe_kda
                ORDER BY kd_ratio ASC, deaths DESC
            """)
        rows = await cursor.fetchall()

    if not rows:
        embed = discord.Embed(
            title="☠️ Ranking de El Más Manco",
            description="Todavía no hay bajas registradas en la tribu.",
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="💡 Añade personajes con /ranking_char_add")
    else:
        embed = discord.Embed(
            title="☠️ Ranking de El Más Manco (K/D/A)",
            description="La tabla de la vergüenza. Ordenado de **PEOR a MEJOR** Ratio K/D.",
            color=discord.Color.red(),
        )

        medallas = ["🥇", "🥈", "🥉", "💀", "💀", "💀", "💀", "💀", "💀", "💀"]

        for idx, row in enumerate(rows):
            medalla = medallas[idx] if idx < len(medallas) else "🪦"

            kd_ratio = row["kd_ratio"]
            kills = row["kills"]
            deaths = row["deaths"]

            embed.add_field(
                name=f"{medalla} #{idx + 1} | {row['player_name']}",
                value=f"**K/D Ratio:** `{kd_ratio:.2f}`\n⚔️ **Kills:** {kills} | ☠️ **Muertes:** {deaths}",
                inline=False,
            )

        embed.set_footer(
            text="💡 El Bot se actualiza en vivo leyendo los logs del servidor."
        )

    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                await message.edit(embed=embed)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            logger.error(f"Error actualizando KDA dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM kda_messages WHERE id = ?", (mid,))
            await db.commit()


class AddBlacklistModal(discord.ui.Modal, title="Añadir a Blacklist"):
    player = discord.ui.TextInput(
        label="Nombre del Jugador", placeholder="Ej: xXDarkHunterXx"
    )
    tribe = discord.ui.TextInput(
        label="Tribu", placeholder="Ej: Los Malos", required=False
    )
    map_name = discord.ui.TextInput(
        label="Mapa", placeholder="Ej: Fjordur", required=False
    )
    notes = discord.ui.TextInput(
        label="Notas",
        placeholder="Razón del ban o información relevante",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO blacklist (player, tribe, map, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    self.player.value,
                    self.tribe.value or "Desconocido",
                    self.map_name.value or "Desconocido",
                    self.notes.value or "",
                    datetime.datetime.now().isoformat(),
                ),
            )
            await db.commit()
        await interaction.response.send_message(
            f"✅ **{self.player.value}** añadido a la Blacklist.", ephemeral=True
        )
        await update_blacklist_dashboards(self.bot)


class ModifyBlacklistModal(discord.ui.Modal, title="Modificar entrada de Blacklist"):
    entry_id = discord.ui.TextInput(label="ID de la entrada", placeholder="Número ID")
    campo = discord.ui.TextInput(
        label="Campo a modificar",
        placeholder="player | tribe | map | notes",
    )
    nuevo_valor = discord.ui.TextInput(
        label="Nuevo valor",
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        valid_fields = {"player", "tribe", "map", "notes"}
        campo = self.campo.value.strip().lower()
        if campo not in valid_fields:
            await interaction.response.send_message(
                f"❌ Campo inválido. Usa: {', '.join(valid_fields)}", ephemeral=True
            )
            return
        try:
            bid = int(self.entry_id.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT id FROM blacklist WHERE id = ?", (bid,))
            if not await cursor.fetchone():
                await interaction.response.send_message(
                    f"❌ No existe la entrada ID {bid}.", ephemeral=True
                )
                return
            await db.execute(
                f"UPDATE blacklist SET {campo} = ? WHERE id = ?",
                (self.nuevo_valor.value, bid),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ ID {bid} actualizado: **{campo}** → {self.nuevo_valor.value}",
            ephemeral=True,
        )
        await update_blacklist_dashboards(self.bot)


class DeleteBlacklistModal(discord.ui.Modal, title="Eliminar de Blacklist"):
    entry_id = discord.ui.TextInput(
        label="ID de la Entrada", placeholder="Número ID", min_length=1
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bid = int(self.entry_id.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute("DELETE FROM blacklist WHERE id = ?", (bid,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Entrada ID {bid} eliminada.", ephemeral=True
        )
        await update_blacklist_dashboards(self.bot)


class PlayerDetailSelect(discord.ui.Select):
    def __init__(self, bot, players):
        self.bot = bot
        options = [discord.SelectOption(label=p, emoji="🔍") for p in players[:25]]
        super().__init__(
            placeholder="Selecciona un jugador para ver detalles...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        player_name = self.values[0]
        embed = await build_player_detail_embed(self.bot, player_name)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class BlacklistView(discord.ui.View):
    def __init__(self, bot, rows=None, page: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.rows = rows or []
        self.page = page

        # Desplegable de detalles (fila 1)
        player_names = [
            r["player"] for r in rows[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        ]
        if player_names:
            self.add_item(PlayerDetailSelect(bot, player_names))

        # Botones de navegación (fila 2)
        # Se añaden manualmente para controlar el orden y las filas
        self.prev_btn = discord.ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            disabled=page == 0,
            row=2,
        )
        self.prev_btn.callback = self.prev_page_callback
        self.add_item(self.prev_btn)

        self.next_btn = discord.ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            disabled=(page + 1) * PAGE_SIZE >= len(rows),
            row=2,
        )
        self.next_btn.callback = self.next_page_callback
        self.add_item(self.next_btn)

        # Botones de Acción (fila 3)
        self.add_btn = discord.ui.Button(
            label="Añadir",
            style=discord.ButtonStyle.success,
            emoji="➕",
            row=3,
        )
        self.add_btn.callback = self.add_callback
        self.add_item(self.add_btn)

        self.mod_btn = discord.ui.Button(
            label="Modificar",
            style=discord.ButtonStyle.primary,
            emoji="📝",
            row=3,
        )
        self.mod_btn.callback = self.mod_callback
        self.add_item(self.mod_btn)

        self.del_btn = discord.ui.Button(
            label="Eliminar",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            row=3,
        )
        self.del_btn.callback = self.del_callback
        self.add_item(self.del_btn)

    async def add_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddBlacklistModal(self.bot))

    async def mod_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ModifyBlacklistModal(self.bot))

    async def del_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DeleteBlacklistModal(self.bot))

    async def prev_page_callback(self, interaction: discord.Interaction):
        """Página anterior de la Blacklist."""
        new_page = max(0, self.page - 1)
        await self._update_page(interaction, new_page)

    async def next_page_callback(self, interaction: discord.Interaction):
        """Página siguiente de la Blacklist."""
        total_pages = max(1, (len(self.rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        new_page = min(total_pages - 1, self.page + 1)
        await self._update_page(interaction, new_page)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        """Carga los datos frescos, construye el embed de la página pedida y edita el mensaje."""
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM blacklist ORDER BY id DESC")
            rows = await cursor.fetchall()

        embed, current_page, _ = build_blacklist_embed(rows, new_page)
        new_view = BlacklistView(self.bot, rows, current_page)
        await interaction.response.edit_message(embed=embed, view=new_view)


class Warfare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Rutina de seguridad para asegurar el esquema correcto (Migración legacy)
        asyncio.create_task(self.check_schema())

    async def check_schema(self):
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Comprobación de existencia del esquema antiguo (steam_id vs id)
            try:
                # Intento de lectura de la columna ID (Nuevo estándar)
                await db.execute("SELECT id FROM blacklist LIMIT 1")
            except aiosqlite.OperationalError:
                # Falla de lectura: Detectado esquema antiguo
                logger.warning(
                    "⚠️ Detectada versión antigua de Blacklist. Migrando tabla..."
                )
                try:
                    backup_name = (
                        f"blacklist_backup_{int(datetime.datetime.now().timestamp())}"
                    )
                    await db.execute(f"ALTER TABLE blacklist RENAME TO {backup_name}")
                    logger.info(f"✅ Tabla antigua renombrada a {backup_name}")

                    await db.execute("""
                        CREATE TABLE blacklist (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            player TEXT,
                            tribe TEXT,
                            map TEXT,
                            notes TEXT,
                            created_at TEXT,
                            last_seen TEXT,
                            total_hours REAL DEFAULT 0
                        )
                    """)
                    logger.info("✅ Nueva tabla blacklist creada con schema correcto.")
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ Error durante la migración de Blacklist: {e}")

            # Comprobación de columnas nuevas para enriquecimiento
            try:
                await db.execute("SELECT last_seen FROM blacklist LIMIT 1")
            except aiosqlite.OperationalError:
                logger.info(
                    "➕ Añadiendo columnas last_seen y total_hours a la blacklist."
                )
                try:
                    await db.execute("ALTER TABLE blacklist ADD COLUMN last_seen TEXT")
                    await db.execute(
                        "ALTER TABLE blacklist ADD COLUMN total_hours REAL DEFAULT 0"
                    )
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ Error añadiendo columnas a Blacklist: {e}")

    # --- Funciones de Autocompletado ---
    async def tribe_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT DISTINCT tribe FROM blacklist WHERE tribe LIKE ? ORDER BY tribe ASC LIMIT 25",
                (f"%{current}%",),
            )
            rows = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=row[0], value=row[0]) for row in rows if row[0]
        ]
        # Retorno de coincidencias o permite texto libre por defecto (Discord behavior)
        return choices

    async def map_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dinámico de mapas basado en los servidores del Guild."""
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        choices = [name for name in servers.keys() if current.lower() in name.lower()]
        return [app_commands.Choice(name=m, value=m) for m in choices[:25]]

    # --- Definición de Comandos ---

    @app_commands.command(
        name="blacklist",
        description="Muestra el dashboard de la Blacklist (Auto-actualizable).",
    )
    async def blacklist(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True
        )  # Aplazamiento de respuesta para prevenir Timeout de la interacción

        # Generación del placeholder inicial (Actualización sincrónica inminente)
        embed = discord.Embed(
            title="Cargando Blacklist...", color=discord.Color.dark_grey()
        )
        await interaction.followup.send(embed=embed)
        message = await interaction.original_response()

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO blacklist_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
            )
            await db.commit()

        await update_blacklist_dashboards(self.bot)

    # /blacklist_add y /blacklist_mod eliminados — cubiertos por botones del dashboard

    @app_commands.command(
        name="sos", description="¡ALERTA DE RAID! Envía una señal de ayuda."
    )
    @app_commands.describe(
        tipo="Tipo de amenaza (Opcional)",
        mapa="Mapa del ataque (Opcional)",
        atacantes="Número aprox. de enemigos",
        defensores="Número de aliados presentes",
        notas="Información extra",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="🔴 RAIDEO (Base Principal)", value="Raideo"),
            app_commands.Choice(name="🟠 FOB Enemiga", value="FOB"),
            app_commands.Choice(name="🟡 Soaking (Tanqueo)", value="Soaking"),
            app_commands.Choice(name="⚔️ PvP Masivo", value="PvP"),
            app_commands.Choice(name="👀 Scouting Hostil", value="Scouting"),
        ]
    )
    @app_commands.autocomplete(mapa=map_autocomplete)
    async def sos(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str] = None,
        mapa: str = None,
        atacantes: int = None,
        defensores: int = None,
        notas: str = None,
    ):
        # Recuperación del Rol SOS desde variables de entorno
        role_id = os.getenv("SOS_ROLE_ID")
        role_mention = f"<@&{role_id}>" if role_id else "@everyone"

        if not tipo and not mapa and not atacantes and not defensores and not notas:
            # Fallback: Dispatch de SOS Generalizado (Falta de argumentos)
            embed = discord.Embed(
                title="🚨 ¡SOS GENERAL! 🚨",
                description=f"**¡SE NECESITA AYUDA URGENTE!**\n\nEl usuario {interaction.user.mention} ha solicitado asistencia inmediata.\n¡Entrad al canal de voz YA!",
                color=discord.Color.brand_red(),
            )
            embed.set_footer(text="⚠️ Alerta de Prioridad MÁXIMA")
        else:
            # Dispatch: SOS Estructurado y Detallado
            titulo = (
                f"🚨 ALERTA: {tipo.value.upper()}" if tipo else "🚨 ALERTA DE COMBATE"
            )
            color = discord.Color.red()

            embed = discord.Embed(title=titulo, color=color)
            embed.description = f"**Solicitud de ayuda de** {interaction.user.mention}"

            if mapa:
                embed.add_field(name="🗺️ Mapa", value=f"**{mapa}**", inline=True)
            if tipo:
                embed.add_field(name="🔥 Tipo", value=tipo.value, inline=True)

            # Formateo de recuento de fuerzas (Enemigos/Aliados)
            atack_str = str(atacantes) if atacantes is not None else "?"
            def_str = str(defensores) if defensores is not None else "?"
            embed.add_field(
                name="⚔️ Status",
                value=f"👿 **Enemigos:** {atack_str}\n🛡️ **Aliados:** {def_str}",
                inline=False,
            )

            if notas:
                embed.add_field(name="📝 Notas", value=notas, inline=False)

            embed.set_footer(text="¡Dejad lo que estéis haciendo y venid!")

        # Broadcast de la alerta al canal de registro
        await interaction.channel.send(content=role_mention, embed=embed)
        await interaction.response.send_message(
            "✅ Alerta SOS enviada.", ephemeral=True
        )

    # --- K/D/A Tracker (Ranking Manco) ---

    @app_commands.command(
        name="ranking",
        description="Muestra el panel en vivo del Ranking K/D/A (El Más Manco).",
    )
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="Cargando Ranking...", color=discord.Color.dark_red()
        )
        await interaction.followup.send(embed=embed)
        message = await interaction.original_response()

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO kda_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
            )
            await db.commit()

        await update_kda_dashboards(self.bot)

    @app_commands.command(
        name="ranking_char_add",
        description="Vincula un personaje In-Game a un jugador para contar sus kills/muertes.",
    )
    @app_commands.describe(
        jugador="Nombre del jugador de Tribu",
        personaje="Nombre exacto del personaje en ARK",
    )
    async def ranking_char_add(
        self, interaction: discord.Interaction, jugador: str, personaje: str
    ):
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Upsert (Insert or Update) del vínculo Personaje-Jugador
            await db.execute(
                "INSERT INTO tribe_characters (character_name, player_name) VALUES (?, ?) ON CONFLICT(character_name) DO UPDATE SET player_name=excluded.player_name",
                (personaje, jugador),
            )
            # Inicialización segura del perfil del jugador en el Tracker KDA a 0
            await db.execute(
                "INSERT OR IGNORE INTO tribe_kda (player_name, kills, deaths) VALUES (?, 0, 0)",
                (jugador,),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Ahora el personaje in-game **{personaje}** registrará muertes y bajas para el jugador **{jugador}**.",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot)

    @app_commands.command(
        name="ranking_char_remove",
        description="Desvincula un personaje del sistema de KDA.",
    )
    @app_commands.describe(personaje="Nombre exacto del personaje en ARK")
    async def ranking_char_remove(
        self, interaction: discord.Interaction, personaje: str
    ):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM tribe_characters WHERE character_name = ?", (personaje,)
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Personaje **{personaje}** eliminado del registro de logs KDA.",
            ephemeral=False,
        )

    @app_commands.command(
        name="ranking_remove",
        description="¡ADMIN! Borra a un jugador entero del KDA Tracker.",
    )
    @app_commands.describe(jugador="Nombre del jugador a purgar")
    async def ranking_remove(self, interaction: discord.Interaction, jugador: str):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute("DELETE FROM tribe_kda WHERE player_name = ?", (jugador,))
            await db.execute(
                "DELETE FROM tribe_characters WHERE player_name = ?", (jugador,)
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ El jugador **{jugador}** ha sido borrado del Leaderboard (Kills y Muertes reseteadas).",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot)


async def setup(bot):
    await bot.add_cog(Warfare(bot))
