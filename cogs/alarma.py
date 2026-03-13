import discord
from discord import app_commands
from discord.ext import commands, tasks
import a2s
import asyncio
import aiosqlite
import logging
import json

logger = logging.getLogger("ArkTribeBot")

# Reutilización de lógica de parseo de IPs (copiada de server_status para independencia)
def parse_battlemetrics(bm_string: str) -> dict:
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
    async with aiosqlite.connect(bot.db_name) as db:
        c = await db.execute(
            "SELECT battlemetrics_urls FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        )
        row = await c.fetchone()
    if row and row[0]:
        return parse_battlemetrics(row[0])
    return {}

class AlarmDismissView(discord.ui.View):
    """Vista con botón para eliminar el mensaje de alerta.
    Usa el custom_id registrado en main.py (DismissAlarmView) para persistencia.
    """
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Silenciar",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="dismiss_alarm_btn", # Coincide con main.py:DismissAlarmView
    )
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Esta función solo se usa si la vista no es persistente, 
        # pero como main.py ya tiene un listener para este custom_id, 
        # el bot ejecutará el código de main.py.
        pass

class Alarma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_alarms_loop.start()

    def cog_unload(self):
        self.check_alarms_loop.cancel()

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
    @app_commands.describe(mapa="Nombre del mapa a vigilar (ej: Fjordur)")
    @app_commands.autocomplete(mapa=mapa_autocomplete)
    async def alarma(self, interaction: discord.Interaction, mapa: str):
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id

        # Verificar si el servidor tiene battlemetrics configurado
        servers = await get_guild_servers(self.bot, guild_id)
        if not servers:
            await interaction.response.send_message(
                "❌ No hay servidores configurados. Usa `/inicio_ark` primero.", ephemeral=True
            )
            return

        if mapa not in servers:
            await interaction.response.send_message(
                f"❌ El mapa `{mapa}` no existe en la configuración actual.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            # Togle de alarma: si existe, borrar. Si no, insertar.
            cursor = await db.execute(
                "SELECT 1 FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                (guild_id, user_id, mapa),
            )
            exists = await cursor.fetchone()

            if exists:
                await db.execute(
                    "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                    (guild_id, user_id, mapa),
                )
                await db.commit()
                await interaction.response.send_message(
                    f"🔕 Alarma para **{mapa}** desactivada.", ephemeral=True
                )
            else:
                await db.execute(
                    "INSERT INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                    (guild_id, user_id, mapa, channel_id),
                )
                await db.commit()
                await interaction.response.send_message(
                    f"🚨 El chupapingas de **{interaction.user.display_name}** tiene miedo en **{mapa}**, le mantendremos avisado. 🔔",
                    ephemeral=True,
                )

    @tasks.loop(minutes=1)
    async def check_alarms_loop(self):
        await self.bot.wait_until_ready()
        
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            
            # Obtener todos los mapas que tienen al menos una alarma activa
            cursor = await db.execute("SELECT DISTINCT guild_id, map_name FROM map_alarms")
            rows = await cursor.fetchall()
            
            for row in rows:
                guild_id = row["guild_id"]
                map_name = row["map_name"]
                
                # Obtener dirección del servidor
                servers = await get_guild_servers(self.bot, guild_id)
                if map_name not in servers:
                    continue
                
                ip, port = servers[map_name]
                address = (ip, port)
                
                try:
                    # Consulta A2S para obtener jugadores
                    players_data = await asyncio.wait_for(
                        asyncio.to_thread(a2s.players, address), timeout=5.0
                    )
                    current_names = {p.name for p in players_data if p.name}
                    
                    # Recuperar lista previa para detectar cambios
                    c_prev = await db.execute(
                        "SELECT players_json FROM map_last_players WHERE guild_id = ? AND map_name = ?",
                        (guild_id, map_name),
                    )
                    prev_row = await c_prev.fetchone()
                    prev_names = set(json.loads(prev_row["players_json"])) if prev_row else set()
                    
                    # Detectar quienes han entrado
                    new_entries = current_names - prev_names
                    
                    if new_entries:
                        intruders = []
                        for name in new_entries:
                            # Verificar si es miembro de la tribu (ignora mayúsculas)
                            c_check = await db.execute(
                                "SELECT 1 FROM tribe_characters WHERE LOWER(character_name) = LOWER(?) AND guild_id = ?",
                                (name, guild_id),
                            )
                            if not await c_check.fetchone():
                                intruders.append(name)
                        
                        if intruders:
                            # Notificar a los usuarios específicos para ese mapa
                            c_users = await db.execute(
                                "SELECT user_id, channel_id FROM map_alarms WHERE guild_id = ? AND map_name = ?",
                                (guild_id, map_name),
                            )
                            alert_targets = await c_users.fetchall()
                            
                            for target in alert_targets:
                                try:
                                    u_id = target["user_id"]
                                    ch_id = target["channel_id"]
                                    
                                    channel = self.bot.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
                                    if channel:
                                        intruders_fmt = ", ".join([f"**{i}**" for i in intruders])
                                        view = AlarmDismissView()
                                        await channel.send(
                                            f"⚠️ <@{u_id}>! **Intruso detectado** en `{map_name}`: {intruders_fmt}",
                                            view=view
                                        )
                                except Exception as e:
                                    logger.error(f"Error enviando alerta a {target['user_id']}: {e}")
                    
                    # Actualizar caché de jugadores
                    await db.execute(
                        "INSERT OR REPLACE INTO map_last_players (guild_id, map_name, players_json) VALUES (?, ?, ?)",
                        (guild_id, map_name, json.dumps(list(current_names))),
                    )
                    await db.commit()
                    
                except Exception:
                    # Silenciar errores de conexión A2S individuales para no romper el bucle
                    pass

async def setup(bot):
    await bot.add_cog(Alarma(bot))
