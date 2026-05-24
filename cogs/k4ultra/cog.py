import asyncio
import json
import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.k4ultra.ui import K4UltraView

logger = logging.getLogger("ArkTribeBot")


class K4Ultra(commands.Cog, name="K4Ultra"):
    def __init__(self, bot):
        self.bot = bot
        self.gather_player_data.start()

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard interactivo de K4Ultra."""
        from cogs.k4ultra.ui import K4UltraView
        from cogs.management import INFO_TEXTS

        info_embed = discord.Embed(
            description=INFO_TEXTS["k4ultra"],
            color=discord.Color.from_rgb(43, 45, 49),
        )
        await channel.send(embed=info_embed)

        pages_k, top_players_k, k4_aliases_k = await self.generate_k4ultra_embed(guild_id)
        view_k = K4UltraView(self.bot, guild_id, top_players_k, k4_aliases_k)
        msg = await channel.send(embed=pages_k[0], view=view_k)
        await asyncio.sleep(0.5)

        db = self.bot.db
        await db.execute(
            "INSERT INTO k4ultra_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (guild_id, channel.id, msg.id),
        )
        await db.commit()
        self.calculate_relationships.start()

    def cog_unload(self):
        self.gather_player_data.cancel()
        self.calculate_relationships.cancel()

    @tasks.loop(minutes=1)
    async def gather_player_data(self):
        """Recoge datos de jugadores cada minuto.

        Cuerpo extraído a ``cogs.k4ultra.sessions.run`` — el decorador
        ``@tasks.loop`` debe quedarse en el cog por restricciones de discord.py.
        """
        await self.bot.wait_until_ready()
        from cogs.k4ultra import sessions

        await sessions.run(self.bot)

    @gather_player_data.error
    async def gather_player_data_error(self, error):
        logger.error(
            f"[K4Ultra] Error CRÍTICO en task gather_player_data: {error}",
            exc_info=True,
        )

    @tasks.loop(hours=24)
    async def calculate_relationships(self):
        """Recalcula las relaciones cada 24 h.

        Cuerpo extraído a ``cogs.k4ultra.relationships.run``.
        """
        await self.bot.wait_until_ready()
        from cogs.k4ultra import relationships

        await relationships.run(self.bot)

    async def generate_k4ultra_embed(self, guild_id: int, mode: str = "radar") -> tuple[list, list, dict]:
        """Wrapper compatible. La implementación vive en ``cogs.k4ultra.embeds``."""
        from cogs.k4ultra.embeds import generate_k4ultra_embed

        return await generate_k4ultra_embed(self.bot, guild_id, mode)

    @app_commands.command(
        name="k4ultra",
        description="Muestra información detallada de jugadores, tiempos y relaciones.",
    )
    @app_commands.describe(
        semana="Opcional. Número de semana para ver el histórico de esa semana.",
        modo="Opcional. Selecciona si ver radar o tribus (por defecto radar).",
    )
    @app_commands.choices(
        modo=[
            app_commands.Choice(name="Radar y Ranking", value="radar"),
            app_commands.Choice(name="Explorador de Tribus", value="tribus"),
        ]
    )
    async def k4ultra_command(
        self, interaction: discord.Interaction, semana: int = None, modo: str = "radar"
    ):

        # Validación de permisos (Admin o ID autorizado)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ **ACCESO DENEGADO.**", ephemeral=True)
            return

        if semana:
            # Consulta de Snapshot histórico
            await interaction.response.defer(ephemeral=True)
            db = self.bot.db
            cursor = await db.execute(
                "SELECT embed_json FROM k4ultra_snapshots WHERE week_number = ? AND guild_id = ?",
                (semana, interaction.guild_id),
            )
            row = await cursor.fetchone()

            if row:
                embed_dict = json.loads(row[0])
                snap_embed = discord.Embed.from_dict(embed_dict)
                await interaction.followup.send(embed=snap_embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ No se encontró un snapshot para la semana {semana}.",
                    ephemeral=True,
                )
        else:
            # Visualización de estadísticas en vivo y guardado como mensaje persistente
            await interaction.response.defer(ephemeral=False)
            pages, top_players, k4_aliases = await self.generate_k4ultra_embed(interaction.guild_id, modo)
            view = (
                K4UltraView(self.bot, interaction.guild_id, top_players, k4_aliases, pages=pages)
                if modo != "tribus"
                else None
            )

            try:
                if view:
                    message = await interaction.followup.send(embed=pages[0], view=view)
                else:
                    message = await interaction.followup.send(embed=pages[0])
            except discord.HTTPException as e:
                logger.error(f"[K4Ultra Debug] HTTPException on send: {e}")
                logger.error(f"[K4Ultra Debug] Embed payload: {pages[0].to_dict()}")
                raise e

            db = self.bot.db
            await db.execute(
                """
                INSERT INTO k4ultra_messages (guild_id, channel_id, message_id, mode)
                VALUES (?, ?, ?, ?)
            """,
                (interaction.guild_id, interaction.channel_id, message.id, modo),
            )
            await db.commit()

    @app_commands.command(
        name="k4ultra_cleanup",
        description="[Admin] Limpia y fusiona perfiles duplicados (_1, _2) con su nombre base.",
    )
    async def k4ultra_cleanup(self, interaction: discord.Interaction):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Búsqueda de jugadores con sufijos numéricos (ej. _1, _2)
        import re

        cursor = await db.execute(
            "SELECT DISTINCT player_name FROM k4ultra_playtime WHERE guild_id = ?", (interaction.guild_id,)
        )
        all_players = [r["player_name"] for r in await cursor.fetchall()]

        # Identificación de nombres base y copias asociadas
        duplicates_to_merge = []
        generic_names = {"123", "human", "humano", "survivor", "player", "bob"}

        for p in all_players:
            match = re.search(r"^(.*)_(\d+)$", p)
            if match:
                base_name = match.group(1)
                # Exclusión de nombres genéricos en la fusión (comparten base de forma legítima)
                if base_name.lower() not in generic_names:
                    duplicates_to_merge.append((p, base_name))

        if not duplicates_to_merge:
            await interaction.followup.send(
                "✅ No se encontraron perfiles duplicados para fusionar.",
                ephemeral=True,
            )
            return

        merged_count = 0
        for dup_name, base_name in duplicates_to_merge:
            # 1. Fusión de Playtime (Minutos jugados)
            cursor = await db.execute(
                "SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
                (dup_name, interaction.guild_id),
            )
            dup_maps = await cursor.fetchall()

            for dm in dup_maps:
                # Comprobación de existencia de Playtime previo para el nombre base en ese mapa
                c2 = await db.execute(
                    "SELECT total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (base_name, dm["map_name"], interaction.guild_id),
                )
                base_map = await c2.fetchone()

                if base_map:
                    # Suma de minutos reteniendo la última conexión ("last_seen")
                    new_mins = base_map["total_minutes"] + dm["total_minutes"]
                    new_last_seen = max(base_map["last_seen"], dm["last_seen"])
                    await db.execute(
                        "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = ? WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                        (new_mins, new_last_seen, base_name, dm["map_name"], interaction.guild_id),
                    )
                else:
                    # Inserción de registro nuevo bajo el nombre base
                    await db.execute(
                        "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                        (
                            interaction.guild_id,
                            base_name,
                            dm["map_name"],
                            dm["total_minutes"],
                            dm["last_seen"],
                        ),
                    )

            await db.execute(
                "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
                (dup_name, interaction.guild_id),
            )

            # 2. Actualización de Sesiones
            await db.execute(
                "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            # 3. Actualización de Relaciones
            # Modificación cuidadosa de pares para evitar pérdida de datos
            await db.execute(
                "UPDATE k4ultra_relationships SET player1 = ? WHERE player1 = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )
            await db.execute(
                "UPDATE k4ultra_relationships SET player2 = ? WHERE player2 = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            # Limpieza de auto-relaciones generadas por la fusión
            await db.execute(
                "DELETE FROM k4ultra_relationships WHERE player1 = player2 AND guild_id = ?",
                (interaction.guild_id,),
            )

            # 4. Limpieza en Blacklist y Alias
            await db.execute(
                "DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (dup_name, interaction.guild_id)
            )
            await db.execute(
                "DELETE FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?",
                (dup_name, interaction.guild_id),
            )
            await db.execute(
                "UPDATE k4ultra_players_log SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (base_name, dup_name, interaction.guild_id),
            )

            merged_count += 1

        await db.commit()

        await interaction.followup.send(
            f"✅ Limpieza completada. Se han fusionado **{merged_count}** perfiles duplicados con sus nombres base.",
            ephemeral=True,
        )

    @app_commands.command(
        name="fijar_tribu",
        description="[Admin] Fija una tribu para que el algoritmo no añada jugadores externos.",
    )
    @app_commands.describe(
        nombre="Nombre de la tribu",
        jugadores="Nombres de los jugadores separados por coma",
        propia="Opcional. Marca True si esta es tu tribu (aparecerá destacada).",
    )
    async def fijar_tribu(
        self, interaction: discord.Interaction, nombre: str, jugadores: str, propia: bool = False
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        # Saneamiento de comillas accidentales y espacios
        nombre = nombre.strip().strip("'\"")
        miembros = [m.strip().strip("'\"") for m in jugadores.split(",") if m.strip().strip("'\"")]

        if len(miembros) < 2:
            await interaction.response.send_message(
                "❌ Debes especificar al menos 2 jugadores válidos separados por comas.",
                ephemeral=True,
            )
            return

        db = self.bot.db
        import json

        is_own = 1 if propia else 0
        if is_own == 1:
            # Quitar is_own a todas las de la guild para que solo haya 1 propia
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET is_own = 0 WHERE guild_id = ?", (interaction.guild_id,)
            )

        await db.execute(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, nombre, json.dumps(miembros), is_own),
        )
        await db.commit()

        tag_propia = "\n🌟 Ha sido marcada como TU TRIBU PROPIA." if propia else ""
        await interaction.response.send_message(
            f"✅ Tribu fijada: **{nombre}** con los jugadores: {', '.join(miembros)}.\nEl algoritmo no añadirá jugadores externos a este bloque.{tag_propia}",
            ephemeral=True,
        )

    tribu_propia_group = app_commands.Group(
        name="tribu_propia",
        description="Gestión de la tribu principal del servidor.",
    )

    @tribu_propia_group.command(
        name="crear",
        description="[Admin] Crea y establece la tribu propia predeterminada.",
    )
    @app_commands.describe(
        nombre="Nombre de tu Tribu",
        jugadores="Jugadores de tu tribu (separados por comas)",
    )
    async def tribu_propia_crear(self, interaction: discord.Interaction, nombre: str, jugadores: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        nombre = nombre.strip().strip("'\"")
        miembros = [m.strip().strip("'\"") for m in jugadores.split(",") if m.strip().strip("'\"")]

        if len(miembros) < 2:
            await interaction.response.send_message(
                "❌ Debes especificar al menos 2 jugadores válidos separados por comas.", ephemeral=True
            )
            return

        db = self.bot.db
        import json

        # Desmarcar las anteriores para evitar conflictos
        await db.execute(
            "UPDATE k4ultra_fixed_tribes SET is_own = 0 WHERE guild_id = ?", (interaction.guild_id,)
        )

        # Buscamos si existía una con el mismo nombre para sobrescribirla limpiamente
        await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?", (nombre, interaction.guild_id)
        )

        await db.execute(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own) VALUES (?, ?, ?, 1)",
            (interaction.guild_id, nombre, json.dumps(miembros)),
        )
        await db.commit()

        await interaction.response.send_message(
            f"✅ Se ha configurado **{nombre}** como tribu propia con los jugadores: {', '.join(miembros)}.",
            ephemeral=True,
        )

    @tribu_propia_group.command(
        name="modificar", description="[Admin] Modifica parámetros de la tribu propia."
    )
    @app_commands.describe(
        opcion="Qué tipo de modificación deseas aplicar",
        valor="El nuevo nombre o el miembro a alterar",
    )
    @app_commands.choices(
        opcion=[
            app_commands.Choice(name="Cambiar Nombre de Tribu", value="nombre"),
            app_commands.Choice(name="Añadir Miembro", value="add"),
            app_commands.Choice(name="Eliminar Miembro", value="remove"),
        ]
    )
    async def tribu_propia_modificar(
        self, interaction: discord.Interaction, opcion: app_commands.Choice[str], valor: str
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        valor = valor.strip().strip("'\"")

        db = self.bot.db
        import json

        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?",
            (interaction.guild_id,),
        )
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                "❌ No hay tribu propia configurada. Usa `/tribu_propia crear` primero.", ephemeral=True
            )
            return

        if opcion.value == "nombre":
            await db.execute("UPDATE k4ultra_fixed_tribes SET name = ? WHERE id = ?", (valor, row["id"]))
            await db.commit()
            await interaction.response.send_message(
                f"✅ Se cambió el nombre de la tribu propia a **{valor}**.", ephemeral=True
            )
            return

        miembros: list = json.loads(row["members_json"])

        if opcion.value == "add":
            if [m.lower() for m in miembros].count(valor.lower()) > 0:
                await interaction.response.send_message(
                    f"⚠️ **{valor}** ya está en la tribu propia (**{row['name']}**).", ephemeral=True
                )
                return
            miembros.append(valor)
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
                (json.dumps(miembros), row["id"]),
            )
            await db.commit()
            await interaction.response.send_message(
                f"✅ Se añadió a **{valor}** a la tribu propia (**{row['name']}**).", ephemeral=True
            )

        elif opcion.value == "remove":
            original_len = len(miembros)
            miembros = [m for m in miembros if m.lower() != valor.lower()]
            if len(miembros) == original_len:
                await interaction.response.send_message(
                    f"❌ **{valor}** no fue encontrado en la tribu propia (**{row['name']}**).",
                    ephemeral=True,
                )
                return
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
                (json.dumps(miembros), row["id"]),
            )
            await db.commit()
            await interaction.response.send_message(
                f"✅ Se eliminó a **{valor}** de la tribu propia (**{row['name']}**).", ephemeral=True
            )

    @tribu_propia_group.command(name="borrar", description="[Admin] Elimina la tribu propia del registro.")
    @app_commands.describe(seguro="True si estás seguro de que deseas borrarla por completo.")
    async def tribu_propia_borrar(self, interaction: discord.Interaction, seguro: bool):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        if not seguro:
            await interaction.response.send_message(
                "❌ Debes seleccionar `seguro: True` para borrar la tribu propia definitivamente.",
                ephemeral=True,
            )
            return

        db = self.bot.db
        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?", (interaction.guild_id,)
        )
        if cursor.rowcount == 0:
            await interaction.response.send_message(
                "❌ No hay tribu propia registrada actualmente.", ephemeral=True
            )
            return
        await db.commit()

        await interaction.response.send_message(
            "✅ Has borrado permanentemente la tribu propia del servidor.", ephemeral=True
        )

    @app_commands.command(
        name="unfijar_tribu",
        description="[Admin] Elimina una tribu fijada por su nombre exacto.",
    )
    @app_commands.describe(nombre="Nombre exacto de la tribu a eliminar")
    async def unfijar_tribu(self, interaction: discord.Interaction, nombre: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        nombre = nombre.strip()

        db = self.bot.db
        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?", (nombre, interaction.guild_id)
        )
        deleted = cursor.rowcount
        await db.commit()

        if deleted > 0:
            await interaction.response.send_message(
                f"✅ Tribu **{nombre}** ha sido eliminada de las fijadas. Sus miembros volverán a agruparse automáticamente.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ No se encontró ninguna tribu fijada con el nombre **{nombre}**.",
                ephemeral=True,
            )

    @app_commands.command(
        name="k4ultra_merge",
        description="[Admin] Fusiona MANUALMENTE un perfil duplicado (origen) hacia un perfil base (destino).",
    )
    @app_commands.describe(
        origen="Perfil a eliminar y fusionar (ej: 123_1)",
        destino="Perfil base que absorberá las horas (ej: 123)",
    )
    async def k4ultra_merge(self, interaction: discord.Interaction, origen: str, destino: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        origen = origen.strip()
        destino = destino.strip()

        if origen == destino:
            await interaction.response.send_message(
                "❌ El origen y el destino no pueden ser el mismo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Verificación de existencia del perfil de origen
        cursor = await db.execute(
            "SELECT * FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (origen, interaction.guild_id),
        )
        origen_maps = await cursor.fetchall()
        if not origen_maps:
            await interaction.followup.send(
                f"❌ El jugador origen **{origen}** no tiene registros de tiempo, o no existe.",
                ephemeral=True,
            )
            return

        # 1. Merge Playtime
        for dm in origen_maps:
            c2 = await db.execute(
                "SELECT total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                (destino, dm["map_name"], interaction.guild_id),
            )
            base_map = await c2.fetchone()

            if base_map:
                new_mins = base_map["total_minutes"] + dm["total_minutes"]
                new_last_seen = max(base_map["last_seen"], dm["last_seen"])
                await db.execute(
                    "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = ? WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (new_mins, new_last_seen, destino, dm["map_name"], interaction.guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (interaction.guild_id, destino, dm["map_name"], dm["total_minutes"], dm["last_seen"]),
                )

        await db.execute(
            "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (origen, interaction.guild_id),
        )

        # 2. Update Sessions
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )

        # 3. Update Relationships
        await db.execute(
            "UPDATE k4ultra_relationships SET player1 = ? WHERE player1 = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )
        await db.execute(
            "UPDATE k4ultra_relationships SET player2 = ? WHERE player2 = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )
        await db.execute(
            "DELETE FROM k4ultra_relationships WHERE player1 = player2 AND guild_id = ?",
            (interaction.guild_id,),
        )

        # 4. Cleanup Blacklist and Aliases
        await db.execute(
            "DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (origen, interaction.guild_id)
        )
        await db.execute(
            "DELETE FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?",
            (origen, interaction.guild_id),
        )
        await db.execute(
            "UPDATE k4ultra_players_log SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, interaction.guild_id),
        )

        await db.commit()

        await interaction.followup.send(
            f"✅ ¡Fusión manual completada con éxito!\nTodas las horas e información de **{origen}** han sido traspasadas a **{destino}**.",
            ephemeral=True,
        )

    @app_commands.command(
        name="k4ultra_split",
        description="[Admin] Separa la SESIÓN ACTUAL de un jugador (origen) hacia un nuevo perfil (destino).",
    )
    @app_commands.describe(
        origen="Jugador que está conectado AHORA (ej: 123_1)",
        destino="Nuevo perfil donde moverlo (ej: 123_2)",
    )
    async def k4ultra_split(self, interaction: discord.Interaction, origen: str, destino: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        origen = origen.strip()
        destino = destino.strip()

        if origen == destino:
            await interaction.response.send_message(
                "❌ El origen y el destino no pueden ser el mismo.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        db = self.bot.db

        # Comprobación de existencia de sesión activa para el perfil de origen
        cursor = await db.execute(
            "SELECT id, map_name FROM k4ultra_sessions WHERE player_name = ? AND is_active = 1 AND guild_id = ?",
            (origen, interaction.guild_id),
        )
        active_sessions = await cursor.fetchall()

        if not active_sessions:
            await interaction.followup.send(
                f"❌ El jugador **{origen}** NO tiene ninguna sesión activa en este momento. Este comando solo sirve para separar a un impostor mientras está conectado.",
                ephemeral=True,
            )
            return

        if len(active_sessions) > 1:
            await interaction.followup.send(
                f"⚠️ **{origen}** tiene múltiples sesiones activas extrañas. Contacta al soporte técnico.",
                ephemeral=True,
            )
            return

        session_id = active_sessions[0]["id"]
        map_name = active_sessions[0]["map_name"]

        # 1. Modificación de identidad en la sesión activa
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE id = ? AND guild_id = ?",
            (destino, session_id, interaction.guild_id),
        )

        # 2. Garantía de existencia del destino en Playtime (prevención de errores visuales)
        cursor = await db.execute(
            "SELECT total_minutes FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
            (destino, map_name, interaction.guild_id),
        )
        if not await cursor.fetchone():
            import datetime as dt

            now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, 0, ?)",
                (interaction.guild_id, destino, map_name, now_str),
            )

        await db.commit()

        await interaction.followup.send(
            f"✅ ¡Sesión separada!\nEl impostor que estaba usando **{origen}** ahora es rastreado como **{destino}**.\nLa sesión actual ya ha sido purgada del historial de **{origen}**.",
            ephemeral=True,
        )


async def setup(bot):
    # La tabla player_identities_link se crea en db/schema.py (init_db).
    await bot.add_cog(K4Ultra(bot))
