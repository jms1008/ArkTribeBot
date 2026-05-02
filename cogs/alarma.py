import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
import logging
import json
from cogs.server_status import get_guild_servers

logger = logging.getLogger("ArkTribeBot")


class AlarmDismissView(discord.ui.View):
    """Vista con botón para eliminar el mensaje de alerta."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Silenciar",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="dismiss_alarm_btn",
    )
    async def dismiss_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            await interaction.message.delete()
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Alarma silenciada.", ephemeral=True
                )
        except Exception:
            pass


async def build_alarmas_embed(bot, guild_id: int, user_id: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔔 PANEL DE ALARMAS ACTIVAS",
        color=discord.Color.from_rgb(255, 100, 0),
    )

    lines = []
    lines.append("Selecciona un mapa en el menú inferior para controlar su alarma.")
    lines.append("")

    async with aiosqlite.connect(bot.db_name) as db:
        c = await db.execute(
            "SELECT map_name FROM map_alarms WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        rows = await c.fetchall()

    if not rows:
        lines.append("## 💤 Estado Actual")
        lines.append("> No tienes ninguna alarma activada ahora.")
    else:
        mapas = [r[0] for r in rows]
        lines.append("## 👀 Mapas Vigilados")
        for m in mapas:
            lines.append(f"> • **{m}**")

    embed.description = "\n".join(lines).strip()
    return embed


class AlarmasPanelView(discord.ui.View):
    """Vista del panel de alarmas. Cada usuario tiene su propia instancia."""

    def __init__(self, bot, servers: list = None):
        super().__init__(timeout=None)
        self.bot = bot

        options = []
        if servers:
            for s in servers[:25]:
                options.append(discord.SelectOption(label=s, value=s))

        if not options:
            options.append(
                discord.SelectOption(label="Sin servidores", value="none")
            )

        self.select_mapa.options = options

    @discord.ui.select(
        placeholder="Selecciona un mapa del clúster...",
        custom_id="alarm_panel_select_map"
    )
    async def select_mapa(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        if select.values[0] == "none":
            await interaction.response.send_message(
                "No hay servidores configurados.", ephemeral=True
            )
            return

        selected = select.values[0]
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        # Comprobar si ya está activada para ofrecer la acción correcta
        async with aiosqlite.connect(self.bot.db_name) as db:
            c = await db.execute(
                "SELECT 1 FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                (guild_id, user_id, selected),
            )
            already_active = await c.fetchone() is not None

        # Vista efímera con acciones directas para ese mapa concreto
        action_view = AlarmActionView(self.bot, selected, already_active, interaction.message)
        status = "🟢 **Activa**" if already_active else "🔴 **Inactiva**"
        await interaction.response.send_message(
            f"📍 Mapa: **{selected}** — Estado: {status}\n"
            f"👉 *Usa los botones para cambiar el estado de la alarma.*",
            view=action_view,
            ephemeral=True,
        )


class AlarmActionView(discord.ui.View):
    """Vista efímera que aparece tras seleccionar un mapa.
    Contiene el mapa seleccionado directamente en la instancia,
    eliminando el bug de estado perdido."""

    def __init__(self, bot, map_name: str, is_active: bool, parent_message: discord.Message = None):
        super().__init__(timeout=60)
        self.bot = bot
        self.map_name = map_name
        self.parent_message = parent_message
        # Desactivar el botón que no aplica
        if is_active:
            self.btn_on.disabled = True
        else:
            self.btn_off.disabled = True

    async def _refresh_parent(self, interaction: discord.Interaction):
        """Actualiza el embed del panel principal para reflejar el cambio."""
        if not self.parent_message:
            return
        try:
            embed = await build_alarmas_embed(
                self.bot, interaction.guild_id, interaction.user.id
            )
            await self.parent_message.edit(embed=embed)
        except Exception as e:
            logger.error(f"[Alarma] Error actualizando panel principal: {e}")

    @discord.ui.button(label="Encender 🔔", style=discord.ButtonStyle.success)
    async def btn_on(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, self.map_name, channel_id),
            )
            await db.commit()

        self.btn_on.disabled = True
        self.btn_off.disabled = False
        await interaction.response.edit_message(
            content=f"🚨 **Alarma activada** para `{self.map_name}`. Recibirás un ping en este canal cuando entre un intruso.",
            view=self,
        )
        await self._refresh_parent(interaction)

    @discord.ui.button(label="Apagar 🔕", style=discord.ButtonStyle.danger)
    async def btn_off(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                (guild_id, user_id, self.map_name),
            )
            await db.commit()

        self.btn_off.disabled = True
        self.btn_on.disabled = False
        await interaction.response.edit_message(
            content=f"🔕 **Alarma desactivada** para `{self.map_name}`.",
            view=self,
        )
        await self._refresh_parent(interaction)


class Alarma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(AlarmasPanelView(self.bot))
        self.check_alarms_loop.start()

    def cog_unload(self):
        self.check_alarms_loop.cancel()

    async def mapa_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        return [
            app_commands.Choice(name=name, value=name)
            for name in servers.keys()
            if current.lower() in name.lower()
        ][:25]

    @app_commands.command(
        name="alarma",
        description="Establece una alarma que te avisará si entra un intruso en un mapa seleccionado.",
    )
    @app_commands.describe(
        mapa="Nombre del mapa a vigilar (ej: Fjordur)",
        estado="Activar (on) o desactivar (off) la alarma",
    )
    @app_commands.choices(
        estado=[
            app_commands.Choice(name="Encendido", value="on"),
            app_commands.Choice(name="Apagado", value="off"),
        ]
    )
    @app_commands.autocomplete(mapa=mapa_autocomplete)
    async def alarma(
        self, interaction: discord.Interaction, mapa: str, estado: str
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id

        try:
            servers = await get_guild_servers(self.bot, guild_id)
            if not servers:
                await interaction.followup.send(
                    "❌ No hay servidores configurados. Usa `/inicio_ark` primero.",
                    ephemeral=True,
                )
                return

            if mapa not in servers:
                await interaction.followup.send(
                    f"❌ El mapa `{mapa}` no existe en la configuración actual.",
                    ephemeral=True,
                )
                return

            async with aiosqlite.connect(self.bot.db_name) as db:
                if estado == "off":
                    await db.execute(
                        "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                        (guild_id, user_id, mapa),
                    )
                    await db.commit()
                    await interaction.followup.send(
                        f"🔕 Alarma para **{mapa}** desactivada.", ephemeral=True
                    )
                else:
                    await db.execute(
                        "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                        (guild_id, user_id, mapa, channel_id),
                    )
                    await db.commit()
                    await interaction.followup.send(
                        f"🚨 **Alarma activada** para `{mapa}`. Te avisaré cuando entre un intruso. 🔔",
                        ephemeral=True,
                    )
        except Exception as e:
            logger.error(f"Error en comando /alarma: {e}")
            await interaction.followup.send(
                f"❌ Ocurrió un error al procesar la alarma: {e}", ephemeral=True
            )

    @app_commands.command(
        name="alarmas",
        description="Abre el panel interactivo rápido de tus alarmas de intrusos.",
    )
    async def alarmas(self, interaction: discord.Interaction):
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        if not servers:
            await interaction.response.send_message(
                "❌ No hay servidores configurados. Usa `/inicio_ark` primero.",
                ephemeral=True,
            )
            return

        server_names = list(servers.keys())
        embed = await build_alarmas_embed(
            self.bot, interaction.guild_id, interaction.user.id
        )
        view = AlarmasPanelView(self.bot, server_names)

        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=False
        )

    @tasks.loop(minutes=1)
    async def check_alarms_loop(self):
        """Comprueba intrusos usando los datos ya guardados en server_status_cache
        por el bucle de status, evitando consultas A2S duplicadas."""
        await self.bot.wait_until_ready()

        try:
            async with aiosqlite.connect(self.bot.db_name) as db:
                db.row_factory = aiosqlite.Row

                # Obtener todos los mapas vigilados (agrupados)
                cursor = await db.execute(
                    "SELECT DISTINCT guild_id, map_name FROM map_alarms"
                )
                watched_maps = await cursor.fetchall()

                if not watched_maps:
                    return

                for row in watched_maps:
                    guild_id = row["guild_id"]
                    map_name = row["map_name"]

                    try:
                        # Leer del caché de status en vez de hacer consulta A2S propia
                        c_cache = await db.execute(
                            "SELECT player_names, player_count FROM server_status_cache WHERE guild_id = ? AND server_name = ?",
                            (guild_id, map_name),
                        )
                        cache_row = await c_cache.fetchone()

                        if not cache_row or not cache_row["player_names"]:
                            continue

                        # Parsear nombres actuales del caché
                        raw_names = cache_row["player_names"]
                        if raw_names == "Nadie conectado." or cache_row["player_count"] == 0:
                            current_names = set()
                        else:
                            current_names = {
                                n.strip()
                                for n in raw_names.split(",")
                                if n.strip()
                            }

                        # Obtener estado anterior
                        c_prev = await db.execute(
                            "SELECT players_json FROM map_last_players WHERE guild_id = ? AND map_name = ?",
                            (guild_id, map_name),
                        )
                        prev_row = await c_prev.fetchone()
                        prev_names = (
                            set(json.loads(prev_row["players_json"]))
                            if prev_row
                            else set()
                        )

                        new_entries = current_names - prev_names

                        if new_entries:
                            # Cargar miembros de la tribu propia
                            c_own = await db.execute(
                                "SELECT members_json FROM k4ultra_fixed_tribes WHERE guild_id = ? AND is_own = 1",
                                (guild_id,),
                            )
                            own_members = set()
                            for row_own in await c_own.fetchall():
                                try:
                                    m_list = json.loads(row_own["members_json"])
                                    for m in m_list:
                                        own_members.add(m.lower())
                                except Exception:
                                    pass

                            intruders = []
                            for name in new_entries:
                                # Ignorar miembros de la tribu propia
                                if name.lower() in own_members:
                                    continue

                                # Comprobar si es un personaje registrado de la tribu
                                c_check = await db.execute(
                                    """SELECT 1 FROM tribe_characters 
                                       WHERE guild_id = ? AND (LOWER(character_name) = LOWER(?) OR LOWER(player_name) = LOWER(?))""",
                                    (guild_id, name, name),
                                )
                                if not await c_check.fetchone():
                                    intruders.append(name)

                            if intruders:
                                c_users = await db.execute(
                                    "SELECT user_id, channel_id FROM map_alarms WHERE guild_id = ? AND map_name = ?",
                                    (guild_id, map_name),
                                )
                                alert_targets = await c_users.fetchall()

                                for target in alert_targets:
                                    try:
                                        u_id = target["user_id"]
                                        ch_id = target["channel_id"]
                                        channel = self.bot.get_channel(
                                            ch_id
                                        ) or await self.bot.fetch_channel(ch_id)
                                        if channel:
                                            intruders_fmt = ", ".join(
                                                [f"**{i}**" for i in intruders]
                                            )
                                            view = AlarmDismissView()
                                            await channel.send(
                                                f"⚠️ <@{u_id}>! **Intruso detectado** en `{map_name}`: {intruders_fmt}",
                                                view=view,
                                            )
                                    except Exception as e:
                                        logger.error(
                                            f"[Alarma] Error enviando alerta a {target['user_id']}: {e}"
                                        )

                        # Actualizar el estado anterior
                        await db.execute(
                            "INSERT OR REPLACE INTO map_last_players (guild_id, map_name, players_json) VALUES (?, ?, ?)",
                            (
                                guild_id,
                                map_name,
                                json.dumps(list(current_names)),
                            ),
                        )
                        await db.commit()

                    except Exception as e:
                        logger.error(
                            f"[Alarma] Error procesando alarma para {map_name} (Guild {guild_id}): {e}"
                        )

        except Exception as e:
            logger.error(f"[Alarma] Error general en check_alarms_loop: {e}")


async def setup(bot):
    async with aiosqlite.connect(bot.db_name) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS map_alarms (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                map_name TEXT NOT NULL,
                channel_id INTEGER,
                PRIMARY KEY(guild_id, user_id, map_name)
            )
        """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS map_last_players (
                guild_id INTEGER NOT NULL,
                map_name TEXT NOT NULL,
                players_json TEXT,
                PRIMARY KEY(guild_id, map_name)
            )
        """
        )
        await db.commit()
    await bot.add_cog(Alarma(bot))
