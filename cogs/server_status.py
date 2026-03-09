import discord
from discord import app_commands
from discord.ext import commands, tasks
import a2s
import asyncio
import aiosqlite
import logging

# Configuración de Logging
logger = logging.getLogger("ArkTribeBot")

AUTHORIZED_ADMIN_ID = 290904414452056064

# Diccionario de Servidores (IP:Port)
SERVERS = {
    "Hub": ("24.157.220.28", 21000),
    "Valguero": ("24.157.220.28", 21023),
    "Scorched Earth": ("24.157.220.28", 21012),
    "Crystal Isles": ("24.157.220.28", 21011),
    "Lost Island": ("24.157.220.28", 21010),
    "Gen1": ("24.157.220.28", 21009),
    "The Island": ("24.157.220.28", 21008),
    "Extinction": ("24.157.220.28", 21007),
    "Aberration": ("24.157.220.28", 21006),
    "Gen2": ("24.157.220.28", 21005),
    "Fjordur": ("24.157.220.28", 21004),
    "The Center": ("24.157.220.28", 21003),
    "Ragnarok": ("24.157.220.28", 21001),
}

# Creación de opciones para el comando (Autocomplete)
SERVER_CHOICES = [app_commands.Choice(name=name, value=name) for name in SERVERS.keys()]


class ServerStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inicio seguro de las tareas en segundo plano al cargar el Cog
        self.status_loop.start()
        self.global_status_loop.start()

    def cog_unload(self):
        self.status_loop.cancel()
        self.global_status_loop.cancel()

    async def get_server_embed(self, server_name):
        """Genera el Embed con el estado del servidor."""
        if server_name not in SERVERS:
            return None

        ip, port = SERVERS[server_name]
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

    @app_commands.command(
        name="status",
        description="Muestra el estado de un servidor de ARK (consulta única).",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa a consultar")
    @app_commands.choices(mapa=SERVER_CHOICES)
    async def status(
        self, interaction: discord.Interaction, mapa: app_commands.Choice[str]
    ):
        await interaction.response.defer()
        server_name = mapa.value

        embed = await self.get_server_embed(server_name)
        if embed:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "❌ Servidor no configurado.", ephemeral=True
            )

    @app_commands.command(
        name="status_permanente",
        description="Crea un mensaje que se actualiza cada 2 minutos con el estado.",
    )
    @app_commands.describe(mapa="Selecciona el servidor/mapa para monitorizar")
    @app_commands.choices(mapa=SERVER_CHOICES)
    # @app_commands.default_permissions(administrator=True) # Check manual para permitir ID específico
    async def status_permanente(
        self, interaction: discord.Interaction, mapa: app_commands.Choice[str]
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(
                "❌ **ACCESO DENEGADO.**", ephemeral=True
            )
            return

        await interaction.response.defer()
        server_name = mapa.value

        embed = await self.get_server_embed(server_name)
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
                INSERT INTO status_messages (channel_id, message_id, map_name)
                VALUES (?, ?, ?)
            """,
                (interaction.channel_id, message.id, server_name),
            )
            await db.commit()

        # Nota: El seguimiento (followup) del mensaje persistente actúa como confirmación inicial

    @tasks.loop(minutes=2)
    async def status_loop(self):
        """Tarea en segundo plano que actualiza los mensajes registrados."""
        # Espera de inicialización completa del bot
        await self.bot.wait_until_ready()

        messages_to_remove = []

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, channel_id, message_id, map_name FROM status_messages"
            )
            rows = await cursor.fetchall()

            for row in rows:
                row_id = row["id"]
                channel_id = row["channel_id"]
                message_id = row["message_id"]
                map_name = row["map_name"]

                try:
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
                    new_embed = await self.get_server_embed(
                        map_name
                    )  # Llamada reutilizable para generar el estado actualizado

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

    async def get_global_status_embed(self):
        """Genera un Embed unificado para todos los servidores, ordenado e inteligentemente agrupado."""
        embed = discord.Embed(
            title="🌐 Estado Global de Servidores de ARK", color=discord.Color.blue()
        )

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

        tasks = [fetch_server(name, ip, port) for name, (ip, port) in SERVERS.items()]
        results = await asyncio.gather(*tasks)

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

        embed = await self.get_global_status_embed()
        message = await interaction.followup.send(embed=embed)

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO status_online_messages (channel_id, message_id)
                VALUES (?, ?)
            """,
                (interaction.channel_id, message.id),
            )
            await db.commit()

    @tasks.loop(minutes=2)
    async def global_status_loop(self):
        await self.bot.wait_until_ready()
        messages_to_remove = []

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, channel_id, message_id FROM status_online_messages"
            )
            rows = await cursor.fetchall()

            if not rows:
                return

            new_embed = await self.get_global_status_embed()

            for row in rows:
                row_id = row["id"]
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
