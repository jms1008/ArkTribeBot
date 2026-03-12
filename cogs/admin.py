import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiosqlite
import asyncio

logger = logging.getLogger("ArkTribeBot")

logger = logging.getLogger("ArkTribeBot")


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        # No hay tareas en segundo plano
        pass

    @app_commands.command(
        name="bind_k4ultra",
        description="[Admin] Asocia un mensaje existente al dashboard de K4Ultra.",
    )
    @app_commands.describe(
        message_id="ID del mensaje a asociar",
        channel_id="Opcional. ID del canal si el mensaje está en otro sitio.",
    )
    async def bind_k4ultra(
        self, interaction: discord.Interaction, message_id: str, channel_id: str = None
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        try:
            msg_id_int = int(message_id)

            # Uso del canal actual si no se provee ID
            if channel_id:
                ch_id_int = int(channel_id)
                target_channel = self.bot.get_channel(
                    ch_id_int
                ) or await self.bot.fetch_channel(ch_id_int)
            else:
                target_channel = interaction.channel
                ch_id_int = interaction.channel_id

            if not target_channel:
                await interaction.response.send_message(
                    "❌ No se encontró el canal especificado.", ephemeral=True
                )
                return

            message = await target_channel.fetch_message(msg_id_int)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error buscando el mensaje o canal: {e}", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            await db.execute(
                "INSERT INTO k4ultra_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (interaction.guild_id, ch_id_int, msg_id_int),
            )
            await db.commit()

        # Generación del primer embed
        from cogs.k4ultra import K4UltraView

        k_cog = self.bot.get_cog("K4Ultra")
        if k_cog:
            embed, top_players = await k_cog.generate_k4ultra_embed(
                interaction.guild_id
            )
            view = K4UltraView(self.bot, interaction.guild_id, top_players)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Mensaje `{message_id}` del canal `<#{ch_id_int}>` asociado a K4Ultra con éxito.",
            ephemeral=True,
        )

    @app_commands.command(
        name="config",
        description="[Admin] Visualiza o modifica la configuración del bot para este servidor.",
    )
    @app_commands.describe(
        canal_sos="Canal de retransmisión de alertas (SOS).",
        canal_logs="Canal puente donde el bot lee eventos del juego.",
        canal_archivos="Canal para almacenamiento redundante de imágenes.",
        intervalo_act="Frecuencia (minutos) para actualizar dashboards.",
        rol_admin="Rol de Discord autorizado para usar comandos protegidos.",
        propietario_bot="Usuario de Discord propietario del bot en este servidor.",
        battlemetrics="Servidores del clúster (Ej: Fjordur|1.2.3.4:21004).",
        puntos_diarios="Habilitar/Deshabilitar sistema de puntos (True/False).",
    )
    async def config(
        self,
        interaction: discord.Interaction,
        canal_sos: discord.TextChannel = None,
        canal_logs: discord.TextChannel = None,
        canal_archivos: discord.TextChannel = None,
        intervalo_act: int = None,
        rol_admin: discord.Role = None,
        propietario_bot: discord.Member = None,
        battlemetrics: str = None,
        puntos_diarios: bool = None,
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **Acceso denegado.** Necesitas permisos de Administrador o el Rol configurado.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        db_name = self.bot.db_name

        # Si hay parámetros, actualizar primero
        updates = []
        params = []
        if canal_sos:
            updates.append("sos_channel_id = ?")
            params.append(canal_sos.id)
        if canal_logs:
            updates.append("log_channel_id = ?")
            params.append(canal_logs.id)
        if canal_archivos:
            updates.append("upload_channel_id = ?")
            params.append(canal_archivos.id)
        if intervalo_act is not None:
            updates.append("update_interval = ?")
            params.append(intervalo_act)
        if rol_admin:
            updates.append("admin_role_id = ?")
            params.append(rol_admin.id)
        if propietario_bot:
            updates.append("bot_owner_id = ?")
            params.append(propietario_bot.id)
        if battlemetrics:
            updates.append("battlemetrics_urls = ?")
            params.append(battlemetrics)
        if puntos_diarios is not None:
            updates.append("daily_points_enabled = ?")
            params.append(1 if puntos_diarios else 0)

        if updates:
            sql = f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id = ?"
            params.append(guild_id)
            async with aiosqlite.connect(db_name) as db:
                await db.execute(sql, tuple(params))
                await db.commit()
            await interaction.response.send_message(
                "✅ **Configuración actualizada correctamente.**", ephemeral=True
            )
        else:
            await interaction.response.defer(ephemeral=False)

        # Consultar configuración actual para el embed
        async with aiosqlite.connect(db_name) as db:
            db.row_factory = aiosqlite.Row
            c = await db.execute(
                "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
            )
            config = await c.fetchone()

            # Miembros registrados
            c2 = await db.execute(
                "SELECT COUNT(*) FROM tribe_characters WHERE guild_id = ?", (guild_id,)
            )
            count_res = await c2.fetchone()
            num_miembros = count_res[0] if count_res else 0

        if not config:
            await (interaction.followup.send if not updates else interaction.edit_original_response)(
                content="❌ Este servidor no está configurado. Usa `/inicio_ark` primero."
            )
            return

        embed = discord.Embed(
            title="⚙️ Configuración Actual de ArkTribeBot",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"ID Servidor: {guild_id}")

        embed.add_field(
            name="📡 Canales Principales",
            value=(
                f"🚨 **SOS:** <#{config['sos_channel_id']}>\n"
                f"📜 **Logs:** <#{config['log_channel_id']}>\n"
                f"📁 **Archivos:** <#{config['upload_channel_id']}>"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛡️ Seguridad y Permisos",
            value=(
                f"👤 **Dueño:** <@{config['bot_owner_id']}>\n"
                f"🛡️ **Rol Admin:** <@&{config['admin_role_id']}>" if config['admin_role_id'] else "🛡️ **Rol Admin:** No configurado"
            ),
            inline=True,
        )

        embed.add_field(
            name="📊 Preferencias",
            value=(
                f"⏱️ **Sync Interval:** {config['update_interval']} min\n"
                f"🪙 **Puntos Diarios:** {'✅ ON' if config['daily_points_enabled'] else '❌ OFF'}"
            ),
            inline=True,
        )

        embed.add_field(
            name="👨‍👩‍👧‍👦 Tribu",
            value=f"👥 **Miembros Registrados:** {num_miembros}",
            inline=True,
        )

        bm_urls = config['battlemetrics_urls'] or "Ninguno"
        if len(bm_urls) > 1024:
            bm_urls = bm_urls[:1021] + "..."
        embed.add_field(
            name="🎮 Cluster (BattleMetrics)",
            value=f"```\n{bm_urls}\n```",
            inline=False,
        )

        if updates:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(embed=embed)

    @commands.command(name="sync")
    async def sync(
        self,
        ctx: commands.Context,
        spec: str | None = None,
    ):
        """Sincroniza los comandos slash. Uso: !sync [global|guild|clear]"""
        if spec == "global":
            await ctx.send(
                "🌐 **Sincronizando comandos globalmente...** (Puede tardar hasta 1 hora en propagarse)"
            )
            synced = await self.bot.tree.sync()
            await ctx.send(
                f"✅ Se han sincronizado **{len(synced)}** comandos globalmente."
            )
        elif spec == "clear":
            await ctx.send("🗑️ **Limpiando comandos en este servidor...**")
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(
                "✅ Comandos de servidor eliminados (se usarán los globales)."
            )
        else:
            await ctx.send(f"🔄 **Sincronizando comandos en '{ctx.guild.name}'...**")
            try:
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(
                    f"✅ **{len(synced)}** comandos sincronizados instantáneamente en este servidor."
                )
                logger.info(
                    f"Comandos sincronizados manualente en {ctx.guild.name} ({ctx.guild.id})"
                )
            except discord.HTTPException as e:
                if e.status == 429:
                    await ctx.send(
                        "⚠️ **Discord nos está limitando (Rate Limit).** El bot esperará automáticamente y completará la sincronización en unos minutos. No vuelvas a ejecutar el comando."
                    )
                else:
                    await ctx.send(f"❌ Error HTTP: {e}")
            except Exception as e:
                await ctx.send(f"❌ Error al sincronizar: {e}")
                logger.error(f"Error sync: {e}")

    @app_commands.command(
        name="inicio_ark",
        description="[Admin/Dueño] Configura ArkTribeBot para este servidor (Multi-Guild Setup).",
    )
    @app_commands.describe(
        canal_sos="Canal de retransmisión de alertas (SOS).",
        canal_logs="Canal puente donde el bot lee eventos del juego (Tribemember Killed, @policía).",
        canal_archivos="Canal o Hilo para almacenamiento redundante de imágenes (Scouts).",
        intervalo_act="Frecuencia (minutos) para actualizar dashboards (Ej: 2, 5, 10).",
        rol_admin="Rol de Discord autorizado para usar comandos protegidos del bot.",
        propietario_bot="Tu usuario de Discord. Será el propietario permanente de este bot en este servidor.",
        battlemetrics="Servidores del clúster. Formato: 'Mapa|IP:Puerto' separados por comas. Ej: Fjordur|1.2.3.4:21004",
        canal_todo="[Opcional] Canal para el To-Do List y Tareas.",
        canal_crianza="[Opcional] Canal para el Dashboard de Líneas Genéticas.",
        canal_blacklist="[Opcional] Canal para el Panel de Enemigos KOS.",
        canal_scouting="[Opcional] Canal global para Reconocimiento de Bases.",
        canal_k4ultra="[Opcional] Canal central para Radar de Inteligencia.",
        canal_status="[Opcional] Canal de monitorización global del clúster.",
    )
    async def inicio_ark(
        self,
        interaction: discord.Interaction,
        canal_sos: discord.TextChannel,
        canal_logs: discord.TextChannel,
        canal_archivos: discord.TextChannel,
        intervalo_act: int = 2,
        rol_admin: discord.Role = None,
        propietario_bot: discord.Member = None,
        battlemetrics: str = None,
        canal_todo: discord.TextChannel = None,
        canal_crianza: discord.TextChannel = None,
        canal_blacklist: discord.TextChannel = None,
        canal_scouting: discord.TextChannel = None,
        canal_k4ultra: discord.TextChannel = None,
        canal_status: discord.TextChannel = None,
    ):
        # Solo el dueño del servidor o verdaderos Admins de Discord pueden configurar el bot inicialmente
        AUTHORIZED_ADMIN_ID = 290904414452056064
        if (
            interaction.user.id != AUTHORIZED_ADMIN_ID
            and interaction.user.id != interaction.guild.owner_id
            and not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "❌ **Acceso denegado.** Solo el Dueño del Servidor o Administradores pueden configurar el bot.",
                ephemeral=True,
            )
            return

        # Defer para evitar ratelimits al crear múltiples canales/dashboards
        await interaction.response.defer(thinking=True)

        guild_id = interaction.guild_id
        admin_role_id = rol_admin.id if rol_admin else None
        bot_owner_id = propietario_bot.id if propietario_bot else interaction.user.id

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO guild_config (
                    guild_id, sos_channel_id, log_channel_id, upload_channel_id,
                    update_interval, admin_role_id, bot_owner_id, battlemetrics_urls
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    sos_channel_id = excluded.sos_channel_id,
                    log_channel_id = excluded.log_channel_id,
                    upload_channel_id = excluded.upload_channel_id,
                    update_interval = excluded.update_interval,
                    admin_role_id = excluded.admin_role_id,
                    bot_owner_id = excluded.bot_owner_id,
                    battlemetrics_urls = excluded.battlemetrics_urls
            """,
                (
                    guild_id,
                    canal_sos.id,
                    canal_logs.id,
                    canal_archivos.id,
                    intervalo_act,
                    admin_role_id,
                    bot_owner_id,
                    battlemetrics,
                ),
            )
            await db.commit()

        embed = discord.Embed(
            title="✅ ArkTribeBot Configurado Correctamente",
            description="El servidor ha sido vinculado con éxito a la base de datos.",
            color=discord.Color.green(),
        )
        embed.add_field(name="🚨 Canal SOS", value=canal_sos.mention, inline=False)
        embed.add_field(
            name="📜 Canal de Logs (Oyente)", value=canal_logs.mention, inline=False
        )
        embed.add_field(
            name="📁 Canal de Archivos", value=canal_archivos.mention, inline=False
        )
        embed.add_field(
            name="⏱️ Intervalo Dashboards",
            value=f"{intervalo_act} minutos",
            inline=False,
        )
        if rol_admin:
            embed.add_field(name="🛡️ Rol Admin", value=rol_admin.mention, inline=False)
        # Mostrar el propietario del bot configurado para este servidor
        owner_mention = (
            propietario_bot.mention if propietario_bot else interaction.user.mention
        )
        embed.add_field(
            name="👑 Propietario del Bot", value=owner_mention, inline=False
        )

        await interaction.followup.send(embed=embed)

        # ------------------- AUTO-SETUP DE CANALES OPCIONALES -------------------
        from cogs.management import INFO_TEXTS, TodoView
        from cogs.warfare import BlacklistView
        from cogs.breeding import BreedingDashboardView
        from cogs.scouting import ScoutView

        # Enviar info de SOS al canal SOS obligatorio
        info_sos_embed = discord.Embed(
            description=INFO_TEXTS["sos"], color=discord.Color.from_rgb(43, 45, 49)
        )
        try:
            await canal_sos.send(embed=info_sos_embed)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error enviando info SOS: {e}")

        # Configuración To-Do List
        if canal_todo:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["todo_list"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_todo.send(embed=info_embed)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT * FROM todos WHERE guild_id = ?",
                        (interaction.guild_id,),
                    )
                    rows = await cursor.fetchall()

                todo_embed = discord.Embed(
                    title="📝 Lista de Tareas", color=discord.Color.orange()
                )
                if not rows:
                    todo_embed.description = (
                        "No hay tareas pendientes. ¡Buen trabajo! 🎉"
                    )
                else:
                    text = ""
                    for row in rows:
                        asignado = (
                            f"<@{row['asignado_a']}>" if row["asignado_a"] else "Nadie"
                        )
                        estado_icon = "⏳" if row["estado"] == "Pendiente" else "🔨"
                        text += f"**#{row['id']}** {estado_icon} - {row['tarea']}\\n   Estado: {row['estado']} | Asignado: {asignado}\\n\\n"
                        if len(text) > 3800:
                            text += "... (lista truncada)"
                            break
                    todo_embed.description = text

                view = TodoView(self.bot)
                msg = await canal_todo.send(embed=todo_embed, view=view)
                await asyncio.sleep(0.5)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    await db.execute(
                        "INSERT INTO todo_messages (channel_id, message_id) VALUES (?, ?)",
                        (canal_todo.id, msg.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando ToDo: {e}")

        # Configuración Crianza / Líneas
        if canal_crianza:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["lineas"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_crianza.send(embed=info_embed)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT * FROM dinos WHERE guild_id = ? ORDER BY especie ASC",
                        (interaction.guild_id,),
                    )
                    rows = await cursor.fetchall()

                crianza_embed = discord.Embed(
                    title="🧬 Líneas de Crianza y Genética Base",
                    color=discord.Color.green(),
                )
                if not rows:
                    crianza_embed.description = "No hay dinos registrados."
                    crianza_view = BreedingDashboardView(self.bot, [])
                else:
                    page_size = 10
                    dinos = [row[0] for row in rows]
                    current_dinos = dinos[0:page_size]

                    for row in rows[
                        :15
                    ]:  # Limit hardcoded for initial setup to avoid going over Discord 10 limit visually during setup, proper pagination resets via buttons anyway
                        crianza_embed.add_field(
                            name=f"🦖 {row['especie']}",
                            value=f"❤️ {row['hp']} | ⚡ {row['stam']} | ⚖️ {row['weight']} | ⚔️ {row['melee']} | 🫧 {row['oxy']} | 🍖 {row['food']} | 💨 {row['speed']}",
                            inline=False,
                        )
                    crianza_embed.set_footer(
                        text="Página 1/1"
                        if len(rows) <= page_size
                        else f"Página 1/{(len(rows) + page_size - 1) // page_size}"
                    )
                    crianza_view = BreedingDashboardView(self.bot, current_dinos)

                msg = await canal_crianza.send(embed=crianza_embed, view=crianza_view)
                await asyncio.sleep(0.5)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    await db.execute(
                        "INSERT INTO breeding_messages (channel_id, message_id) VALUES (?, ?)",
                        (canal_crianza.id, msg.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando Crianza: {e}")

        # Configuración Blacklist
        if canal_blacklist:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["blacklist"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_blacklist.send(embed=info_embed)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT * FROM blacklist WHERE guild_id = ? ORDER BY is_enemy DESC, id DESC",
                        (interaction.guild_id,),
                    )
                    rows = await cursor.fetchall()

                bl_embed = discord.Embed(
                    title="☠️ Blacklist de Jugadores", color=discord.Color.dark_red()
                )
                if not rows:
                    bl_embed.description = "La lista negra está vacía."
                else:
                    enemigos_text = ""
                    neutrales_text = ""
                    for row in rows:
                        mapa_str = f" [{row['mapa']}]" if row["mapa"] else ""
                        if row["is_enemy"] == 1:
                            enemigos_text += f"> **#{row['id']}** 🔴 {row['nombre']} | Tribu: {row['tribu']}{mapa_str}\\n   Notas: {row['notas']}\\n\\n"
                        else:
                            neutrales_text += f"> **#{row['id']}** ⚪ {row['nombre']} | Tribu: {row['tribu']}{mapa_str}\\n   Notas: {row['notas']}\\n\\n"

                    bl_embed.description = ""
                    if enemigos_text:
                        bl_embed.description += (
                            f"**ENEMIGOS ACTIVOS**\\n{enemigos_text}\\n"
                        )
                    if neutrales_text:
                        bl_embed.description += (
                            f"**REGISTROS K4ULTRA (Neutrales)**\\n{neutrales_text}"
                        )

                    if len(bl_embed.description) > 3800:
                        bl_embed.description = (
                            bl_embed.description[:3800] + "...\\n(Lista truncada)"
                        )

                view = BlacklistView(self.bot, rows=rows, page=0)
                msg = await canal_blacklist.send(embed=bl_embed, view=view)
                await asyncio.sleep(0.5)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    await db.execute(
                        "INSERT INTO blacklist_messages (channel_id, message_id) VALUES (?, ?)",
                        (canal_blacklist.id, msg.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando Blacklist: {e}")

        # Configuración Scouting
        if canal_scouting:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["scouting"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_scouting.send(embed=info_embed)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT * FROM scouts WHERE guild_id = ? ORDER BY nivel_amenaza DESC LIMIT 5",
                        (interaction.guild_id,),
                    )
                    rows = await cursor.fetchall()

                sc_embed = discord.Embed(
                    title="🛰️ Reconocimiento Global: Bases Enemigas",
                    color=discord.Color.dark_purple(),
                )
                if not rows:
                    sc_embed.description = (
                        "No hay bases enemigas reportadas en ningún mapa."
                    )
                else:
                    for row in rows:
                        threat_stars = "⭐" * row["nivel_amenaza"]
                        notas = row["notas"] or "Sin notas adjuntas."
                        amenaza_texto = (
                            "Máxima/Alfa"
                            if row["nivel_amenaza"] == 5
                            else "Alta"
                            if row["nivel_amenaza"] >= 4
                            else "Media"
                            if row["nivel_amenaza"] == 3
                            else "Baja/FOB"
                        )
                        sc_embed.add_field(
                            name=f"ID: #{row['id']} | Tribu: {row['tribu_enemiga']} {threat_stars}",
                            value=f"**Mapa:** {row['mapa']} | **Lat/Lon:** {row['coordenadas']}\\n**Amenaza ({row['nivel_amenaza']}/5):** {amenaza_texto}\\n**Notas:** {notas}",
                            inline=False,
                        )
                    sc_embed.set_footer(
                        text="Mostrando primeros 5. Genera panel filtrado por mapa usando /scout_list mapa:X"
                    )

                view = ScoutView(
                    self.bot,
                    map_filter=None,
                    page=0,
                    total_rows=len(rows) if rows else 0,
                )
                msg = await canal_scouting.send(embed=sc_embed, view=view)
                await asyncio.sleep(0.5)

                async with aiosqlite.connect(self.bot.db_name) as db:
                    await db.execute(
                        "INSERT INTO scout_messages (channel_id, message_id) VALUES (?, ?)",
                        (canal_scouting.id, msg.id),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando Scouting: {e}")

        # Configuración K4Ultra
        if canal_k4ultra:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["k4ultra"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_k4ultra.send(embed=info_embed)

                k_cog = self.bot.get_cog("K4Ultra")
                if k_cog:
                    embed_k, top_players_k = await k_cog.generate_k4ultra_embed(
                        interaction.guild_id
                    )
                    view_k = __import__(
                        "cogs.k4ultra", fromlist=["K4UltraView"]
                    ).K4UltraView(self.bot, interaction.guild_id, top_players_k)
                    msg = await canal_k4ultra.send(embed=embed_k, view=view_k)
                    await asyncio.sleep(0.5)

                    async with aiosqlite.connect(self.bot.db_name) as db:
                        await db.execute(
                            "INSERT INTO k4ultra_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                            (interaction.guild_id, canal_k4ultra.id, msg.id),
                        )
                        await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando K4Ultra: {e}")

        # Configuración Server Status
        if canal_status:
            try:
                info_embed = discord.Embed(
                    description=INFO_TEXTS["status"],
                    color=discord.Color.from_rgb(43, 45, 49),
                )
                await canal_status.send(embed=info_embed)

                s_cog = self.bot.get_cog("ServerStatus")
                if s_cog:
                    from cogs.server_status import get_guild_servers

                    servers = await get_guild_servers(self.bot, interaction.guild_id)
                    embed_s = await s_cog.get_global_status_embed(servers)
                    msg = await canal_status.send(embed=embed_s)
                    await asyncio.sleep(0.5)

                    async with aiosqlite.connect(self.bot.db_name) as db:
                        await db.execute(
                            "INSERT INTO status_online_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                            (interaction.guild_id, canal_status.id, msg.id),
                        )
                        await db.commit()
            except Exception as e:
                logger.error(f"Error auto-configurando Server Status: {e}")

    @app_commands.command(
        name="wipe_db", description="☢️ BORRA TODOS LOS DATOS (Solo Admin)."
    )
    async def wipe_db(self, interaction: discord.Interaction):
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.** No tienes permisos para usar este comando.",
                ephemeral=True,
            )
            logger.warning(
                f"Intento de WIPE no autorizado por {interaction.user.name} ({interaction.user.id})"
            )
            return

        # Respuesta inicial efímera (sin confirmación extra dada la restricción)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            async with aiosqlite.connect(self.bot.db_name) as db:
                # Borrado de datos (usando DELETE al no existir TRUNCATE en SQLite)
                tables = [
                    "scouts",
                    "scout_messages",
                    "todos",
                    "todo_messages",
                    "dinos",
                    "breeding_messages",
                    "blacklist",
                    "blacklist_messages",
                    "status_messages",
                ]

                guild_id = interaction.guild_id

                for table in tables:
                    await db.execute(
                        f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,)
                    )
                    # Exclusión explícita de `sqlite_sequence` para proteger el autoincremental de datos unificados

                await db.commit()

            await interaction.followup.send(
                "✅ **BASE DE DATOS BORRADA.**\nTodos los registros han sido eliminados y los contadores reiniciados.",
                ephemeral=True,
            )
            logger.warning(f"☢️ BASE DE DATOS BORRADA por {interaction.user.name}")

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error al borrar DB: {e}", ephemeral=True
            )
            logger.error(f"Error en WIPE DB: {e}")

    @app_commands.command(
        name="clear_updates",
        description="🛑 DETIENE ACTUALIZACIONES (Borra dashboards, no datos).",
    )
    async def clear_updates(self, interaction: discord.Interaction):
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.** No tienes permisos para usar este comando.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            async with aiosqlite.connect(self.bot.db_name) as db:
                # Borrado de tablas de mensajes (Dashboards)
                tables = [
                    "scout_messages",
                    "todo_messages",
                    "breeding_messages",
                    "blacklist_messages",
                    "status_messages",
                ]

                guild_id = interaction.guild_id

                for table in tables:
                    await db.execute(
                        f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,)
                    )
                    # Vaciado estructural simple preservando el conteo incremental

                await db.commit()

            await interaction.followup.send(
                "✅ **DASHBOARDS LIMPIOS.** Si los mensajes viejos siguen existiendo en Discord, bórralos a mano.\nEl bot ya LOS HA OLVIDADO y no intentará editarlos más.",
                ephemeral=True,
            )
            logger.info(f"DASHBOARDS LIMPIADOS por {interaction.user.name}")

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error al limpiar dashboards: {e}", ephemeral=True
            )
            logger.error(f"Error en CLEAR UPDATES: {e}")

    @app_commands.command(
        name="log",
        description="Muestra los últimos comandos ejecutados (Sesión Actual).",
    )
    async def log(self, interaction: discord.Interaction):
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.** Necesitas permisos de Administrador.",
                ephemeral=True,
            )
            return

        log_file = self.bot.log_filename
        logs = []

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "EJECUCIDN:" in line or "EJECUCIÓN:" in line:
                        # Format: yyyy-mm-dd hh:mm:ss [INFO] EJECUCIÓN: User='Name' | Cmd='/cmd' | Args=[...]
                        logs.append(line.strip())

            if not logs:
                await interaction.response.send_message(
                    "No hay registros de comandos en esta sesión.", ephemeral=True
                )
            else:
                # Ordenar desde el más reciente
                logs.reverse()
                response_text = "\n".join(logs[:15])  # Límite de 15 registros

                # Formateo en bloque de código
                formatted_text = f"```log\n{response_text}\n```"

                await interaction.response.send_message(formatted_text, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"Error leyendo logs: {e}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Admin(bot))
