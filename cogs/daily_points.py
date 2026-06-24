import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.i18n import resolve_lang, t

logger = logging.getLogger("ArkTribeBot")

# Configuración de zonas horarias soportadas
TIMEZONES = {"es": ZoneInfo("Europe/Madrid"), "mx": ZoneInfo("America/Mexico_City")}

# URLs de voto de fallback (si el servidor no ha configurado las suyas propias)
DEFAULT_VOTE_URLS = [
    "https://ark-servers.net/server/388872/",
    "https://ark-servers.net/server/388875/",
    "https://ark-servers.net/server/388871/",
]


def parse_vote_urls(vote_urls_str: str) -> list[str]:
    """Parsea el campo vote_urls del formato 'MapaName|URL,Map2|URL2' y devuelve solo las URLs."""
    if not vote_urls_str:
        return DEFAULT_VOTE_URLS
    urls = []
    for entry in vote_urls_str.split(","):
        entry = entry.strip()
        if "|" in entry:
            urls.append(entry.split("|", 1)[1].strip())
        elif entry.startswith("http"):
            urls.append(entry)
    return urls if urls else DEFAULT_VOTE_URLS


class DailyPointsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Completado",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="daily_points_completado_btn",
    )
    async def completado_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        now_utc = datetime.now(ZoneInfo("UTC"))
        # Uso de zona horaria de España para la marca visual del log en el DM
        today_str = now_utc.astimezone(TIMEZONES["es"]).strftime("%d/%m/%Y")

        await interaction.response.edit_message(
            content=f"✅ **¡Votación Completada!** ({today_str})\n\n🛒 _Recuerda entrar al juego y usar la tienda para reclamar tus puntos antes de que caduquen._",
            view=None,
        )


class DailyPoints(commands.Cog):
    # Grupo unificado de puntos diarios (antes /puntos_diarios, /config_puntos).
    puntos = app_commands.Group(name="puntos", description="Recordatorios de puntos diarios de voto.")

    def __init__(self, bot):
        self.bot = bot
        self.points_loop.start()

    def cog_unload(self):
        self.points_loop.cancel()

    @puntos.command(
        name="mi",
        description="Activa o desactiva tus notificaciones diarias para votar los mapas.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        estado="Activar (on) o desactivar (off)",
        hora="Hora del recordatorio (0-23) [Defecto: 8]",
        zona="Zona horaria [Defecto: España]",
    )
    @app_commands.choices(
        estado=[
            app_commands.Choice(name="Activar (On)", value="on"),
            app_commands.Choice(name="Desactivar (Off)", value="off"),
        ],
        zona=[
            app_commands.Choice(name="España", value="es"),
            app_commands.Choice(name="México", value="mx"),
        ],
    )
    async def puntos_diarios(
        self,
        interaction: discord.Interaction,
        estado: app_commands.Choice[str],
        hora: int = 8,
        zona: app_commands.Choice[str] = None,
    ):
        user_id = interaction.user.id
        zona_val = zona.value if zona else "es"
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", user_id)

        if hora < 0 or hora > 23:
            await interaction.response.send_message(t("puntos.cmd.hour_invalid", lang), ephemeral=True)
            return

        db = self.bot.db
        # Verificar si el sistema está activo para este servidor
        if interaction.guild_id:
            row = await db.fetchone(
                "SELECT daily_points_enabled FROM guild_config WHERE guild_id = ?",
                (interaction.guild_id,),
            )
            if row and row["daily_points_enabled"] == 0:
                await interaction.response.send_message(t("puntos.cmd.disabled_server", lang), ephemeral=True)
                return

        if estado.value == "on":
            try:
                await db.execute(
                    """
                    INSERT INTO daily_points_users (guild_id, user_id, alert_hour, timezone, last_sent_date)
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        alert_hour=excluded.alert_hour,
                        timezone=excluded.timezone
                    """,
                    (interaction.guild_id, user_id, hora, zona_val),
                )
                await db.commit()

                zona_nombre = t(f"puntos.zone.{zona_val}", lang)
                await interaction.response.send_message(
                    t("puntos.cmd.enabled", lang, hora=hora, zona=zona_nombre), ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    t("puntos.cmd.enable_error", lang, err=e), ephemeral=True
                )
        else:
            try:
                await db.execute(
                    "DELETE FROM daily_points_users WHERE user_id = ? AND guild_id = ?",
                    (user_id, interaction.guild_id),
                )
                await db.commit()
                await interaction.response.send_message(t("puntos.cmd.disabled", lang), ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(
                    t("puntos.cmd.disable_error", lang, err=e), ephemeral=True
                )

    @puntos.command(
        name="config",
        description="[Admin] Activa/desactiva puntos diarios para el servidor o edita los enlaces de voto.",
    )
    @app_commands.describe(
        estado="Activar o desactivar el sistema de puntos diarios para todos en este servidor.",
        vote_links="URLs de voto (Formato: 'Mapa1|URL1,Mapa2|URL2'). Deja vacío para no cambiar.",
    )
    @app_commands.choices(
        estado=[
            app_commands.Choice(name="Activar (On)", value="on"),
            app_commands.Choice(name="Desactivar (Off)", value="off"),
        ]
    )
    async def config_puntos(
        self,
        interaction: discord.Interaction,
        estado: app_commands.Choice[str] = None,
        vote_links: str = None,
    ):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        guild_id = interaction.guild_id
        cambios = []
        db = self.bot.db

        if estado is not None:
            enabled = 1 if estado.value == "on" else 0
            await db.execute(
                """
                INSERT INTO guild_config (guild_id, daily_points_enabled) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET daily_points_enabled = excluded.daily_points_enabled
                """,
                (guild_id, enabled),
            )
            cambios.append(t("puntos.config.sys_on" if enabled else "puntos.config.sys_off", lang))

        if vote_links is not None:
            await db.execute(
                """
                INSERT INTO guild_config (guild_id, vote_urls) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET vote_urls = excluded.vote_urls
                """,
                (guild_id, vote_links),
            )
            # Mostrar los enlaces parseados para confirmación visual
            parsed = parse_vote_urls(vote_links)
            links_fmt = "\n".join([f"{i + 1}️⃣ {url}" for i, url in enumerate(parsed)])
            cambios.append(t("puntos.config.urls_updated", lang, links=links_fmt))

        await db.commit()

        if not cambios:
            # Sin args: mostrar estado actual
            row = await db.fetchone(
                "SELECT daily_points_enabled, vote_urls FROM guild_config WHERE guild_id = ?",
                (guild_id,),
            )
            enabled_str = t(
                "puntos.config.active"
                if (not row or row["daily_points_enabled"] != 0)
                else "puntos.config.inactive",
                lang,
            )
            current_urls = parse_vote_urls(row["vote_urls"] if row else None)
            urls_str = "\n".join([f"{i + 1}️⃣ {url}" for i, url in enumerate(current_urls)])
            await interaction.response.send_message(
                t("puntos.config.status", lang, enabled=enabled_str, urls=urls_str), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t("puntos.config.updated", lang, changes="\n".join(cambios)), ephemeral=True
            )

    @tasks.loop(minutes=1)
    async def points_loop(self):
        await self.bot.wait_until_ready()

        now_utc = datetime.now(ZoneInfo("UTC"))
        db = self.bot.db

        users = await db.fetchall(
            "SELECT guild_id, user_id, alert_hour, timezone, last_sent_date FROM daily_points_users"
        )
        if not users:
            return

        # Cargar todos los guild_config para evitar múltiples queries por usuario
        cfg_rows = await db.fetchall("SELECT guild_id, daily_points_enabled, vote_urls FROM guild_config")
        guild_configs = {row["guild_id"]: row for row in cfg_rows}

        users_to_notify: list[tuple[int, int, str]] = []

        for u in users:
            try:
                g_id = u["guild_id"]
                # Si el sistema está desactivado en ese guild, saltarse
                if g_id in guild_configs and guild_configs[g_id]["daily_points_enabled"] == 0:
                    continue

                tz_key = u["timezone"] if u["timezone"] in TIMEZONES else "es"
                tz = TIMEZONES[tz_key]
                user_time = now_utc.astimezone(tz)

                target_hour = u["alert_hour"] if u["alert_hour"] is not None else 8
                current_date_str = user_time.strftime("%Y-%m-%d")

                if user_time.hour == target_hour and u["last_sent_date"] != current_date_str:
                    users_to_notify.append((u["user_id"], g_id, current_date_str))
            except Exception as e:
                logger.error(
                    f"[DailyPoints] Error calculando hora para usuario {u['user_id']} en guild {u['guild_id']}: {e}"
                )

        if not users_to_notify:
            return

        for uid, gid, date_str in users_to_notify:
            try:
                user_obj = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                if not user_obj:
                    continue

                cfg = guild_configs.get(gid)
                vote_urls_str = cfg["vote_urls"] if cfg else None

                vote_links = parse_vote_urls(vote_urls_str)
                links_block = "\n".join([f"{i + 1}️⃣ {url}" for i, url in enumerate(vote_links)])

                message_content = (
                    "🌅 ¡Buenas! Es hora de reclamar tus puntos diarios de los mapas.\n\n"
                    f"🔗 **Enlaces para votar:**\n{links_block}\n\n"
                    "*(Para dejar de recibir estos mensajes, usa `/puntos mi estado:off` en el servidor).* "
                )

                view = DailyPointsView()
                await user_obj.send(message_content, view=view)

                # Registro de notificación diaria enviada en base de datos
                await db.execute(
                    "UPDATE daily_points_users SET last_sent_date = ? WHERE user_id = ? AND guild_id = ?",
                    (date_str, uid, gid),
                )
            except discord.Forbidden:
                logger.warning(f"[DailyPoints] No pude enviar DM a {uid}. Posiblemente tiene DMs cerrados.")
            except Exception as e:
                logger.error(f"[DailyPoints] Error enviando recordatorio a {uid} (Guild {gid}): {e}")

        await db.commit()


async def setup(bot):
    await bot.add_cog(DailyPoints(bot))
