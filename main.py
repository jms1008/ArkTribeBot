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
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


# --- CONFIGURACIÓN DE LOGGING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(LOG_DIR, "bot_system.log")

# Rotación diaria, conservando 14 archivos (~2 semanas).
_root_handler = TimedRotatingFileHandler(
    log_filename, when="midnight", backupCount=14, encoding="utf-8"
)
_root_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logging.basicConfig(
    level=logging.INFO,
    handlers=[_root_handler, logging.StreamHandler()],
)

# Silenciar logs de discord.py para evitar saturación
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("discord.webhook").setLevel(logging.WARNING)

logger = logging.getLogger("ArkTribeBot")
logger.info(f"--- NUEVA SESIÓN INICIADA: {timestamp} ---")


def get_guild_logger(guild_id: int) -> logging.Logger:
    """Devuelve un logger específico para un Guild, creando la carpeta y fichero si no existen."""
    guild_log_dir = os.path.join(LOG_DIR, str(guild_id))
    if not os.path.exists(guild_log_dir):
        os.makedirs(guild_log_dir)

    logger_name = f"ArkTribeBot.guild.{guild_id}"
    guild_logger = logging.getLogger(logger_name)

    # Añadir el FileHandler solo la primera vez que se pide.
    # Rotación diaria con 14 días de retención (consistente con el logger global).
    if not guild_logger.handlers:
        guild_log_file = os.path.join(guild_log_dir, "server_event.log")
        handler = TimedRotatingFileHandler(
            guild_log_file, when="midnight", backupCount=14, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        guild_logger.addHandler(handler)
        guild_logger.setLevel(logging.INFO)
        guild_logger.propagate = (
            True  # Reenviar al logger raíz (y al StreamHandler del servidor)
        )

    return guild_logger


# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_NAME = "tribe_data.db"

# Configuración de Intents
intents = discord.Intents.default()
intents.message_content = True


class PoliciaSosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Solucionado",
        style=discord.ButtonStyle.success,
        custom_id="policia_sos_solucionado",
        emoji="✅",
    )
    async def solucionado_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.message.delete()
        await interaction.response.send_message(
            "SOS marcado como solucionado.", ephemeral=True
        )


class DismissAlarmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Completado",
        style=discord.ButtonStyle.success,
        custom_id="dismiss_alarm_btn",
        emoji="✅",
    )
    async def dismiss_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Eliminar mensaje de alarma
        await interaction.message.delete()
        # Respuesta efímera para evitar error de interacción en Discord
        await interaction.response.send_message(
            "Alarma silenciada y eliminada.", ephemeral=True
        )


# Clase del Bot
class ArkTribeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            application_id=os.getenv("APPLICATION_ID"),
        )
        self.db_name = DB_NAME
        self.log_filename = log_filename
        self.is_syncing = False
        logger.info(f"Base de datos configurada en: {os.path.abspath(self.db_name)}")

    async def setup_hook(self):
        """Se ejecuta al iniciar el bot."""
        await self.init_db()
        await self.load_extensions()

        # Registrar Listener para Logging de Comandos
        self.tree.on_command_completion = self.on_app_command_completion

        # Registro de Vistas Persistentes
        self.add_view(TodoView(self))
        self.add_view(BlacklistView(self))
        self.add_view(ScoutView(self, map_filter="Global"))
        self.add_view(BreedingDashboardView(self))
        self.add_view(PoliciaSosView())

        from cogs.k4ultra import K4UltraView

        try:
            async with aiosqlite.connect(self.db_name) as db:
                c = await db.execute("SELECT DISTINCT guild_id FROM k4ultra_messages")
                active_guilds = await c.fetchall()
                for (g_id,) in active_guilds:
                    self.add_view(K4UltraView(self, g_id))
        except Exception as e:
            logger.error(f"Error registrando vistas K4Ultra: {e}")

        from cogs.daily_points import DailyPointsView

        self.add_view(DailyPointsView())

        self.add_view(DismissAlarmView())

        # Registro de vistas dinámicas para Eventos activos
        try:
            from cogs.events import EventPollView

            async with aiosqlite.connect(self.db_name) as db:
                c = await db.execute("SELECT id FROM events WHERE status = 'active'")
                active_events = await c.fetchall()
                for (evt_id,) in active_events:
                    view = await EventPollView.build(self, evt_id)
                    self.add_view(view)
        except Exception as e:
            logger.error(f"Error registrando vistas persistentes de Eventos: {e}")

    async def on_guild_join(self, guild: discord.Guild):
        """Bienvenida automática al unirse a un nuevo servidor."""
        # Buscar el canal de sistema o el primer canal de texto accesible
        canal = guild.system_channel
        if not canal or not canal.permissions_for(guild.me).send_messages:
            # Fallback al primer canal donde el bot pueda escribir y leer
            for ch in guild.text_channels:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.view_channel:
                    canal = ch
                    break

        if not canal:
            return

        embed = discord.Embed(
            title="🦖 ¡ArkTribeBot ha completado su despliegue!",
            description=(
                "El sistema está en línea. Soy tu IA táctica para la gestión de clanes en **ARK: Survival Evolved**.\n\n"
                "Para iniciar los subsistemas, un administrador debe ejecutar la configuración inicial obligatoria."
            ),
            color=discord.Color.from_rgb(35, 135, 80),
        )

        embed.add_field(
            name="⚙️ Arranque y Configuración",
            value=(
                "El comando `/inicio_ark` vinculará el bot a este servidor y preparará todos los sub-sistemas automáticamente.\n\n"
                "💡 **RECOMENDACIÓN:** Antes de ejecutar el comando, crea en tu Discord los canales vacíos que vayas a necesitar (ej. `#todo-list`, `#scouting`, `#crianza`, `#blacklist`, `#k4ultra`, `#status`).\n\n"
                "⚠️ *La ejecución de `/inicio_ark` es estrictamente necesaria para desbloquear el resto del bot.*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🤖 Módulos Principales",
            value=(
                "👁️ **K4Ultra Intel:** Radar pasivo que monitoriza sesiones, tiempos y alianzas.\n"
                "☠️ **Blacklist:** Panel interactivo para gestionar Enemigos (KOS) y Neutrales.\n"
                "🛰️ **Scouting:** Inventario global de bases enemigas paginado.\n"
                "🚨 **Alerta SOS:** Pings estructurados y detector silencioso (`@policia`).\n"
                "🧬 **Crianza:** Dashboard de líneas estadísticas y alarmas.\n"
                "📝 **To-Do List:** Panel interactivo de tareas tribales.\n"
                "🟢 **Server Status:** Monitorización 24/7 de tus mapas."
            ),
            inline=False,
        )
        embed.add_field(
            name="👨‍👩‍👧‍👦 Gestión de Miembros (VITAL)",
            value=(
                "Para que el sistema de K/D/A y el detector de muertes funcionen:\n"
                "1. Usa `/fijar_tribu` para registrar los nombres de tus clanes aliados.\n"
                "2. Usa `/ranking_char_add` para vincular los nombres de personajes de tus miembros (ARK) con sus usuarios de Discord."
            ),
            inline=False,
        )
        embed.set_footer(text="ArkTribeBot v2.0 • By: @K4NEKIs")

        try:
            await canal.send(embed=embed)
            logger.info(f"[Bot] Bienvenida enviada: {guild.name} ({guild.id})")
        except Exception as e:
            logger.error(f"[Bot] Error enviando bienvenida en {guild.name}: {e}")

        async def _sync_guild():
            # Pequeña pausa para dejar que Discord procese la unión antes del sync
            await asyncio.sleep(5)

            if hasattr(self, "is_syncing") and self.is_syncing:
                logger.warning(
                    f"[Bot] Sincronización omitida en {guild.name}: Ya hay un sync en curso."
                )
                return

            self.is_syncing = True
            try:
                # Sync silencioso de comandos para que este servidor los tenga disponibles al instante
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Comandos sincronizados silenciosamente en {guild.name}")
            except discord.HTTPException as e:
                if e.status == 429:
                    logger.warning(
                        f"Rate limit en sync de {guild.name}. Discord reintentará automáticamente."
                    )
                else:
                    logger.error(
                        f"Error HTTP sincronizando comandos en {guild.name}: {e}"
                    )
            except Exception as e:
                logger.error(f"Error sincronizando comandos en {guild.name}: {e}")
            finally:
                self.is_syncing = False

        asyncio.create_task(_sync_guild())

    # El método on_message ha sido extraido al cog LogProcessor para mantener main.py limpio.
    # El método por defecto de commands.Bot se encargará de self.process_commands(message).

    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: app_commands.Command
    ):
        """Loguea cada comando ejecutado con sus argumentos."""
        user = interaction.user.name
        cmd_name = command.name

        args_list = []

        def parse_options(options):
            for opt in options:
                if "options" in opt:  # Subcomando o Grupo
                    args_list.append(f"subcmd:{opt['name']}")
                    parse_options(opt["options"])
                elif "value" in opt:
                    args_list.append(f"{opt['name']}='{opt['value']}'")

        if interaction.data and "options" in interaction.data:
            parse_options(interaction.data["options"])

        args_str = ", ".join(args_list) if args_list else "Sin argumentos"
        
        # Redirigir log a la guild si existe
        target_log = logger
        if interaction.guild_id:
            target_log = get_guild_logger(interaction.guild_id)
            
        target_log.info(f"EJECUCIÓN: User='{user}' | Cmd='/{cmd_name}' | Args=[{args_str}]")

    async def is_authorized_admin(self, interaction: discord.Interaction) -> bool:
        """Verifica si el usuario tiene permisos de administrador del bot en este servidor."""
        # Fallback global cuando no hay config de servidor. Configurable vía .env (BOT_OWNER_ID).
        try:
            hardcoded_owner_id = int(os.getenv("BOT_OWNER_ID", "0"))
        except ValueError:
            hardcoded_owner_id = 0
        if interaction.user.guild_permissions.administrator:
            return True
        if hardcoded_owner_id and interaction.user.id == hardcoded_owner_id:
            return True
        if interaction.guild_id:
            async with aiosqlite.connect(self.db_name) as db:
                c = await db.execute(
                    "SELECT admin_role_id, bot_owner_id FROM guild_config WHERE guild_id = ?",
                    (interaction.guild_id,),
                )
                row = await c.fetchone()
                if row:
                    admin_role_id, bot_owner_id = row
                    # Verificar el ID de propietario configurado por este servidor
                    if bot_owner_id and interaction.user.id == bot_owner_id:
                        return True
                    # Verificar el Rol de Administrador personalizado
                    if admin_role_id:
                        role = interaction.guild.get_role(admin_role_id)
                        if role and role in interaction.user.roles:
                            return True
        return False

    async def on_ready(self):
        logger.info(f"Conectado como {self.user} (ID: {self.user.id})")
        # Activity personalizado corto para evitar recortes
        await self.change_presence(
            activity=discord.CustomActivity(name="ARK | By @K4NEKIs")
        )
        
        # Refrescar todos los dashboards que se actualizan por acción (no periódicos)
        # para que reflejen el estado real de la DB al arrancar.
        try:
            async with aiosqlite.connect(self.db_name) as db:
                c = await db.execute("SELECT guild_id FROM guild_config")
                guilds = await c.fetchall()
            
            for (guild_id,) in guilds:
                try:
                    from cogs.warfare import update_blacklist_dashboards, update_kda_dashboards
                    await update_blacklist_dashboards(self, guild_id)
                    await update_kda_dashboards(self, guild_id)
                except Exception as e:
                    logger.error(f"[Startup] Error refrescando blacklist/kda guild {guild_id}: {e}")
                
                try:
                    from cogs.scouting import update_scout_dashboards
                    await update_scout_dashboards(self, guild_id)
                except Exception as e:
                    logger.error(f"[Startup] Error refrescando scouting guild {guild_id}: {e}")
                
                try:
                    from cogs.management import update_all_dashboards
                    await update_all_dashboards(self, guild_id)
                except Exception as e:
                    logger.error(f"[Startup] Error refrescando todo-list guild {guild_id}: {e}")
                
                try:
                    from cogs.breeding import update_breeding_dashboards
                    await update_breeding_dashboards(self, guild_id)
                except Exception as e:
                    logger.error(f"[Startup] Error refrescando breeding guild {guild_id}: {e}")

            logger.info("[Startup] Todos los dashboards refrescados correctamente.")
        except Exception as e:
            logger.error(f"[Startup] Error general refrescando dashboards: {e}")

    async def init_db(self):
        """Inicializa la base de datos delegando en db.schema (esquema centralizado)."""
        from db.schema import init_database

        await init_database(self.db_name)

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
