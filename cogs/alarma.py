import discord
from discord import app_commands
from discord.ext import commands, tasks
import a2s
import asyncio
import aiosqlite
import logging
import json

logger = logging.getLogger("ArkTribeBot")

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
    Usa el custom_id registrado en main.py para persistencia si se registra globalmente.
    """
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
            # Respondemos para evitar "Interaction Failed"
            if not interaction.response.is_done():
                await interaction.response.send_message("Alarma silenciada.", ephemeral=True)
        except Exception:
            pass

async def build_alarmas_embed(bot, guild_id: int, user_id: int) -> discord.Embed:
    embed = discord.Embed(
        title="🔔 Panel de Alarmas Activas",
        description="Selecciona un mapa en el menú de abajo para encender o apagar la alarma contra intrusos.",
        color=discord.Color.gold()
    )
    async with aiosqlite.connect(bot.db_name) as db:
        c = await db.execute(
            "SELECT map_name FROM map_alarms WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        rows = await c.fetchall()
        
    if not rows:
        embed.add_field(name="Estado", value="💤 No tienes ninguna alarma activada ahora.", inline=False)
    else:
        mapas = [r[0] for r in rows]
        lista_str = "\n".join([f"• **{m}**" for m in mapas])
        embed.add_field(name="👀 Mapas Vigilados:", value=lista_str, inline=False)
        
    return embed

class AlarmasPanelView(discord.ui.View):
    def __init__(self, bot, servers: list):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected_map = None

        options = []
        for s in servers[:25]:
            options.append(discord.SelectOption(label=s, value=s))
            
        if not options:
            options.append(discord.SelectOption(label="Sin servidores", value="none"))
            
        self.select_mapa.options = options

    @discord.ui.select(placeholder="Selecciona un mapa del clúster...", custom_id="alarm_panel_select")
    async def select_mapa(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "none":
            await interaction.response.send_message("No hay servidores configurados.", ephemeral=True)
            return
            
        self.selected_map = select.values[0]
        await interaction.response.send_message(f"📍 Servidor **{self.selected_map}** seleccionado.\n👉 *Usa los botones para Encender 🔔 o Apagar 🔕 la alarma.*", ephemeral=True)

    @discord.ui.button(label="Encender 🔔", style=discord.ButtonStyle.success, custom_id="alarm_panel_on")
    async def btn_on(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_map:
            await interaction.response.send_message("⚠️ Selecciona un mapa en el menú desplegable primero.", ephemeral=True)
            return
            
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        channel_id = interaction.channel_id
        
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, self.selected_map, channel_id)
            )
            await db.commit()
            
        embed = await build_alarmas_embed(self.bot, guild_id, user_id)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"🚨 **Alarma activada** para `{self.selected_map}`.", ephemeral=True)

    @discord.ui.button(label="Apagar 🔕", style=discord.ButtonStyle.danger, custom_id="alarm_panel_off")
    async def btn_off(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_map:
            await interaction.response.send_message("⚠️ Selecciona un mapa en el menú desplegable primero.", ephemeral=True)
            return
            
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM map_alarms WHERE guild_id = ? AND user_id = ? AND map_name = ?",
                (guild_id, user_id, self.selected_map)
            )
            await db.commit()
            
        embed = await build_alarmas_embed(self.bot, guild_id, user_id)
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"🔕 **Alarma desactivada** para `{self.selected_map}`.", ephemeral=True)

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
    @app_commands.describe(
        mapa="Nombre del mapa a vigilar (ej: Fjordur)",
        estado="Activar (on) o desactivar (off) la alarma"
    )
    @app_commands.choices(estado=[
        app_commands.Choice(name="Encendido", value="on"),
        app_commands.Choice(name="Apagado", value="off"),
    ])
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
                    "❌ No hay servidores configurados. Usa `/inicio_ark` primero.", ephemeral=True
                )
                return

            if mapa not in servers:
                await interaction.followup.send(
                    f"❌ El mapa `{mapa}` no existe en la configuración actual.", ephemeral=True
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
                    # Inserción segura (ON CONFLICT no necesario aquí por el check o INSERT OR REPLACE)
                    await db.execute(
                        "INSERT OR REPLACE INTO map_alarms (guild_id, user_id, map_name, channel_id) VALUES (?, ?, ?, ?)",
                        (guild_id, user_id, mapa, channel_id),
                    )
                    await db.commit()
                    await interaction.followup.send(
                        f"🚨 El chupapingas de **{interaction.user.display_name}** tiene miedo en **{mapa}**, le mantendremos avisado. 🔔",
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
            await interaction.response.send_message("❌ No hay servidores configurados. Usa `/inicio_ark` primero.", ephemeral=True)
            return
            
        server_names = list(servers.keys())
        embed = await build_alarmas_embed(self.bot, interaction.guild_id, interaction.user.id)
        view = AlarmasPanelView(self.bot, server_names)
        
        await interaction.response.send_message(embed=embed, view=view)

    @tasks.loop(minutes=1)
    async def check_alarms_loop(self):
        await self.bot.wait_until_ready()
        
        # Semáforo para no saturar la red (especialmente si coincide con server_status)
        semaphore = asyncio.Semaphore(3)

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT DISTINCT guild_id, map_name FROM map_alarms")
            rows = await cursor.fetchall()
            
            for row in rows:
                guild_id = row["guild_id"]
                map_name = row["map_name"]
                
                servers = await get_guild_servers(self.bot, guild_id)
                if map_name not in servers:
                    continue
                
                ip, port = servers[map_name]
                address = (ip, port)
                
                try:
                    async with semaphore:
                        players_data = await asyncio.wait_for(
                            asyncio.to_thread(a2s.players, address), timeout=6.0
                        )
                    current_names = {p.name for p in players_data if p.name}
                    
                    c_prev = await db.execute(
                        "SELECT players_json FROM map_last_players WHERE guild_id = ? AND map_name = ?",
                        (guild_id, map_name),
                    )
                    prev_row = await c_prev.fetchone()
                    prev_names = set(json.loads(prev_row["players_json"])) if prev_row else set()
                    
                    new_entries = current_names - prev_names
                    
                    if new_entries:
                        # Cargar miembros de la tribu propia
                        c_own = await db.execute("SELECT members_json FROM k4ultra_fixed_tribes WHERE guild_id = ? AND is_own = 1", (guild_id,))
                        own_members = set()
                        for row_own in await c_own.fetchall():
                            try:
                                m_list = json.loads(row_own[0])
                                for m in m_list:
                                    own_members.add(m.lower())
                            except Exception:
                                pass

                        intruders = []
                        for name in new_entries:
                            # Ignorar si está en la tribu propia fijada
                            if name.lower() in own_members:
                                continue

                            # Comprobamos si el nombre existe como Character Name O como Player Name
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
                    
                    await db.execute(
                        "INSERT OR REPLACE INTO map_last_players (guild_id, map_name, players_json) VALUES (?, ?, ?)",
                        (guild_id, map_name, json.dumps(list(current_names))),
                    )
                    await db.commit()
                except Exception:
                    pass

async def setup(bot):
    async with aiosqlite.connect(bot.db_name) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS map_alarms (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                map_name TEXT NOT NULL,
                channel_id INTEGER,
                PRIMARY KEY(guild_id, user_id, map_name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS map_last_players (
                guild_id INTEGER NOT NULL,
                map_name TEXT NOT NULL,
                players_json TEXT,
                PRIMARY KEY(guild_id, map_name)
            )
        """)
        await db.commit()
    await bot.add_cog(Alarma(bot))
