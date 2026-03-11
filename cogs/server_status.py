import discord
from discord import app_commands
from discord.ext import commands, tasks
import a2s
import asyncio
import aiosqlite
import logging

# Configuración de Logging
logger = logging.getLogger("ArkTribeBot")


def parse_battlemetrics(bm_string: str) -> dict:
    """Parsea el campo battlemetrics_urls del formato 'MapName|IP:PORT,Map2|IP:PORT2'.

    Devuelve un diccionario {nombre_mapa: (ip, puerto)}.
    """
    servers = {}
    if not bm_string:
        return servers
    for entry in bm_string.split(","):
        entry = entry.strip()
        if "|" not in entry:
            continue
        parts = entry.split("|", 1)
        if len(parts) != 2:
            continue
        map_name = parts[0].strip()
        address_str = parts[1].strip()
        if ":" not in address_str:
            continue
        addr_parts = address_str.rsplit(":", 1)
        try:
            ip = addr_parts[0].strip()
            port = int(addr_parts[1].strip())
            servers[map_name] = (ip, port)
        except (ValueError, IndexError):
            continue
    return servers


async def get_guild_servers(bot, guild_id: int) -> dict:
    """Recupera el diccionario de servidores configurados para un Guild desde la Base de Datos."""
    async with aiosqlite.connect(bot.db_name) as db:
        c = await db.execute(
            "SELECT battlemetrics_urls FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
        row = await c.fetchone()
    if row and row[0]:
        return parse_battlemetrics(row[0])
    return {}


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inicio seguro de las tareas en segundo plano al cargar el Cog
        self.status_loop.start()
        self.global_status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()
        self.global_status_loop.cancel()

    async def get_server_embed(self, server_name: str, servers: dict):
        """Genera el Embed con el estado del servidor."""
        if server_name not in servers:
            return None

        ip, port = servers[server_name]
        address = (ip, port)

        try:
            # Ejecución asíncrona de consultas A2S
            info = await asyncio.wait_for(
                asyncio.to_thread(a2s.info, address), timeout=5.0
            )
            players = await asyncio.wait_for(
                asyncio.to_thread(a2s.players, address), timeout=5.0
            )

            valid_players = [p.name for p in players if p.name]
            p_count = len(valid_players)
            ping_ms = int(info.ping * 1000)

            embed = discord.Embed(
                title=f"🦖 Estado: {server_name}", color=discord.Color.green()
            )
            embed.add_field(name="Mapa", value=info.map_name, inline=True)

            player_list = ", ".join(valid_players)

            # Manejo de servidor sin jugadores activos
            if p_count == 0:
                player_list = "Nadie conectado."

            if len(player_list) > 1000:
                player_list = player_list[:1000] + "..."

            embed.add_field(
                name="Jugadores", value=f"{p_count}/{info.max_players}", inline=True
            )
            embed.add_field(name="Ping", value=f"{ping_ms}ms", inline=True)
            embed.add_field(name="IP", value=f"`{ip}:{port}`", inline=False)

            embed.add_field(
                name="Conectados", value=f"```{player_list}```", inline=False
            )
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

    @app_commands.command(
        name="status",
        description="Muestra el estado de un servidor de ARK (consulta única).",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa a consultar")
    @app_commands.autocomplete(mapa=status_mapa_autocomplete)
    async def status(self, interaction: discord.Interaction, mapa: str):
        await interaction.response.defer(ephemeral=True)
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_server_embed(mapa, servers)
        if embed:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Servidor no configurado. Usa `/inicio_ark` para añadir tus servidores.",
                ephemeral=True,
            )

    @app_commands.command(
        name="status_permanente",
        description="Crea un mensaje que se actualiza cada 2 minutos con el estado.",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa para monitorizar")
    @app_commands.autocomplete(mapa=status_mapa_autocomplete)
    async def status_permanente(self, interaction: discord.Interaction, mapa: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.**", ephemeral=True
            )
            return

        await interaction.response.defer()
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_server_embed(mapa, servers)
        if not embed:
            await interaction.followup.send(
                "❌ Error al generar el estado inicial.", ephemeral=True
            )
            return

        # Envío del mensaje inicial
        message = await interaction.followup.send(embed=embed)

        # Persistencia del mensaje en Base de Datos
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO status_messages (guild_id, channel_id, message_id, map_name)
                VALUES (?, ?, ?, ?)
            """,
                (interaction.guild_id, interaction.channel_id, message.id, mapa),
            )
            await db.commit()

    @tasks.loop(minutes=2)
    async def status_loop(self):
        """Tarea en segundo plano que actualiza los mensajes registrados."""
        # Espera de inicialización completa del bot
        await self.bot.wait_until_ready()

        messages_to_remove = []

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, guild_id, channel_id, message_id, map_name FROM status_messages"
            )
            rows = await cursor.fetchall()

            for row in rows:
                row_id = row["id"]
                guild_id = row["guild_id"]
                channel_id = row["channel_id"]
                message_id = row["message_id"]
                map_name = row["map_name"]

                try:
                    # Carga dinámica de servidores configurados para este Guild
                    servers = await get_guild_servers(self.bot, guild_id)
                    channel = self.bot.get_channel(
                        channel_id
                    ) or await self.bot.fetch_channel(channel_id)
                    if not channel:
                        logger.warning(
                            f"Canal {channel_id} no encontrado. Eliminando mensaje persistente {row_id}."
                        )
                        messages_to_remove.append(row_id)
                        continue

                    message = await channel.fetch_message(message_id)
                    new_embed = await self.get_server_embed(map_name, servers)

                    if new_embed:
                        await message.edit(embed=new_embed)
                        logger.info(
                            f"Actualizado estado de {map_name} en mensaje {message_id}"
                        )

                except discord.NotFound:
                    # Intercepción: El mensaje fue eliminado manualmente de Discord
                    logger.warning(
                        f"Mensaje {message_id} no encontrado. Eliminando de DB."
                    )
                    messages_to_remove.append(row_id)
                except discord.Forbidden:
                    logger.error(
                        f"Sin permiso para editar mensaje {message_id} en canal {channel_id}."
                    )
                except Exception as e:
                    logger.error(f"Error actualizando mensaje {row_id}: {e}")

            # Purgado de registros inválidos en Base de Datos
            if messages_to_remove:
                for msg_id in messages_to_remove:
                    await db.execute(
                        "DELETE FROM status_messages WHERE id = ?", (msg_id,)
                    )
                await db.commit()

    async def get_global_status_embed(self, servers: dict):
        """Genera un Embed unificado para todos los servidores del Guild, ordenado por jugadores."""
        embed = discord.Embed(
            title="🌐 Estado Global de Servidores de ARK", color=discord.Color.blue()
        )

        if not servers:
            embed.description = (
                "⚠️ No hay servidores configurados. Usa `/inicio_ark` para añadirlos."
            )
            return embed

        async def fetch_server(name, ip, port):
            address = (ip, port)
            try:
                # Límite de tiempo en la consulta A2S para prevenir bloqueos de la rutina
                info = await asyncio.wait_for(
                    asyncio.to_thread(a2s.info, address), timeout=5.0
                )
                players = await asyncio.wait_for(
                    asyncio.to_thread(a2s.players, address), timeout=5.0
                )

                valid_players = [p.name for p in players if p.name]
                p_count = len(valid_players)

                player_list = ", ".join(valid_players)
                ping_ms = int(info.ping * 1000)

                # Manejo de respuesta vacía (0 jugadores)
                if p_count == 0:
                    player_list = "Nadie conectado."

                if len(player_list) > 1000:
                    player_list = player_list[:1000] + "..."

                return {
                    "name": name,
                    "players": p_count,
                    "max_players": info.max_players,
                    "list": player_list,
                    "ping": ping_ms,
                    "error": None,
                }
            except Exception as e:
                return {"name": name, "error": str(e)}

        fetch_tasks = [
            fetch_server(name, ip, port) for name, (ip, port) in servers.items()
        ]
        results = await asyncio.gather(*fetch_tasks)

        populated_servers = []
        empty_servers = []
        offline_servers = []

        total_players = 0
        total_max = 0

        for res in results:
            if res["error"]:
                offline_servers.append(res["name"])
            else:
                total_players += res["players"]
                total_max += res["max_players"]

                if res["players"] > 0:
                    populated_servers.append(res)
                else:
                    empty_servers.append(res)

        # Clasificación de servidores activos por afluencia de jugadores (Descendente)
        populated_servers.sort(key=lambda x: x["players"], reverse=True)

        # 1. Servidores Poblados (Prioridad de visualización con detalle completo)
        for s in populated_servers:
            embed.add_field(
                name=f"🟢 {s['name']} - {s['players']}/{s['max_players']} Jugadores | 📶 {s['ping']}ms",
                value=f"```{s['list']}```",
                inline=False,
            )

        # 2. Servidores Vacíos (Agrupación para condensación de espacio)
        if empty_servers:
            empty_list_str = "\n".join(
                [f"🔸 **{s['name']}** - `{s['ping']}ms`" for s in empty_servers]
            )
            embed.add_field(
                name="🟡 Servidores Vacíos (Online)", value=empty_list_str, inline=False
            )

        # 3. Servidores Inactivos (Offline/Timeout)
        if offline_servers:
            offline_list_str = "\n".join([f"❌ **{s}**" for s in offline_servers])
            embed.add_field(
                name="🔴 Servidores Offline / Timeout",
                value=offline_list_str,
                inline=False,
            )

        embed.description = (
            f"**Total de jugadores en la red:** {total_players}/{total_max}"
        )
        embed.set_footer(text="Actualizado automáticamente cada 2 minutos.")

        return embed

    @app_commands.command(
        name="status_online",
        description="Muestra todos los servidores, jugadores y nombres, actualizándose cada 2 mins.",
    )
    async def status_online(self, interaction: discord.Interaction):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.**", ephemeral=True
            )
            return

        await interaction.response.defer()

        servers = await get_guild_servers(self.bot, interaction.guild_id)
        embed = await self.get_global_status_embed(servers)
        message = await interaction.followup.send(embed=embed)

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO status_online_messages (guild_id, channel_id, message_id)
                VALUES (?, ?, ?)
            """,
                (interaction.guild_id, interaction.channel_id, message.id),
            )
            await db.commit()

    @tasks.loop(minutes=2)
    async def global_status_loop(self):
        await self.bot.wait_until_ready()
        messages_to_remove = []

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, guild_id, channel_id, message_id FROM status_online_messages"
            )
            rows = await cursor.fetchall()

            if not rows:
                return

            # Generar un embed por Guild, agrupando los mensajes
            guild_embeds = {}
            for row in rows:
                guild_id = row["guild_id"]
                if guild_id not in guild_embeds:
                    servers = await get_guild_servers(self.bot, guild_id)
                    guild_embeds[guild_id] = await self.get_global_status_embed(servers)

            for row in rows:
                row_id = row["id"]
                guild_id = row["guild_id"]
                channel_id = row["channel_id"]
                message_id = row["message_id"]

                try:
                    channel = self.bot.get_channel(
                        channel_id
                    ) or await self.bot.fetch_channel(channel_id)
                    if not channel:
                        messages_to_remove.append(row_id)
                        continue

                    message = await channel.fetch_message(message_id)
                    new_embed = guild_embeds.get(guild_id)

                    if new_embed:
                        await message.edit(embed=new_embed)

                except discord.NotFound:
                    messages_to_remove.append(row_id)
                except discord.Forbidden:
                    pass
                except Exception as e:
                    logger.error(
                        f"Error actualizando global status mensaje {row_id}: {e}"
                    )

            if messages_to_remove:
                for msg_id in messages_to_remove:
                    await db.execute(
                        "DELETE FROM status_online_messages WHERE id = ?", (msg_id,)
                    )
                await db.commit()


async def setup(bot):
    await bot.add_cog(ServerStatus(bot))
