"""Bus de eventos interno del bot (basado en discord.py dispatch).

En discord.py, ``bot.dispatch("foo", *args)`` invoca todos los listeners
registrados como ``on_foo`` en cogs (``@commands.Cog.listener()``).

Aquí centralizamos los nombres de eventos como constantes para evitar typos
y facilitar la búsqueda de productores/consumidores con grep.

Convención: el productor sólo dispara el evento. El cog dueño del dashboard
escucha y refresca su UI. Esto rompe los imports cruzados entre cogs.

Productor (cualquier cog que muta datos)::

    self.bot.dispatch(events.BLACKLIST_UPDATED, guild_id)

Consumidor (cog dueño del dashboard)::

    @commands.Cog.listener()
    async def on_blacklist_updated(self, guild_id: int):
        await update_blacklist_dashboards(self.bot, guild_id)
"""

from __future__ import annotations

# --- Nombres de evento (lo que se pasa a bot.dispatch) -------------------
# Importante: el nombre **NO** debe llevar el prefijo "on_". discord.py lo
# añade automáticamente al buscar el listener.

BLACKLIST_UPDATED = "blacklist_updated"
"""Se ha modificado la blacklist de un guild. Args: (guild_id: int,)."""

KDA_UPDATED = "kda_updated"
"""Se han modificado los contadores KDA. Args: (guild_id: int,)."""

SCOUTING_UPDATED = "scouting_updated"
"""Se ha modificado la información de scouting. Args: (guild_id: int,)."""

TODO_UPDATED = "todo_updated"
"""Se ha modificado la lista de tareas. Args: (guild_id: int,)."""

BREEDING_UPDATED = "breeding_updated"
"""Se han modificado las líneas de crianza. Args: (guild_id: int,)."""

TRUSTED_MEMBERS_CHANGED = "trusted_members_changed"
"""La lista de miembros "confiables" (tribu propia / aliados) ha cambiado en un
guild. El cog de Alarmas reacciona limpiando ``map_last_players`` para forzar
una re-evaluación de todos los jugadores actualmente online en el próximo tick.
Args: (guild_id: int,)."""

# --- Tabla de eventos publicables (utilidad para tests/documentación) ----
ALL_EVENTS: tuple[str, ...] = (
    BLACKLIST_UPDATED,
    KDA_UPDATED,
    SCOUTING_UPDATED,
    TODO_UPDATED,
    BREEDING_UPDATED,
    TRUSTED_MEMBERS_CHANGED,
)
