import discord
from discord.ext import commands
from discord import app_commands
from cogs.management import TodoView
from cogs.warfare import BlacklistView
from cogs.scouting import ScoutView
from cogs.breeding import BreedingDashboardView
import os
import aiosqlite
import asyncio
from dotenv import load_dotenv
import logging
from datetime import datetime

# --- CONFIGURACIÓN DE LOGGING (Relative Path) ---
# Obtener la ruta del directorio donde está main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
log_filename = os.path.join(LOG_DIR, f"session_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Silenciar los logs de discord.py que saturan el archivo (ej: HTTP requests de editar mensajes)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.webhook').setLevel(logging.WARNING)

logger = logging.getLogger("ArkTribeBot")
logger.info(f"--- NUEVA SESIÓN INICIADA: {timestamp} ---")

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_NAME = "tribe_data.db"

# Definir Intents
intents = discord.Intents.default()
intents.message_content = True

class PoliciaSosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Solucionado", style=discord.ButtonStyle.success, custom_id="policia_sos_solucionado", emoji="✅")
    async def solucionado_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("SOS marcado como solucionado.", ephemeral=True)

class DismissAlarmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Completado", style=discord.ButtonStyle.success, custom_id="dismiss_alarm_btn", emoji="✅")
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Borrar el mensaje de alarma
        await interaction.message.delete()
        # Enviar respuesta efímera para que Discord no dé error de interacción fallida
        await interaction.response.send_message("Alarma silenciada y eliminada.", ephemeral=True)

# Clase del Bot
class ArkTribeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            application_id=os.getenv("APPLICATION_ID")
        )
        self.db_name = DB_NAME
        self.log_filename = log_filename

    async def setup_hook(self):
        """Se ejecuta al iniciar el bot."""
        await self.init_db()
        await self.load_extensions()
        
        # Registrar Listener para Logging de Comandos
        self.tree.on_command_completion = self.on_app_command_completion
        
        # Registrar Vistas Persistentes
        self.add_view(TodoView(self))
        self.add_view(BlacklistView(self))
        self.add_view(ScoutView(self, map_filter="Global"))
        self.add_view(BreedingDashboardView(self))
        self.add_view(PoliciaSosView())
        
        from cogs.k4ultra import K4UltraView
        self.add_view(K4UltraView(self))
        
        from cogs.daily_points import DailyPointsView
        self.add_view(DailyPointsView())
        
        self.add_view(DismissAlarmView())

    async def on_message(self, message: discord.Message):
        # No procesar mensajes de sí mismo
        if message.author.id == self.user.id:
            return

        # Para los webhooks o bots que mandan logs, a veces el texto viene en los Embeds
        content_lower = message.content.lower()
        if message.embeds:
            for embed in message.embeds:
                if embed.description:
                    content_lower += " " + embed.description.lower()
                if embed.title:
                    content_lower += " " + embed.title.lower()

        # Asegurar que leemos sin case sensitive
        # A veces @policia es una mención de rol real (<@&ID>) y el emoji del cuchillo es literal 🔪 
        contains_policia = "@policia" in content_lower or "<@&" in content_lower
        contains_knife = "was :knife: by" in content_lower or "fue :knife: por" in content_lower or "was 🔪 by" in content_lower or "fue 🔪 por" in content_lower
        
        if contains_knife:
            import re
            
            # Buscar el contenido original formateado
            texto_original = message.content
            if not texto_original and message.embeds and message.embeds[0].description:
                texto_original = message.embeds[0].description
                
            # Procesar SOS de Policía
            if contains_policia:
                map_match = re.search(r'\((.*?)\)', texto_original)
                map_name = map_match.group(1) if map_match else "Desconocido"
                try:
                    sos_channel = self.get_channel(1471900560776233080) or await self.fetch_channel(1471900560776233080)
                    if sos_channel:
                        view = PoliciaSosView()
                        await sos_channel.send(f"@here 🚨 **SOS en {map_name}** 🚨\n📝 Log original:\n> {texto_original}", view=view)
                except Exception as e:
                    logger.error(f"Error enviando SOS de policia: {e}")
                    
            # Procesar K/D/A Tracker (Manco)
            # Formato esperado: @here (Gn2) Day 1, 23:28: Tribemember Lacomeabuelas - Lvl 2 was :knife: by Larry Capija - Lvl 105 (UNNAMED)!
            try:
                # Normalizamos texto para facilitar regex (quitar comillas, arreglar cuchillo)
                t_clean = texto_original.replace(":knife:", "🔪").replace("was 🔪 by", "fue 🔪 por")
                
                # Buscamos: Tribemember [Victima] - Lvl [X] fue 🔪 por [Asesino] - Lvl [Y]
                # Modificamos la regex para capturar nombres que pueden contener espacios o guiones
                match = re.search(r'Tribemember (.*?) - Lvl.*?fue 🔪 por (.*?) - Lvl', t_clean, re.IGNORECASE)
                
                if match:
                    victima_char = match.group(1).strip()
                    asesino_char = match.group(2).strip()
                    
                    async with aiosqlite.connect(self.db_name) as db:
                        # Convertir personajes in-game a Jugadores Reales
                        c1 = await db.execute("SELECT player_name FROM tribe_characters WHERE character_name = ?", (victima_char,))
                        victima_res = await c1.fetchone()
                        victima_player = victima_res[0] if victima_res else None
                        
                        c2 = await db.execute("SELECT player_name FROM tribe_characters WHERE character_name = ?", (asesino_char,))
                        asesino_res = await c2.fetchone()
                        asesino_player = asesino_res[0] if asesino_res else None
                        
                        made_changes = False
                        
                        # Si ambos existen, es un TeamKill (lo ignoramos)
                        if victima_player and asesino_player:
                            logger.info(f"[KDA] Fuego amigo detectado: {asesino_player} mató a {victima_player}. Ignorado.")
                            
                        else:
                            # 1. ¿Murió alguien de la tribu?
                            if victima_player:
                                await db.execute("INSERT INTO tribe_kda (player_name, deaths) VALUES (?, 1) ON CONFLICT(player_name) DO UPDATE SET deaths = deaths + 1", (victima_player,))
                                logger.info(f"[KDA] +1 Muerte a {victima_player} (Asesinado por {asesino_char})")
                                made_changes = True
                                
                            # 2. ¿Mató alguien de la tribu?
                            if asesino_player:
                                await db.execute("INSERT INTO tribe_kda (player_name, kills) VALUES (?, 1) ON CONFLICT(player_name) DO UPDATE SET kills = kills + 1", (asesino_player,))
                                logger.info(f"[KDA] +1 Kill a {asesino_player} (Mató a {victima_char})")
                                made_changes = True
                                
                        if made_changes:
                            await db.commit()
                            # Disparar actualización de dashboards
                            try:
                                warfare_cog = self.get_cog("Warfare")
                                if warfare_cog and hasattr(warfare_cog, "update_kda_dashboards"):
                                    await warfare_cog.update_kda_dashboards()
                            except Exception as e:
                                logger.error(f"[KDA] Error recargando dashboards: {e}")
                                
            except Exception as e:
                logger.error(f"[KDA] Error parseando kill log: {e}")
                
        await self.process_commands(message)

    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        """Loguea cada comando ejecutado con sus argumentos."""
        user = interaction.user.name
        cmd_name = command.name
        
        args_list = []
        def parse_options(options):
            for opt in options:
                if 'options' in opt: # Subcomando o Grupo
                    args_list.append(f"subcmd:{opt['name']}")
                    parse_options(opt['options'])
                elif 'value' in opt:
                    args_list.append(f"{opt['name']}='{opt['value']}'")
        
        if interaction.data and 'options' in interaction.data:
            parse_options(interaction.data['options'])
        
        args_str = ", ".join(args_list) if args_list else "Sin argumentos"
        logger.info(f"EJECUCIÓN: User='{user}' | Cmd='/{cmd_name}' | Args=[{args_str}]")

    async def on_ready(self):
        logger.info(f'Conectado como {self.user} (ID: {self.user.id})')
        # Discord a veces trunca "Jugando a..." si es largo, usamos Custom Activity para que se vea completo.
        await self.change_presence(activity=discord.CustomActivity(name="ARK: Survival Evolved | By @k4nekis"))

    async def init_db(self):
        """Crea las tablas necesarias si no existen."""
        async with aiosqlite.connect(self.db_name) as db:
            # Tabla Scouts
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tribu_enemiga TEXT,
                    mapa TEXT,
                    coordenadas TEXT,
                    nivel_amenaza INTEGER,
                    url_imagen TEXT,
                    notas TEXT
                )
            """)
            
            # Tabla ToDos
            await db.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarea TEXT,
                    asignado_a INTEGER,
                    estado TEXT DEFAULT 'Pendiente'
                )
            """)
            
            # Tabla Mensajes de ToDo (Dashboard)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS todo_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            
            # Tabla Mensajes de Scout (Dashboard)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scout_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    map_filter TEXT
                )
            """)
            
            # Tabla Mensajes de Breeding (Dashboard)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS breeding_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            
            # Tabla Dinos (Breeding)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dinos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    especie TEXT,
                    sexo TEXT,
                    hp INTEGER,
                    melee INTEGER,
                    stam INTEGER,
                    weight INTEGER,
                    oxy INTEGER,
                    food INTEGER,
                    speed INTEGER,
                    mutaciones INTEGER,
                    estado TEXT
                )
            """)
            
            # Tabla Blacklist
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player TEXT,
                    tribe TEXT,
                    map TEXT,
                    notes TEXT,
                    created_at TEXT
                )
            """)

            # Tabla Mensajes de Blacklist (Dashboard)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            
            # Tabla de Mensajes de Estado Persistentes
            await db.execute("""
                CREATE TABLE IF NOT EXISTS status_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    map_name TEXT
                )
            """)
            
            # Tabla de Mensajes de Estado Global Persistentes
            await db.execute("""
                CREATE TABLE IF NOT EXISTS status_online_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            
            # Tabla de Usuarios Suscritos a Puntos Diarios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_points_users (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            # Migración para Puntos Diarios Configurable
            try:
                await db.execute("ALTER TABLE daily_points_users ADD COLUMN alert_hour INTEGER DEFAULT 8")
                await db.execute("ALTER TABLE daily_points_users ADD COLUMN timezone TEXT DEFAULT 'es'")
                await db.execute("ALTER TABLE daily_points_users ADD COLUMN last_sent_date TEXT")
            except aiosqlite.OperationalError:
                pass # Las columnas ya existen

            # Tablas K4Ultra
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_players_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    map_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_playtime (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    map_name TEXT,
                    total_minutes INTEGER DEFAULT 0,
                    last_seen DATETIME
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player1 TEXT,
                    player2 TEXT,
                    probability_score INTEGER DEFAULT 0,
                    is_manual INTEGER DEFAULT 0,
                    UNIQUE(player1, player2)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_number INTEGER,
                    embed_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    map_name TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_tribe_names (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tribe_signature TEXT UNIQUE,
                    custom_name TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_fixed_tribes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    members_json TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS k4ultra_aliases (
                    player_name TEXT PRIMARY KEY,
                    alias TEXT
                )
            """)
            
            # Tablas para el Ranking KDA (Manco)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tribe_kda (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT UNIQUE,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tribe_characters (
                    character_name TEXT PRIMARY KEY,
                    player_name TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS kda_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            
            # Tabla de Alarmas de Crianza
            await db.execute("""
                CREATE TABLE IF NOT EXISTS breeding_alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    alert_time TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("Base de datos inicializada correctamente.")

    async def load_extensions(self):
        """Carga todos los archivos .py en la carpeta cogs."""
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"Cog cargado: {filename}")
                except Exception as e:
                    logger.error(f"Error cargando {filename}: {e}")

# Ejecución
async def main():
    bot = ArkTribeBot()
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("Error: No se encontró el token en el archivo .env")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
