import asyncio
import logging
import socket
import aiohttp

import a2s
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.i18n import GAME_ASA, get_game_mode, resolve_lang, t
from utils.parsing import parse_battlemetrics

# Configuración de Logging
logger = logging.getLogger("ArkTribeBot")


async def get_guild_servers(bot, guild_id: int) -> dict:
    """Recupera el diccionario de servidores configurados para un Guild desde la Base de Datos.

    Usa la conexión persistente (``bot.db``) si está disponible. Mantiene fallback a
    conexión efímera para escenarios excepcionales (ej. tests que no inicializan bot.db).
    """
    if getattr(bot, "db", None) is not None:
        row = await bot.db.fetchone(
            "SELECT battlemetrics_urls FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
    else:
        async with aiosqlite.connect(bot.db_name) as db:
            c = await db.execute(
                "SELECT battlemetrics_urls FROM guild_config WHERE guild_id = ?",
                (guild_id,),
            )
            row = await c.fetchone()
    if row and row[0]:
        return parse_battlemetrics(row[0])
    return {}


# --- CACHÉ COMPARTIDO DE CONSULTAS A2S ---
# Evita consultas duplicadas cuando server_status y k4ultra sondean en el mismo ciclo.
import time as _time  # noqa: E402  (separación deliberada para agrupar el módulo de caché)

_a2s_cache = {}  # {(guild_id, map_name): {"info": ..., "players": [...], "ts": float}}
# TTL: 90 s — algo menor que el ciclo de status_loop (120 s) y mayor que el de
# k4ultra/global_status (60 s) para que el segundo loop del minuto reutilice el
# resultado de red del primero sin volver a consultar A2S.
_A2S_CACHE_TTL = 90  # segundos

_a2s_semaphore = asyncio.Semaphore(5)


class MockA2SInfo:
    def __init__(self, map_name, player_count, max_players):
        self.map_name = map_name
        self.player_count = player_count
        self.max_players = max_players
        self.ping = 0.0

async def _fetch_from_battlemetrics(ip: str, port: int):
    import urllib.parse
    try:
        resolved_ip = socket.gethostbyname(ip)
    except Exception:
        resolved_ip = ip
        
    search_query = urllib.parse.quote(f'"{resolved_ip}:{port}"')
    url = f"https://api.battlemetrics.com/servers?filter[search]={search_query}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=5.0) as resp:
            if resp.status == 200:
                data = await resp.json()
                for s in data.get("data", []):
                    attrs = s.get("attributes", {})
                    # Battlemetrics puede tener portQuery == port para ASA
                    if attrs.get("ip") == resolved_ip and (attrs.get("port") == port or attrs.get("portQuery") == port):
                        info = MockA2SInfo(
                            map_name=attrs.get("details", {}).get("map", "Unknown"),
                            player_count=attrs.get("players", 0),
                            max_players=attrs.get("maxPlayers", 0)
                        )
                        return info, []
    raise TimeoutError("Timeout o servidor no encontrado en Battlemetrics")

async def _fetch_single_server(name: str, ip: str, port: int, game_mode: str = None):
    """Consulta A2S de un solo servidor con semáforo global, con fallback a Battlemetrics."""
    async with _a2s_semaphore:
        address = (ip, port)
        try:
            info = await asyncio.wait_for(asyncio.to_thread(a2s.info, address), timeout=4.0)
            if game_mode == GAME_ASA:
                players = []
            else:
                players = await asyncio.wait_for(asyncio.to_thread(a2s.players, address), timeout=4.0)
            return info, players
        except Exception:
            return await _fetch_from_battlemetrics(ip, port)



async def query_all_servers(bot, guild_id: int, servers: dict = None) -> dict:
    """Consulta A2S centralizada con caché de corta vida (30s).

    Devuelve un dict {map_name: {"info": a2s.Info, "players": [{"name": str, "duration": float}], "error": str|None}}.
    Si la consulta de un mapa está en caché y tiene menos de 30s, se reutiliza.
    """
    if servers is None:
        servers = await get_guild_servers(bot, guild_id)

    now = _time.time()
    results = {}
    to_fetch = {}

    # 1. Comprobar caché para cada servidor
    for name, (ip, port) in servers.items():
        key = (guild_id, name)
        cached = _a2s_cache.get(key)
        if cached and (now - cached["ts"]) < _A2S_CACHE_TTL:
            results[name] = cached["data"]
        else:
            to_fetch[name] = (ip, port)

    game_mode = await get_game_mode(bot, guild_id)

    # 2. Consultar solo los que no están en caché
    if to_fetch:

        async def _query_one(map_name, ip, port):
            try:
                info, players = await _fetch_single_server(map_name, ip, port, game_mode)

                if game_mode == GAME_ASA:
                    valid = []
                    p_count = info.player_count
                else:
                    valid = [{"name": p.name.strip(), "duration": p.duration} for p in players if p.name]
                    p_count = len(valid)

                return map_name, {
                    "info": info,
                    "players": valid,
                    "address": f"{ip}:{port}",
                    "ping": int(info.ping * 1000),
                    "player_count": p_count,
                    "max_players": info.max_players,
                    "error": None,
                }
            except Exception as e:
                return map_name, {"info": None, "players": [], "error": str(e), "address": f"{ip}:{port}"}

        tasks = [_query_one(n, ip, port) for n, (ip, port) in to_fetch.items()]
        fetched = await asyncio.gather(*tasks)

        for map_name, data in fetched:
            results[map_name] = data
            _a2s_cache[(guild_id, map_name)] = {"data": data, "ts": _time.time()}

    return results


class ServerStatus(commands.Cog):
    # Grupo unificado de estado (antes /status, /status_online, /status_permanente).
    status_grp = app_commands.Group(name="status", description="Estado de los servidores del clúster.")

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.status_loop.start()
        self.global_status_loop.start()

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard interactivo de Estado de Servidores."""
        import asyncio

        from cogs.management import get_info_texts

        info_lang = await resolve_lang(self.bot, guild_id, "periodic")
        info_embed = discord.Embed(
            description=get_info_texts(info_lang)["status"],
            color=discord.Color.from_rgb(43, 45, 49),
        )
        await channel.send(embed=info_embed)

        embed = discord.Embed(
            title="🔍 Monitorizando Servidores...",
            description="El bot contactará con los servidores en el próximo ciclo de actualización.",
            color=discord.Color.orange(),
        )
        msg = await channel.send(embed=embed)
        await asyncio.sleep(0.5)

        await self.bot.db.execute(
            "INSERT INTO status_online_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (guild_id, channel.id, msg.id),
        )
        await self.bot.db.commit()

    def cog_unload(self):
        self.status_loop.cancel()
        self.global_status_loop.cancel()

    async def get_server_embed(self, server_name: str, servers: dict, guild_id: int):
        """Genera el Embed con el estado del servidor."""
        if server_name not in servers:
            return None

        ip, port = servers[server_name]
        address = (ip, port)

        game_mode = await get_game_mode(self.bot, guild_id)

        try:
            info, players = await _fetch_single_server(server_name, ip, port, game_mode)

            if game_mode == GAME_ASA:
                p_count = info.player_count
                player_list = f"👥 {p_count} jugadores"
            else:
                valid_players = [p.name for p in players if getattr(p, "name", None)]
                p_count = len(valid_players)
                player_list = ", ".join(valid_players)
                if p_count == 0:
                    player_list = "Nadie conectado."

            ping_ms = int(info.ping * 1000)

            embed = discord.Embed(title=f"🦖 Estado: {server_name}", color=discord.Color.green())
            embed.add_field(name="Mapa", value=info.map_name, inline=True)

            if len(player_list) > 1000:
                player_list = player_list[:1000] + "..."

            embed.add_field(name="Jugadores", value=f"{p_count}/{info.max_players}", inline=True)
            embed.add_field(name="Ping", value=f"{ping_ms}ms", inline=True)
            embed.add_field(name="IP", value=f"`{ip}:{port}`", inline=False)

            embed.add_field(name="Conectados", value=f"```{player_list}```", inline=False)
            embed.set_footer(text="Actualizado automáticamente cada 2 minutos.")
            return embed

        except Exception as e:
            embed = discord.Embed(
                title=f"⚠️ Error: {server_name}",
                description=f"No se pudo conectar.\n`{e}`",
                color=discord.Color.red(),
            )
            embed.set_footer(text="Se reintentará en 5 minutos.")
            return embed

    async def status_mapa_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete dinámico basado en los servidores configurados en el Guild."""
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        return [
            app_commands.Choice(name=name, value=name)
            for name in servers.keys()
            if current.lower() in name.lower()
        ][:25]

    @status_grp.command(
        name="mapa",
        description="Muestra el estado de un servidor de ARK (consulta única).",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa a consultar")
    @app_commands.autocomplete(mapa=status_mapa_autocomplete)
    async def status(self, interaction: discord.Interaction, mapa: str):
        await interaction.response.defer(ephemeral=True)
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_server_embed(mapa, servers, interaction.guild_id)
        if embed:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(t("status.cmd.not_configured", lang), ephemeral=True)

    @status_grp.command(
        name="fijar",
        description="Crea un mensaje que se actualiza cada 2 minutos con el estado.",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa para monitorizar")
    @app_commands.autocomplete(mapa=status_mapa_autocomplete)
    async def status_permanente(self, interaction: discord.Interaction, mapa: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        await interaction.response.defer()
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_server_embed(mapa, servers, interaction.guild_id)
        if not embed:
            await interaction.followup.send(t("status.cmd.gen_error", lang), ephemeral=True)
            return

        # Envío del mensaje inicial
        message = await interaction.followup.send(embed=embed)

        # Persistencia del mensaje en Base de Datos
        await self.bot.db.execute(
            "INSERT INTO status_messages (guild_id, channel_id, message_id, map_name) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, interaction.channel_id, message.id, mapa),
        )
        await self.bot.db.commit()

    @tasks.loop(minutes=2)
    async def status_loop(self):
        """Tarea en segundo plano que actualiza los mensajes registrados."""
        # Espera de inicialización completa del bot
        await self.bot.wait_until_ready()

        messages_to_remove: list[int] = []
        db = self.bot.db
        rows = await db.fetchall("SELECT id, guild_id, channel_id, message_id, map_name FROM status_messages")

        for row in rows:
            row_id = row["id"]
            guild_id = row["guild_id"]
            channel_id = row["channel_id"]
            message_id = row["message_id"]
            map_name = row["map_name"]

            try:
                # Carga dinámica de servidores configurados para este Guild
                servers = await get_guild_servers(self.bot, guild_id)
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                if not channel:
                    logger.warning(
                        f"Canal {channel_id} no encontrado. Eliminando mensaje persistente {row_id}."
                    )
                    messages_to_remove.append(row_id)
                    continue

                message = await channel.fetch_message(message_id)
                new_embed = await self.get_server_embed(map_name, servers, guild_id)

                if new_embed:
                    await message.edit(embed=new_embed)
                    logger.info(f"Actualizado estado de {map_name} en mensaje {message_id}")

            except discord.NotFound:
                # Intercepción: El mensaje fue eliminado manualmente de Discord
                logger.warning(f"Mensaje {message_id} no encontrado. Eliminando de DB.")
                messages_to_remove.append(row_id)
            except discord.Forbidden:
                logger.error(f"Sin permiso para editar mensaje {message_id} en canal {channel_id}.")
            except Exception as e:
                logger.error(f"Error actualizando mensaje {row_id}: {e}")

        # Purgado de registros inválidos en Base de Datos
        if messages_to_remove:
            for msg_id in messages_to_remove:
                await db.execute("DELETE FROM status_messages WHERE id = ?", (msg_id,))
            await db.commit()

    async def get_global_status_embed(self, guild_id: int, servers: dict):
        """Genera un Embed unificado para todos los servidores del Guild, ordenado por jugadores."""
        lang = await resolve_lang(self.bot, guild_id, "periodic")
        embed = discord.Embed(title=t("status.title", lang), color=discord.Color.from_rgb(0, 120, 255))

        if not servers:
            embed.description = t("status.no_servers", lang)
            return embed

        # Consulta A2S centralizada (compartida con K4Ultra)
        raw_results = await query_all_servers(self.bot, guild_id, servers)
        game_mode = await get_game_mode(self.bot, guild_id)

        # Guardar en caché de DB (usa la conexión persistente compartida).
        try:
            db = self.bot.db
            for name, res in raw_results.items():
                if not res.get("error"):
                    if game_mode == GAME_ASA:
                        player_names = t("status.player_count_only", lang, count=res["player_count"])
                    else:
                        player_names = ", ".join([p["name"] for p in res["players"]])
                        if not player_names:
                            player_names = t("status.nobody", lang)
                    await db.execute(
                        """INSERT OR REPLACE INTO server_status_cache
                           (guild_id, server_name, ip_port, ping, player_count, player_names, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                        (
                            guild_id,
                            name,
                            res.get("address"),
                            res.get("ping"),
                            res.get("player_count"),
                            player_names,
                        ),
                    )
            await db.commit()
        except Exception as e:
            logger.error(f"Error guardando caché de status: {e}")

        populated_servers = []
        empty_servers = []
        offline_servers = []

        total_players = 0
        total_max = 0

        for name, res in raw_results.items():
            if res.get("error"):
                offline_servers.append({"name": name, "error": res["error"]})
            else:
                p_count = res.get("player_count", 0)
                total_players += p_count
                total_max += res.get("max_players", 0)

                if game_mode == GAME_ASA:
                    player_list = t("status.player_count_only", lang, count=p_count)
                else:
                    player_list = ", ".join([p["name"] for p in res["players"]])
                    if not player_list:
                        player_list = t("status.nobody", lang)

                if len(player_list) > 1000:
                    player_list = player_list[:1000] + "..."

                entry = {
                    "name": name,
                    "players": p_count,
                    "max_players": res.get("max_players", 0),
                    "list": player_list,
                    "ping": res.get("ping", 0),
                }

                if p_count > 0:
                    populated_servers.append(entry)
                else:
                    empty_servers.append(entry)

        # Clasificación de servidores activos por afluencia de jugadores (Descendente)
        populated_servers.sort(key=lambda x: x["players"], reverse=True)

        # Cabecera con badges (estilo Blacklist/Scouting).
        n_pop = len(populated_servers)
        n_empty = len(empty_servers)
        n_off = len(offline_servers)
        # Barra de ocupación visual del cluster (10 segmentos).
        if total_max > 0:
            ratio = total_players / total_max
            filled = min(10, max(0, int(round(ratio * 10))))
            occupancy_bar = "█" * filled + "░" * (10 - filled)
            occupancy_text = f"`{occupancy_bar}` `{total_players}/{total_max}` ({int(ratio * 100)}%)"
        else:
            occupancy_text = t("status.no_data", lang)

        lines = [
            t("status.total_players", lang, occupancy=occupancy_text),
            t("status.badges", lang, pop=n_pop, empty=n_empty, off=n_off),
            "",
        ]

        # 1. Servidores Poblados.
        if populated_servers:
            lines.append(t("status.section.active", lang))
            for s in populated_servers:
                lines.append(
                    f"**{s['name']}**  ·  👥 `{s['players']}/{s['max_players']}`  ·  📶 `{s['ping']}ms`"
                )
                lines.append(f"```{s['list']}```")
            lines.append("")

        # 2. Servidores Vacíos.
        if empty_servers:
            lines.append(t("status.section.empty", lang))
            for s in empty_servers:
                lines.append(f"🔸 **{s['name']}**  ·  📶 `{s['ping']}ms`")
            lines.append("")

        # 3. Servidores Inactivos.
        if offline_servers:
            lines.append(t("status.section.offline", lang))
            for s in offline_servers:
                lines.append(f"❌ **{s['name']}**  ·  *{s['error']}*")
            lines.append("")

        embed.description = "\n".join(lines).strip()
        embed.set_footer(text=t("status.footer", lang))
        return embed

    @status_grp.command(
        name="cluster",
        description="Muestra todos los servidores, jugadores y nombres, actualizándose cada 2 mins.",
    )
    async def status_online(self, interaction: discord.Interaction):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        await interaction.response.defer()

        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_global_status_embed(interaction.guild_id, servers)
        message = await interaction.followup.send(embed=embed)

        await self.bot.db.execute(
            "INSERT INTO status_online_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (interaction.guild_id, interaction.channel_id, message.id),
        )
        await self.bot.db.commit()

    @tasks.loop(minutes=1)
    async def global_status_loop(self):
        await self.bot.wait_until_ready()

        import time

        current_minute = int(time.time() // 60)

        messages_to_remove: list[int] = []
        db = self.bot.db

        # Extraer las configuraciones de intervalo por guild
        cfg_rows = await db.fetchall("SELECT guild_id, update_interval FROM guild_config")
        guild_configs = {r["guild_id"]: r["update_interval"] or 2 for r in cfg_rows}

        rows = await db.fetchall("SELECT id, guild_id, channel_id, message_id FROM status_online_messages")
        if not rows:
            return

        # Filtrar qué guilds deben actualizarse en base al minuto actual y su intervalo
        guilds_to_update: set[int] = set()
        active_rows = []
        for row in rows:
            g_id = row["guild_id"]
            interval = guild_configs.get(g_id, 2)
            if current_minute % interval == 0:
                guilds_to_update.add(g_id)
                active_rows.append(row)

        if not active_rows:
            return

        # Generar un embed por Guild, agrupando los mensajes
        guild_embeds: dict[int, discord.Embed] = {}
        for guild_id in guilds_to_update:
            servers = await get_guild_servers(self.bot, guild_id)
            guild_embeds[guild_id] = await self.get_global_status_embed(guild_id, servers)

        for row in active_rows:
            row_id = row["id"]
            guild_id = row["guild_id"]
            channel_id = row["channel_id"]
            message_id = row["message_id"]

            try:
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                if not channel:
                    messages_to_remove.append(row_id)
                    continue

                message = await channel.fetch_message(message_id)
                new_embed = guild_embeds.get(guild_id)

                if new_embed:
                    # Marca de tiempo de actualización para transparencia
                    from datetime import datetime

                    now_str = datetime.now().strftime("%H:%M:%S")
                    new_embed.set_footer(text=f"Actualizado cada 2 min • Última vez: {now_str}")
                    await message.edit(embed=new_embed)

            except discord.NotFound:
                messages_to_remove.append(row_id)
            except discord.Forbidden as e:
                logger.debug(f"[Status] Sin permiso editando mensaje {message_id}: {e}")
            except Exception as e:
                logger.error(f"Error actualizando global status mensaje {row_id}: {e}")

        if messages_to_remove:
            for msg_id in messages_to_remove:
                await db.execute("DELETE FROM status_online_messages WHERE id = ?", (msg_id,))
            await db.commit()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
