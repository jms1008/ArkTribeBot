import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger("ArkTribeBot")

# Configuración de zonas horarias soportadas
TIMEZONES = {"es": ZoneInfo("Europe/Madrid"), "mx": ZoneInfo("America/Mexico_City")}


class DailyPointsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Completado",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="daily_points_completado_btn",
    )
    async def completado_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        now_utc = datetime.now(ZoneInfo("UTC"))
        # Uso de zona horaria de España para la marca visual del log en el DM
        today_str = now_utc.astimezone(TIMEZONES["es"]).strftime("%d/%m/%Y")

        await interaction.response.edit_message(
            content=f"✅ **¡Votación Completada!** ({today_str})\n\n🛒 _Recuerda entrar al juego y usar la tienda para reclamar tus puntos antes de que caduquen._",
            view=None,
        )


class DailyPoints(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.points_loop.start()

    def cog_unload(self):
        self.points_loop.cancel()

    @app_commands.command(
        name="puntos_diarios",
        description="Activa o desactiva las notificaciones diarias para votar los mapas.",
    )
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

        if hora < 0 or hora > 23:
            await interaction.response.send_message(
                "❌ La hora debe estar entre 0 y 23.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            if estado.value == "on":
                try:
                    await db.execute(
                        """
                        INSERT INTO daily_points_users (user_id, alert_hour, timezone, last_sent_date) 
                        VALUES (?, ?, ?, NULL)
                        ON CONFLICT(user_id) DO UPDATE SET 
                            alert_hour=excluded.alert_hour,
                            timezone=excluded.timezone
                    """,
                        (user_id, hora, zona_val),
                    )
                    await db.commit()

                    zona_nombre = "España" if zona_val == "es" else "México"
                    await interaction.response.send_message(
                        f"✅ **Notificaciones activadas.** Te avisaré todos los días a las **{hora:02d}:00** (Hora de {zona_nombre}) para votar.",
                        ephemeral=True,
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Error al activar: {e}", ephemeral=True
                    )
            else:
                try:
                    await db.execute(
                        "DELETE FROM daily_points_users WHERE user_id = ?", (user_id,)
                    )
                    await db.commit()
                    await interaction.response.send_message(
                        "🔕 **Notificaciones desactivadas.** Ya no te enviaré mensajes diarios.",
                        ephemeral=True,
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Error al desactivar: {e}", ephemeral=True
                    )

    @tasks.loop(minutes=1)
    async def points_loop(self):
        await self.bot.wait_until_ready()

        now_utc = datetime.now(ZoneInfo("UTC"))

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT user_id, alert_hour, timezone, last_sent_date FROM daily_points_users"
            )
            users = await cursor.fetchall()

            if not users:
                return

            users_to_notify = []

            for u in users:
                try:
                    tz_key = u["timezone"] if u["timezone"] in TIMEZONES else "es"
                    tz = TIMEZONES[tz_key]
                    user_time = now_utc.astimezone(tz)

                    target_hour = u["alert_hour"] if u["alert_hour"] is not None else 8

                    current_date_str = user_time.strftime("%Y-%m-%d")

                    # Comprobación de coincidencia con la hora objetivo configurada
                    if user_time.hour == target_hour:
                        if u["last_sent_date"] != current_date_str:
                            users_to_notify.append((u["user_id"], current_date_str))
                except Exception as e:
                    logger.error(
                        f"[DailyPoints] Error calculando hora para usuario {u['user_id']}: {e}"
                    )

            if users_to_notify:
                message_content = (
                    "🌅 ¡Buenas! Es hora de reclamar tus puntos diarios de los mapas.\n\n"
                    "🔗 **Enlaces para votar:**\n"
                    "1️⃣ https://ark-servers.net/server/388872/\n"
                    "2️⃣ https://ark-servers.net/server/388875/\n"
                    "3️⃣ https://ark-servers.net/server/388871/\n\n"
                    "*(Para dejar de recibir estos mensajes, usa `/puntos_diarios off` en el servidor).* "
                )

                for uid, date_str in users_to_notify:
                    try:
                        user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                        if user:
                            view = DailyPointsView()
                            await user.send(message_content, view=view)

                        # Registro de notificación diaria enviada en base de datos
                        await db.execute(
                            "UPDATE daily_points_users SET last_sent_date = ? WHERE user_id = ?",
                            (date_str, uid),
                        )
                    except discord.Forbidden:
                        logger.warning(
                            f"[DailyPoints] No pude enviar DM a {uid}. Posiblemente tiene DMs cerrados."
                        )
                    except Exception as e:
                        logger.error(
                            f"[DailyPoints] Error enviando recordatorio a {uid}: {e}"
                        )

                await db.commit()


async def setup(bot):
    await bot.add_cog(DailyPoints(bot))
