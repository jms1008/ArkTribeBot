import asyncio
import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from utils import bus, i18n
from utils.i18n import t

logger = logging.getLogger("ArkTribeBot")


class Admin(commands.Cog):
    # Grupo unificado de administración (antes /config, /idioma, /wipe_db,
    # /clear_updates, /log, /bind_k4ultra, /db_backup). /inicio_ark se mantiene
    # suelto como comando de arranque canónico.
    admin = app_commands.Group(name="admin", description="Administración y mantenimiento del bot.")

    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        # No hay tareas en segundo plano
        pass

    @admin.command(
        name="bind",
        description="[Admin] Asocia un mensaje existente al dashboard de K4Ultra.",
    )
    @app_commands.describe(
        message_id="ID del mensaje a asociar",
        channel_id="Opcional. ID del canal si el mensaje está en otro sitio.",
    )
    async def bind_k4ultra(self, interaction: discord.Interaction, message_id: str, channel_id: str = None):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        try:
            msg_id_int = int(message_id)

            # Uso del canal actual si no se provee ID
            if channel_id:
                ch_id_int = int(channel_id)
                target_channel = self.bot.get_channel(ch_id_int) or await self.bot.fetch_channel(ch_id_int)
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

        # La tabla k4ultra_messages se crea en db/schema.py (init_db).
        await self.bot.db.execute(
            "INSERT INTO k4ultra_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (interaction.guild_id, ch_id_int, msg_id_int),
        )
        await self.bot.db.commit()

        # Generación del primer embed
        from cogs.k4ultra import K4UltraView

        k_cog = self.bot.get_cog("K4Ultra")
        if k_cog:
            pages, top_players, k4_aliases = await k_cog.generate_k4ultra_embed(interaction.guild_id)
            view = K4UltraView(self.bot, interaction.guild_id, top_players, k4_aliases)
            await message.edit(embed=pages[0], view=view)

        await interaction.response.send_message(
            f"✅ Mensaje `{message_id}` del canal `<#{ch_id_int}>` asociado a K4Ultra con éxito.",
            ephemeral=True,
        )

    @admin.command(
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
        lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        guild_id = interaction.guild_id

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

        db = self.bot.db
        if updates:
            sql = f"UPDATE guild_config SET {', '.join(updates)} WHERE guild_id = ?"
            params.append(guild_id)
            await db.execute(sql, tuple(params))
            await db.commit()
            await interaction.response.send_message(
                t("admin.config.updated", lang), ephemeral=True
            )
        else:
            await interaction.response.defer(ephemeral=False)

        # Consultar configuración actual para el embed
        config = await db.fetchone("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))

        # Miembros registrados
        count_res = await db.fetchone(
            "SELECT COUNT(*) AS n FROM tribe_characters WHERE guild_id = ?", (guild_id,)
        )
        num_miembros = count_res["n"] if count_res else 0

        if not config:
            target = interaction.followup.send if not updates else interaction.edit_original_response
            await target(content=t("admin.config.not_setup", lang))
            return

        embed = build_config_embed(config, num_miembros, guild_id, lang)
        await interaction.followup.send(embed=embed)

    @admin.command(
        name="idioma",
        description="[Admin] Cambia el idioma del bot en este servidor (Español / Inglés).",
    )
    @app_commands.describe(modo="Idioma y alcance que se aplicará en este servidor.")
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="🇪🇸 Español", value=i18n.MODE_ES),
            app_commands.Choice(name="🇬🇧 English (solo dashboards)", value=i18n.MODE_EN_PERIODIC),
            app_commands.Choice(name="🇬🇧 English (todo / everything)", value=i18n.MODE_EN_TOTAL),
        ]
    )
    async def idioma(self, interaction: discord.Interaction, modo: app_commands.Choice[str]):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("idioma.denied", "es"), ephemeral=True)
            return

        guild_id = interaction.guild_id
        mode = modo.value

        db = self.bot.db
        # Upsert: el guild puede no tener fila aún si no se ejecutó /inicio_ark.
        await db.execute(
            "INSERT INTO guild_config (guild_id, language) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET language = excluded.language",
            (guild_id, mode),
        )
        await db.commit()

        # Invalidar la caché para que dashboards y comandos reflejen el cambio ya.
        i18n.invalidate_lang_cache(guild_id)

        # Refresco inmediato de los dashboards con bus de eventos: se repintan en el
        # nuevo idioma sin esperar al loop periódico. Los paneles sin bus (status,
        # k4ultra, alarmas) se actualizan en su próximo ciclo/interacción.
        for event in (
            bus.BLACKLIST_UPDATED,
            bus.KDA_UPDATED,
            bus.SCOUTING_UPDATED,
            bus.TODO_UPDATED,
            bus.BREEDING_UPDATED,
        ):
            self.bot.dispatch(event, guild_id)

        # Confirmación en el idioma de comando del nuevo modo (EN solo si total).
        conf_lang = "en" if mode == i18n.MODE_EN_TOTAL else "es"
        await interaction.response.send_message(t(f"idioma.set.{mode}", conf_lang), ephemeral=True)

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
            await ctx.send(f"✅ Se han sincronizado **{len(synced)}** comandos globalmente.")
        elif spec == "clear":
            await ctx.send("🗑️ **Limpiando comandos en este servidor...**")
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send("✅ Comandos de servidor eliminados (se usarán los globales).")
        else:
            await ctx.send(f"🔄 **Sincronizando comandos en '{ctx.guild.name}'...**")
            try:
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(
                    f"✅ **{len(synced)}** comandos sincronizados instantáneamente en este servidor."
                )
                logger.info(f"Comandos sincronizados manualmente en {ctx.guild.name} ({ctx.guild.id})")
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

        db = self.bot.db
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

        # Consultar configuración final para el embed (asegurar datos frescos)
        config_fresh = await db.fetchone("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        count_res = await db.fetchone(
            "SELECT COUNT(*) AS n FROM tribe_characters WHERE guild_id = ?", (guild_id,)
        )
        num_miembros = count_res["n"] if count_res else 0

        if config_fresh:
            cfg_lang = await i18n.resolve_lang(self.bot, guild_id, "command", interaction.user.id)
            embed = build_config_embed(config_fresh, num_miembros, guild_id, cfg_lang)
            embed.title = "✅ ArkTribeBot Configurado Correctamente"
            embed.description = (
                "El servidor ha sido vinculado con éxito. Aquí tienes el resumen de tu configuración:"
            )
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("✅ Configuración guardada correctamente.")

        # ------------------- AUTO-SETUP DE CANALES OPCIONALES -------------------
        # Enviar info de SOS al canal SOS obligatorio
        from cogs.management import get_info_texts

        setup_lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "periodic")
        info_sos_embed = discord.Embed(
            description=get_info_texts(setup_lang)["sos"], color=discord.Color.from_rgb(43, 45, 49)
        )
        try:
            await canal_sos.send(embed=info_sos_embed)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error enviando info SOS: {e}")

        # Delegación Desacoplada a Cogs
        canales = {
            "Management": canal_todo,
            "Breeding": canal_crianza,
            "Warfare": canal_blacklist,
            "Scouting": canal_scouting,
            "K4Ultra": canal_k4ultra,
            "ServerStatus": canal_status,
        }

        for cog_name, ch in canales.items():
            if ch:
                try:
                    cog = self.bot.get_cog(cog_name)
                    if cog and hasattr(cog, "setup_dashboard"):
                        await cog.setup_dashboard(interaction.guild_id, ch)
                except Exception as e:
                    logger.error(f"Error inicializando dashboard de {cog_name}: {e}")

    @admin.command(name="wipe", description="☢️ BORRA TODOS LOS DATOS (Solo Admin).")
    async def wipe_db(self, interaction: discord.Interaction):
        lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            logger.warning(
                f"Intento de WIPE no autorizado por {interaction.user.name} ({interaction.user.id})"
            )
            return

        # Respuesta inicial efímera (sin confirmación extra dada la restricción)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # Borrado de datos (usando DELETE al no existir TRUNCATE en SQLite).
            # Lista COMPLETA de tablas con datos del guild — debe cumplir el
            # contrato del comando ("borra TODOS los datos"). Se excluye a
            # propósito `guild_config` (canales/roles/idioma) para que el bot
            # siga configurado tras el wipe, y `sqlite_sequence`.
            tables = [
                # Módulos de datos
                "scouts",
                "todos",
                "dinos",
                "blacklist",
                "breeding_alarms",
                # K4Ultra / inteligencia
                "k4ultra_playtime",
                "k4ultra_sessions",
                "k4ultra_relationships",
                "k4ultra_fixed_tribes",
                "k4ultra_aliases",
                "k4ultra_tribe_names",
                "k4ultra_players_log",
                "k4ultra_snapshots",
                "k4ultra_config",
                "player_identities_link",
                # Perfiles de miembros y KDA
                "tribe_profiles",
                "tribe_characters",
                "tribe_kda",
                "tribe_death_log",
                # Eventos y alarmas
                "events",
                "event_options",
                "map_alarms",
                "map_last_players",
                "alarm_alert_messages",
                # Preferencias de usuario
                "daily_points_users",
                "user_language",
                # Cachés y registros de dashboards
                "server_status_cache",
                "guild_loop_state",
                "scout_messages",
                "todo_messages",
                "breeding_messages",
                "blacklist_messages",
                "status_online_messages",
                "status_messages",
                "kda_messages",
                "k4ultra_messages",
            ]

            guild_id = interaction.guild_id
            db = self.bot.db
            for table in tables:
                try:
                    await db.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
                except aiosqlite.OperationalError as e:
                    # Tabla inexistente en instalaciones antiguas — tolerable.
                    logger.debug(f"[Wipe] Tabla {table} omitida: {e}")
            await db.commit()

            await interaction.followup.send(t("admin.wipe.done", lang), ephemeral=True)
            logger.warning(f"☢️ BASE DE DATOS BORRADA por {interaction.user.name}")

        except Exception as e:
            await interaction.followup.send(t("admin.wipe.error", lang, err=e), ephemeral=True)
            logger.error(f"Error en WIPE DB: {e}")

    @admin.command(
        name="clear",
        description="🛑 DETIENE ACTUALIZACIONES (Borra dashboards, no datos).",
    )
    async def clear_updates(self, interaction: discord.Interaction):
        lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # Borrado de TODAS las tablas de registros de dashboards. Si falta
            # alguna aquí, ese panel seguiría editándose sobre mensajes viejos
            # tras el clear (bug que afectaba a ranking y k4ultra).
            tables = [
                "scout_messages",
                "todo_messages",
                "breeding_messages",
                "blacklist_messages",
                "status_online_messages",
                "status_messages",
                "kda_messages",
                "k4ultra_messages",
            ]

            guild_id = interaction.guild_id
            db = self.bot.db
            for table in tables:
                try:
                    await db.execute(f"DELETE FROM {table} WHERE guild_id = ?", (guild_id,))
                except aiosqlite.OperationalError as e:
                    logger.debug(f"[Clear] Tabla {table} omitida: {e}")
            await db.commit()

            await interaction.followup.send(t("admin.clear.done", lang), ephemeral=True)
            logger.info(f"DASHBOARDS LIMPIADOS por {interaction.user.name}")

        except Exception as e:
            await interaction.followup.send(t("admin.clear.error", lang, err=e), ephemeral=True)
            logger.error(f"Error en CLEAR UPDATES: {e}")

    @admin.command(
        name="log",
        description="Muestra los últimos comandos ejecutados (Sesión Actual).",
    )
    async def log(self, interaction: discord.Interaction):
        lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        # Verificación de permisos de administrador
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        log_file = self.bot.log_filename
        logs = []

        try:
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    if "EJECUCIDN:" in line or "EJECUCIÓN:" in line:
                        # Format: yyyy-mm-dd hh:mm:ss [INFO] EJECUCIÓN: User='Name' | Cmd='/cmd' | Args=[...]
                        logs.append(line.strip())

            if not logs:
                await interaction.response.send_message(t("admin.log.empty", lang), ephemeral=True)
            else:
                # Ordenar desde el más reciente
                logs.reverse()
                response_text = "\n".join(logs[:15])  # Límite de 15 registros

                # Formateo en bloque de código
                formatted_text = f"```log\n{response_text}\n```"

                await interaction.response.send_message(formatted_text, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(t("admin.log.error", lang, err=e), ephemeral=True)

    @admin.command(name="backup", description="[Admin] Genera un backup manual de la base de datos.")
    async def db_backup(self, interaction: discord.Interaction):
        import os

        from cogs.backup import _do_backup, _prune_old_backups

        lang = await i18n.resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            target = _do_backup(self.bot.db_name)
            removed = _prune_old_backups()
            size_kb = os.path.getsize(target) / 1024
            await interaction.followup.send(
                t("admin.backup.done", lang, file=os.path.basename(target), size=f"{size_kb:.1f}", removed=removed),
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"[Backup] Falló /admin backup: {e}")
            await interaction.followup.send(t("admin.backup.error", lang, err=e), ephemeral=True)


def build_config_embed(
    config: aiosqlite.Row, num_miembros: int, guild_id: int, lang: str = "es"
) -> discord.Embed:
    """Construye un embed premium con la configuración del servidor."""
    embed = discord.Embed(
        title=t("config.title", lang),
        description=t("config.subtitle", lang),
        color=discord.Color.from_rgb(35, 135, 80),  # Verde oscuro premium
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=t("config.footer", lang, guild_id=guild_id))

    embed.add_field(
        name=t("config.f.channels", lang),
        value=t(
            "config.channels_value",
            lang,
            sos=config["sos_channel_id"],
            log=config["log_channel_id"],
            upload=config["upload_channel_id"],
        ),
        inline=False,
    )

    embed.add_field(
        name=t("config.f.auth", lang),
        value=(
            t("config.auth_full", lang, owner=config["bot_owner_id"], role=config["admin_role_id"])
            if config["admin_role_id"]
            else t("config.auth_norole", lang)
        ),
        inline=True,
    )

    embed.add_field(
        name=t("config.f.modules", lang),
        value=t(
            "config.modules_value",
            lang,
            interval=config["update_interval"],
            status="✅ ON" if config["daily_points_enabled"] else "❌ OFF",
        ),
        inline=True,
    )

    embed.add_field(
        name=t("config.f.tribe", lang),
        value=t("config.tribe_value", lang, n=num_miembros),
        inline=True,
    )

    bm_urls = config["battlemetrics_urls"] or t("config.no_servers_linked", lang)
    if len(bm_urls) > 1024:
        bm_urls = bm_urls[:1021] + "..."
    embed.add_field(
        name=t("config.f.cluster", lang),
        value=f"```\n{bm_urls}\n```",
        inline=False,
    )
    return embed


async def setup(bot):
    await bot.add_cog(Admin(bot))
