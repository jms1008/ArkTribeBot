import asyncio
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from cogs.breeding import BreedingDashboardView
from cogs.management import TodoView
from cogs.scouting import ScoutView
from cogs.warfare import BlacklistView

# --- CONFIGURACIÓN DE LOGGING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(LOG_DIR, "bot_system.log")

# Rotación diaria, conservando 14 archivos (~2 semanas).
_root_handler = TimedRotatingFileHandler(log_filename, when="midnight", backupCount=14, encoding="utf-8")
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
        handler = TimedRotatingFileHandler(guild_log_file, when="midnight", backupCount=14, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        guild_logger.addHandler(handler)
        guild_logger.setLevel(logging.INFO)
        guild_logger.propagate = True  # Reenviar al logger raíz (y al StreamHandler del servidor)

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
    async def solucionado_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("SOS marcado como solucionado.", ephemeral=True)


class DismissAlarmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Completado",
        style=discord.ButtonStyle.success,
        custom_id="dismiss_alarm_btn",
        emoji="✅",
    )
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Eliminar mensaje de alarma
        await interaction.message.delete()
        # Respuesta efímera para evitar error de interacción en Discord
        await interaction.response.send_message("Alarma silenciada y eliminada.", ephemeral=True)


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
        # `self.db` se inicializa en setup_hook tras crear el esquema.
        self.db = None
        logger.info(f"Base de datos configurada en: {os.path.abspath(self.db_name)}")

    async def setup_hook(self):
        """Se ejecuta al iniciar el bot."""
        await self.init_db()

        # Conexión persistente compartida (hot paths la usan vía ``self.bot.db``).
        from db.database import Database

        self.db = Database(self.db_name)
        await self.db.connect()

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
            active_guilds = await self.db.fetchall("SELECT DISTINCT guild_id FROM k4ultra_messages")
            for row in active_guilds:
                self.add_view(K4UltraView(self, row["guild_id"]))
        except Exception as e:
            logger.error(f"Error registrando vistas K4Ultra: {e}")

        from cogs.daily_points import DailyPointsView

        self.add_view(DailyPointsView())

        self.add_view(DismissAlarmView())

        # Registro de vistas dinámicas para Eventos activos
        try:
            from cogs.events import EventPollView

            active_events = await self.db.fetchall("SELECT id FROM events WHERE status = 'active'")
            for row in active_events:
                view = await EventPollView.build(self, row["id"])
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
                logger.warning(f"[Bot] Sincronización omitida en {guild.name}: Ya hay un sync en curso.")
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
                    logger.error(f"Error HTTP sincronizando comandos en {guild.name}: {e}")
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
            # Si la conexión persistente está disponible, usarla; fallback efímero para tests.
            if getattr(self, "db", None) is not None:
                row = await self.db.fetchone(
                    "SELECT admin_role_id, bot_owner_id FROM guild_config WHERE guild_id = ?",
                    (interaction.guild_id,),
                )
            else:
                async with aiosqlite.connect(self.db_name) as db:
                    c = await db.execute(
                        "SELECT admin_role_id, bot_owner_id FROM guild_config WHERE guild_id = ?",
                        (interaction.guild_id,),
                    )
                    row = await c.fetchone()
            if row:
                admin_role_id = row["admin_role_id"] if hasattr(row, "keys") else row[0]
                bot_owner_id = row["bot_owner_id"] if hasattr(row, "keys") else row[1]
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
        await self.change_presence(activity=discord.CustomActivity(name="ARK | By @K4NEKIs"))

        # Refrescar todos los dashboards al arrancar disparando el bus de eventos.
        # Cada cog dueño escucha su evento y refresca su UI — sin imports cruzados.
        try:
            from utils import bus

            guilds = await self.db.fetchall("SELECT guild_id FROM guild_config")
            for row in guilds:
                guild_id = row["guild_id"]
                self.dispatch(bus.BLACKLIST_UPDATED, guild_id)
                self.dispatch(bus.KDA_UPDATED, guild_id)
                self.dispatch(bus.SCOUTING_UPDATED, guild_id)
                self.dispatch(bus.TODO_UPDATED, guild_id)
                self.dispatch(bus.BREEDING_UPDATED, guild_id)

            logger.info("[Startup] Eventos de refresh disparados para todos los guilds.")
        except Exception as e:
            logger.error(f"[Startup] Error disparando eventos de refresh: {e}")

    async def init_db(self):
        """Inicializa la base de datos delegando en db.schema (esquema centralizado)."""
        from db.schema import init_database

        await init_database(self.db_name)

    async def close(self):
        """Cierre limpio: cerrar la conexión persistente antes de salir."""
        try:
            if self.db is not None:
                await self.db.close()
        finally:
            await super().close()

    async def load_extensions(self):
        """Carga todas las extensiones de ``cogs/`` que expongan ``setup()``.

        Soporta tanto archivos sueltos (``cogs/admin.py``) como paquetes
        (``cogs/k4ultra/__init__.py``). Los módulos auxiliares sin ``setup``
        (Views, helpers) se ignoran silenciosamente vía ``NoEntryPointError``
        — más robusto que una heurística por regex porque cubre ``def setup``
        definido en el archivo Y ``setup`` re-exportado desde un submódulo
        (caso del paquete ``cogs/k4ultra/__init__.py``).
        """
        from discord.ext.commands.errors import NoEntryPointError

        cogs_dir = os.path.join(BASE_DIR, "cogs")
        for entry in sorted(os.listdir(cogs_dir)):
            full_path = os.path.join(cogs_dir, entry)
            module_name: str | None = None
            display_name: str = entry

            if os.path.isdir(full_path):
                # Es un paquete si contiene __init__.py.
                if not os.path.isfile(os.path.join(full_path, "__init__.py")):
                    continue
                module_name = f"cogs.{entry}"
            elif entry.endswith(".py") and entry != "__init__.py":
                module_name = f"cogs.{entry[:-3]}"
            else:
                continue

            try:
                await self.load_extension(module_name)
                logger.info(f"Cog cargado: {display_name}")
            except NoEntryPointError:
                # Módulo sin función setup() — es un auxiliar (Views, helpers).
                logger.debug(f"[Loader] {display_name} sin setup(), se ignora")
            except Exception as e:
                logger.error(f"Error cargando {display_name}: {e}")


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
