"""Backup automático y manual de la base de datos.

- Tarea diaria que copia `tribe_data.db` a `backups/tribe_data_YYYY-MM-DD.db`.
- Conserva los últimos 7 backups, borra los más antiguos.
- El backup manual on-demand vive en `/admin backup` (cog Admin).
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, time, timedelta, timezone

from discord.ext import commands, tasks

logger = logging.getLogger("ArkTribeBot")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
BACKUP_RETENTION = 7  # Días/archivos a conservar.
# Hora de UTC en la que se ejecuta el backup diario.
BACKUP_TIME_UTC = time(hour=4, minute=0)


def _backup_filename(date: datetime) -> str:
    return f"tribe_data_{date.strftime('%Y-%m-%d')}.db"


def _do_backup(db_path: str) -> str:
    """Realiza la copia (síncrona, idempotente para el mismo día) y devuelve la ruta."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    target = os.path.join(BACKUP_DIR, _backup_filename(datetime.now(timezone.utc)))
    shutil.copy2(db_path, target)
    return target


def _prune_old_backups() -> int:
    """Borra backups con antigüedad > BACKUP_RETENTION días. Devuelve cuántos se borraron."""
    if not os.path.isdir(BACKUP_DIR):
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION)
    removed = 0
    for fname in os.listdir(BACKUP_DIR):
        if not fname.startswith("tribe_data_") or not fname.endswith(".db"):
            continue
        full = os.path.join(BACKUP_DIR, fname)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(full), tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                os.remove(full)
                removed += 1
            except OSError as e:
                logger.warning(f"[Backup] No se pudo borrar {fname}: {e}")
    return removed


class Backup(commands.Cog):
    """Gestor de backups automáticos y comandos manuales."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.daily_backup.start()

    def cog_unload(self):
        self.daily_backup.cancel()

    @tasks.loop(time=BACKUP_TIME_UTC)
    async def daily_backup(self):
        """Backup diario a las 04:00 UTC."""
        await self.bot.wait_until_ready()
        try:
            target = _do_backup(self.bot.db_name)
            removed = _prune_old_backups()
            logger.info(
                f"[Backup] Backup diario creado: {os.path.basename(target)} (podados {removed} antiguos)"
            )
        except Exception as e:
            logger.error(f"[Backup] Falló el backup diario: {e}")

    @daily_backup.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Backup(bot))
