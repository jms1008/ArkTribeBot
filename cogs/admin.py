import discord
from discord import app_commands
from discord.ext import commands
import logging
import aiosqlite

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
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            await db.execute(
                "INSERT INTO k4ultra_messages (channel_id, message_id) VALUES (?, ?)",
                (ch_id_int, msg_id_int),
            )
            await db.commit()

        # Generación del primer embed
        from cogs.k4ultra import K4UltraView

        k_cog = self.bot.get_cog("K4Ultra")
        if k_cog:
            embed, top_players = await k_cog.generate_k4ultra_embed()
            view = K4UltraView(self.bot, top_players)
            await message.edit(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Mensaje `{message_id}` del canal `<#{ch_id_int}>` asociado a K4Ultra con éxito.",
            ephemeral=True,
        )

    @commands.command(name="sync")
    async def sync(self, ctx):
        """Sincroniza los comandos slash con el servidor actual."""
        await ctx.send("🔄 Sincronizando comandos...")
        try:
            # Sincronización instantánea con el servidor actual
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)

            await ctx.send(
                f"✅ **{len(synced)}** comandos sincronizados en este servidor."
            )
            logger.info(
                f"Comandos sincronizados manualente en {ctx.guild.name} ({ctx.guild.id})"
            )
        except Exception as e:
            await ctx.send(f"❌ Error al sincronizar: {e}")
            logger.error(f"Error sync: {e}")

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
