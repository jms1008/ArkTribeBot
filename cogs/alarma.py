import json
import logging
from collections import Counter

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.server_status import get_guild_servers
from utils.i18n import resolve_lang, t

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
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
            if not interaction.response.is_done():
                await interaction.response.send_message("Alarma silenciada.", ephemeral=True)
        except Exception as e:
            logger.debug(f"[Alarma] Dismiss falló (mensaje ya eliminado o sin permisos): {e}")


async def _get_trusted_members(bot, guild_id: int) -> set[str]:
    """Devuelve el set de jugadores (en lowercase) que NO deben disparar alarma:
    miembros de la tribu propia + miembros de tribus marcadas como aliadas.

    Se lee de `k4ultra_fixed_tribes` filtrando por `is_own = 1 OR is_ally = 1`.
    """
    trusted: set[str] = set()
    rows = await bot.db.fetchall(
        "SELECT members_json FROM k4ultra_fixed_tribes "
        "WHERE guild_id = ? AND (is_own = 1 OR is_ally = 1)",
        (guild_id,),
    )
    for row in rows:
        try:
            members = json.loads(row["members_json"])
            for m in members:
                trusted.add(m.lower())
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"[Alarma] members_json inválido en tribu fijada: {e}")
    return trusted


async def _fetch_user_alarms(bot, guild_id: int, user_id: int) -> list[dict]:
    """Alarmas de un usuario concreto en un guild. Usado por el Select para
    saber qué mapas ya tiene activos el usuario que interactúa."""
    if getattr(bot, "db", None) is not None:
        rows = await bot.db.fetchall(
            "SELECT map_name, channel_id FROM map_alarms WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
    else:
        async with aiosqlite.connect(bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            c = await db.execute(
                "SELECT map_name, channel_id FROM map_alarms WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )
            rows = await c.fetchall()
    return [{"map_name": r["map_name"], "channel_id": r["channel_id"]} for r in rows]


async def _fetch_guild_alarms(bot, guild_id: int) -> list[dict]:
    """Todas las alarmas del guild (de todos los usuarios). Usado por el embed
    del panel compartido."""
    if getattr(bot, "db", None) is not None:
        rows = await bot.db.fetchall(
            "SELECT user_id, map_name, channel_id FROM map_alarms WHERE guild_id = ? ORDER BY map_name, user_id",
            (guild_id,),
        )
    else:
        async with aiosqlite.connect(bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            c = await db.execute(
                "SELECT user_id, map_name, channel_id FROM map_alarms WHERE guild_id = ? ORDER BY map_name, user_id",
                (guild_id,),
            )
            rows = await c.fetchall()
    return [{"user_id": r["user_id"], "map_name": r["map_name"], "channel_id": r["channel_id"]} for r in rows]


async def build_alarmas_embed(bot, guild_id: int) -> discord.Embed:
    """Construye el embed compartido del panel de alarmas del servidor.

    Patrón visual unificado (Blacklist/Scouting/Ranking):
    - Header en mayúscula
    - Badges de contador (🗺️ N · 👥 M)
    - Sección con items en formato ``#NN 🟢 **mapa** + watchers``
    - Footer con hint del comando
    """
    lang = await resolve_lang(bot, guild_id, "periodic")
    embed = discord.Embed(
        title=t("alarm.title", lang),
        color=discord.Color.from_rgb(255, 100, 0),
    )

    alarms = await _fetch_guild_alarms(bot, guild_id)
    logger.info(f"[Alarma] build_alarmas_embed guild={guild_id} → {len(alarms)} alarmas activas")

    if not alarms:
        embed.description = t("alarm.empty", lang)
        embed.set_footer(text=t("alarm.empty_footer", lang))
        return embed

    # Agrupar por mapa.
    by_map: dict[str, list[int]] = {}
    for a in alarms:
        by_map.setdefault(a["map_name"], []).append(a["user_id"])

    total_watchers = sum(len(v) for v in by_map.values())
    unique_watchers = len({uid for uids in by_map.values() for uid in uids})

    lines: list[str] = [
        t("alarm.badges", lang, maps=len(by_map), unique=unique_watchers, subs=total_watchers),
        "",
        t("alarm.section", lang),
    ]

    for idx, map_name in enumerate(sorted(by_map.keys()), start=1):
        watchers = by_map[map_name]
        mentions = " · ".join(f"<@{uid}>" for uid in watchers)
        count = len(watchers)
        word = t("alarm.watcher_one", lang) if count == 1 else t("alarm.watcher_many", lang)
        lines.append(t("alarm.map_line", lang, idx=idx, map=map_name, count=count, word=word))
        lines.append(f"  └ {mentions}")

    embed.description = "\n".join(lines).strip()
    embed.set_footer(text=t("alarm.footer", lang))
    return embed


class AlarmasPanelView(discord.ui.View):
    """Vista del panel COMPARTIDO de alarmas de la tribu.

    El panel es público (visible para todos los miembros) y refleja el estado
    global. Cuando un miembro pulsa el Select, se le abre una vista efímera
    con el estado de SUS alarmas para ese mapa concreto.

    El Select NO marca mapas como activos porque el panel lo ve gente con
    configuraciones distintas — el estado individual aparece al pulsar.
    """

    def __init__(self, bot, servers: list = None, lang: str = "es"):
        super().__init__(timeout=None)
        self.bot = bot
        self.lang = lang

        # Etiquetas traducibles de la vista.
        self.select_mapa.placeholder = t("alarm.select_placeholder", lang)
        self.refresh_btn.label = t("alarm.btn.refresh", lang)

        options = []
        if servers:
            for s in servers[:25]:
                options.append(discord.SelectOption(label=s, value=s))

        if not options:
            options.append(discord.SelectOption(label="Sin servidores", value="none"))

        self.select_mapa.options = options

    @discord.ui.select(placeholder="Selecciona un mapa del clúster...", custom_id="alarm_panel_select_map")
    async def select_mapa(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "none":
            await interaction.response.send_message("No hay servidores configurados.", ephemeral=True)
            return

        selected = select.values[0]
        guild_id = interaction.guild_id
        user_id = interaction.user.id

        # Comprobar si ya está activada para ofrecer la acción correcta
        already_active = (
            await self.bot.db.fetchone(
                "SELECT 1 FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                (guild_id, user_id, selected),
            )
            is not None
        )

        # Vista efímera con acciones directas para ese mapa concreto
        action_view = AlarmActionView(self.bot, selected, already_active, interaction.message)
        status = "🟢 **Activa**" if already_active else "🔴 **Inactiva**"
        await interaction.response.send_message(
            f"📍 Mapa: **{selected}** — Estado: {status}\n"
            f"👉 *Usa los botones para cambiar el estado de la alarma.*",
            view=action_view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Refrescar",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        custom_id="alarm_panel_refresh",
    )
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vuelve a leer la DB y reconstruye el embed compartido + el Select."""
        guild_id = interaction.guild_id

        servers = await get_guild_servers(self.bot, guild_id)
        server_names = list(servers.keys()) if servers else []

        # El panel es compartido: el embed muestra estado global, el Select
        # queda neutro (sin marca de "activa" porque el panel lo ven varios
        # usuarios con configs distintas). Cada usuario verá su estado
        # personal en el ephemeral que aparece al pulsar.
        lang = await resolve_lang(self.bot, guild_id, "periodic")
        new_view = AlarmasPanelView(self.bot, server_names, lang=lang)
        new_embed = await build_alarmas_embed(self.bot, guild_id)
        await interaction.response.edit_message(embed=new_embed, view=new_view)


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
        """Actualiza el embed del panel compartido para reflejar el cambio global."""
        if not self.parent_message:
            return
        try:
            embed = await build_alarmas_embed(self.bot, interaction.guild_id)
            await self.parent_message.edit(embed=embed)
        except Exception as e:
            logger.error(f"[Alarma] Error actualizando panel principal: {e}")

    @discord.ui.button(label="Encender 🔔", style=discord.ButtonStyle.success)
    async def btn_on(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id

        await self.bot.db.execute(
            "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, self.map_name, channel_id),
        )
        await self.bot.db.commit()

        self.btn_on.disabled = True
        self.btn_off.disabled = False
        await interaction.response.edit_message(
            content=(
                f"🚨 **Alarma activada** para `{self.map_name}`. "
                f"Te mencionaré en este canal cuando entre un intruso."
            ),
            view=self,
        )
        await self._refresh_parent(interaction)

    @discord.ui.button(label="Apagar 🔕", style=discord.ButtonStyle.danger)
    async def btn_off(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        await self.bot.db.execute(
            "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
            (guild_id, user_id, self.map_name),
        )
        await self.bot.db.commit()

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

    @commands.Cog.listener()
    async def on_trusted_members_changed(self, guild_id: int):
        """Limpia el snapshot de jugadores conocidos del guild al cambiar la
        lista de tribu propia o tribus aliadas. Así el siguiente tick re-evalúa
        a todos los jugadores online — útil cuando alguien deja de ser confiable
        pero sigue conectado (su nombre estaría cacheado y no dispararía alarma).
        """
        try:
            cursor = await self.bot.db.execute(
                "DELETE FROM map_last_players WHERE guild_id = ?", (guild_id,)
            )
            await self.bot.db.commit()
            logger.info(
                f"[Alarma] Snapshot de map_last_players limpiado para guild={guild_id} "
                f"({cursor.rowcount} mapas reseteados) tras cambio de miembros confiables."
            )
        except Exception as e:
            logger.error(f"[Alarma] Error limpiando snapshot tras TRUSTED_MEMBERS_CHANGED: {e}")

    async def mapa_autocomplete(self, interaction: discord.Interaction, current: str):
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
    async def alarma(self, interaction: discord.Interaction, mapa: str, estado: str):
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

            db = self.bot.db
            if estado == "off":
                await db.execute(
                    "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                    (guild_id, user_id, mapa),
                )
                await db.commit()
                await interaction.followup.send(f"🔕 Alarma para **{mapa}** desactivada.", ephemeral=True)
            else:
                await db.execute(
                    "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                    (guild_id, user_id, mapa, channel_id),
                )
                await db.commit()
                await interaction.followup.send(
                    f"🚨 **Alarma activada** para `{mapa}`. Te mencionaré en este canal "
                    f"cuando entre un intruso. 🔔",
                    ephemeral=True,
                )
        except Exception as e:
            logger.error(f"Error en comando /alarma: {e}")
            await interaction.followup.send(f"❌ Ocurrió un error al procesar la alarma: {e}", ephemeral=True)

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
        embed = await build_alarmas_embed(self.bot, interaction.guild_id)
        # Panel compartido: el Select queda neutro (todos los mapas ⚪).
        # Cada usuario gestiona sus alarmas individualmente vía ephemeral.
        lang = await resolve_lang(self.bot, interaction.guild_id, "periodic")
        view = AlarmasPanelView(self.bot, server_names, lang=lang)

        # NO efímero — debe ser visible para toda la tribu.
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @tasks.loop(minutes=1)
    async def check_alarms_loop(self):
        """Comprueba intrusos usando los datos ya guardados en server_status_cache
        por el bucle de status, evitando consultas A2S duplicadas."""
        await self.bot.wait_until_ready()

        try:
            db = self.bot.db

            watched_maps = await db.fetchall("SELECT DISTINCT guild_id, map_name FROM map_alarms")
            if not watched_maps:
                return

            for row in watched_maps:
                guild_id = row["guild_id"]
                map_name = row["map_name"]

                try:
                    # Leer del caché de status en vez de hacer consulta A2S propia
                    cache_row = await db.fetchone(
                        "SELECT player_names, player_count FROM server_status_cache WHERE guild_id = ? AND server_name = ?",
                        (guild_id, map_name),
                    )

                    if not cache_row or not cache_row["player_names"]:
                        continue

                    # Parsear nombres actuales del caché. Se usa Counter (no set) para
                    # distinguir jugadores distintos que comparten Steam name (caso clásico:
                    # varios "123" o "bob" online a la vez). Si el contador de un nombre
                    # SUBE entre dos ticks, hay un nuevo jugador con ese mismo nombre y la
                    # alarma debe dispararse.
                    raw_names = cache_row["player_names"]
                    if raw_names == "Nadie conectado." or cache_row["player_count"] == 0:
                        current_counter: Counter[str] = Counter()
                    else:
                        current_counter = Counter(
                            n.strip() for n in raw_names.split(",") if n.strip()
                        )

                    # Obtener estado anterior — convertimos la lista (con duplicados
                    # preservados) a Counter para hacer la resta multi-conjunto.
                    prev_row = await db.fetchone(
                        "SELECT players_json FROM map_last_players WHERE guild_id = ? AND map_name = ?",
                        (guild_id, map_name),
                    )
                    if prev_row:
                        try:
                            prev_counter = Counter(json.loads(prev_row["players_json"]))
                        except (json.JSONDecodeError, TypeError):
                            prev_counter = Counter()
                    else:
                        prev_counter = Counter()

                    # Counter - Counter solo conserva claves con delta positivo.
                    diff = current_counter - prev_counter
                    new_entries = set(diff.keys())

                    if new_entries:
                        # Set de "confiables": tribu propia + tribus aliadas.
                        trusted_members = await _get_trusted_members(self.bot, guild_id)

                        intruders: list[str] = []
                        for name in new_entries:
                            # Ignorar miembros de la tribu propia o tribus aliadas
                            if name.lower() in trusted_members:
                                continue

                            # Comprobar si es un personaje registrado de la tribu
                            check_row = await db.fetchone(
                                """SELECT 1 FROM tribe_characters
                                   WHERE guild_id = ? AND (LOWER(character_name) = LOWER(?) OR LOWER(player_name) = LOWER(?))""",
                                (guild_id, name, name),
                            )
                            if not check_row:
                                intruders.append(name)

                        if intruders:
                            alert_targets = await db.fetchall(
                                "SELECT user_id, channel_id FROM map_alarms WHERE guild_id = ? AND map_name = ?",
                                (guild_id, map_name),
                            )

                            intruders_fmt = ", ".join([f"**{i}**" for i in intruders])
                            for target in alert_targets:
                                u_id = target["user_id"]
                                ch_id = target["channel_id"]
                                # Mensaje en el canal donde se activó la alarma, con mención
                                # al destinatario para que reciba notificación push.
                                try:
                                    channel = self.bot.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
                                    if channel is None:
                                        logger.warning(
                                            f"[Alarma] Canal {ch_id} no encontrado, no se envía alerta."
                                        )
                                        continue
                                    view = AlarmDismissView()
                                    await channel.send(
                                        f"⚠️ <@{u_id}>! **Intruso detectado** en `{map_name}`: {intruders_fmt}",
                                        view=view,
                                    )
                                except discord.Forbidden:
                                    logger.warning(
                                        f"[Alarma] Sin permisos para enviar en canal {ch_id} "
                                        f"(usuario {u_id}, mapa {map_name})."
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"[Alarma] Error enviando alerta a canal {ch_id} (user {u_id}): {e}"
                                    )

                    # Actualizar el estado anterior. Serializamos como lista con duplicados
                    # expandidos (Counter.elements()) para que el siguiente tick pueda
                    # detectar incrementos de cuenta en nombres repetidos.
                    await db.execute(
                        "INSERT OR REPLACE INTO map_last_players (guild_id, map_name, players_json) VALUES (?, ?, ?)",
                        (
                            guild_id,
                            map_name,
                            json.dumps(list(current_counter.elements())),
                        ),
                    )
                    await db.commit()

                except Exception as e:
                    logger.error(f"[Alarma] Error procesando alarma para {map_name} (Guild {guild_id}): {e}")

        except Exception as e:
            logger.error(f"[Alarma] Error general en check_alarms_loop: {e}")



async def setup(bot):
    # Tablas map_alarms y map_last_players creadas en db/schema.py.
    await bot.add_cog(Alarma(bot))
