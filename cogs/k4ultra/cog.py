import asyncio
import json
import logging

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.k4ultra.ui import K4UltraView
from utils import bus
from utils.i18n import resolve_lang, t

logger = logging.getLogger("ArkTribeBot")


class K4Ultra(commands.Cog, name="K4Ultra"):
    # --- Grupo unificado de gestión de tribus e identidades (/tribu ...) ---
    # Reúne lo que antes eran /tribu_propia, /fijar_tribu, /unfijar_tribu,
    # /perfil_tribu, /aliados y los k4ultra_merge/split/cleanup.
    tribu = app_commands.Group(name="tribu", description="Gestión de tribus, miembros e identidades.")
    propia = app_commands.Group(name="propia", description="Tu tribu principal del servidor.", parent=tribu)
    aliada = app_commands.Group(name="aliada", description="Tribus aliadas (no disparan alarmas).", parent=tribu)

    def __init__(self, bot):
        self.bot = bot
        self.gather_player_data.start()

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard interactivo de K4Ultra."""
        from cogs.k4ultra.ui import K4UltraView
        from cogs.management import get_info_texts
        from utils.i18n import resolve_lang

        lang = await resolve_lang(self.bot, guild_id, "periodic")
        info_embed = discord.Embed(
            description=get_info_texts(lang)["k4ultra"],
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
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
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
                    t("k4.cmd.no_snapshot", lang, semana=semana), ephemeral=True
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

    @tribu.command(
        name="limpiar",
        description="[Admin] Limpia y fusiona perfiles duplicados (_1, _2) con su nombre base.",
    )
    async def k4ultra_cleanup(self, interaction: discord.Interaction):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
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
            await interaction.followup.send(t("tribu.limpiar.none", lang), ephemeral=True)
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

        await interaction.followup.send(t("tribu.limpiar.done", lang, n=merged_count), ephemeral=True)

    @tribu.command(
        name="fijar",
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
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        # Saneamiento de comillas accidentales y espacios
        nombre = nombre.strip().strip("'\"")
        miembros = [m.strip().strip("'\"") for m in jugadores.split(",") if m.strip().strip("'\"")]

        if len(miembros) < 2:
            await interaction.response.send_message(t("common.min_2_players", lang), ephemeral=True)
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
        # Solo invalida snapshot si la tribu marca confianza (propia). Las tribus
        # fijadas neutras no afectan al filtro de intrusos.
        if is_own == 1:
            self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)

        tag_propia = t("tribu.fijar.own_tag", lang) if propia else ""
        await interaction.response.send_message(
            t("tribu.fijar.done", lang, nombre=nombre, jugadores=", ".join(miembros), tag=tag_propia),
            ephemeral=True,
        )

    @propia.command(
        name="crear",
        description="[Admin] Crea y establece la tribu propia predeterminada.",
    )
    @app_commands.describe(
        nombre="Nombre de tu Tribu",
        jugadores="Jugadores de tu tribu (separados por comas)",
    )
    async def tribu_propia_crear(self, interaction: discord.Interaction, nombre: str, jugadores: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        nombre = nombre.strip().strip("'\"")
        miembros = [m.strip().strip("'\"") for m in jugadores.split(",") if m.strip().strip("'\"")]

        if len(miembros) < 2:
            await interaction.response.send_message(t("common.min_2_players", lang), ephemeral=True)
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
        self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)

        await interaction.response.send_message(
            t("tribu.propia.crear_done", lang, nombre=nombre, jugadores=", ".join(miembros)),
            ephemeral=True,
        )

    @propia.command(name="modificar", description="[Admin] Modifica parámetros de la tribu propia.")
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
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
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
            await interaction.response.send_message(t("tribu.propia.none", lang), ephemeral=True)
            return

        if opcion.value == "nombre":
            await db.execute("UPDATE k4ultra_fixed_tribes SET name = ? WHERE id = ?", (valor, row["id"]))
            await db.commit()
            await interaction.response.send_message(
                t("tribu.propia.renamed", lang, valor=valor), ephemeral=True
            )
            return

        miembros: list = json.loads(row["members_json"])

        if opcion.value == "add":
            if [m.lower() for m in miembros].count(valor.lower()) > 0:
                await interaction.response.send_message(
                    t("tribu.propia.already", lang, valor=valor, name=row["name"]), ephemeral=True
                )
                return
            miembros.append(valor)
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
                (json.dumps(miembros), row["id"]),
            )
            await db.commit()
            self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
            await interaction.response.send_message(
                t("tribu.propia.added", lang, valor=valor, name=row["name"]), ephemeral=True
            )

        elif opcion.value == "remove":
            original_len = len(miembros)
            miembros = [m for m in miembros if m.lower() != valor.lower()]
            if len(miembros) == original_len:
                await interaction.response.send_message(
                    t("tribu.propia.not_found", lang, valor=valor, name=row["name"]), ephemeral=True
                )
                return
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
                (json.dumps(miembros), row["id"]),
            )
            await db.commit()
            self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
            await interaction.response.send_message(
                t("tribu.propia.removed", lang, valor=valor, name=row["name"]), ephemeral=True
            )

    @propia.command(name="borrar", description="[Admin] Elimina la tribu propia del registro.")
    @app_commands.describe(seguro="True si estás seguro de que deseas borrarla por completo.")
    async def tribu_propia_borrar(self, interaction: discord.Interaction, seguro: bool):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        if not seguro:
            await interaction.response.send_message(t("tribu.propia.need_sure", lang), ephemeral=True)
            return

        db = self.bot.db
        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?", (interaction.guild_id,)
        )
        if cursor.rowcount == 0:
            await interaction.response.send_message(
                t("tribu.propia.none_registered", lang), ephemeral=True
            )
            return
        await db.commit()
        self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)

        await interaction.response.send_message(t("tribu.propia.deleted", lang), ephemeral=True)

    @tribu.command(
        name="desfijar",
        description="[Admin] Elimina una tribu fijada por su nombre exacto.",
    )
    @app_commands.describe(nombre="Nombre exacto de la tribu a eliminar")
    async def unfijar_tribu(self, interaction: discord.Interaction, nombre: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        nombre = nombre.strip()

        db = self.bot.db
        # Comprobamos antes del DELETE si la tribu marcaba confianza, para saber
        # si invalidar el snapshot del módulo de alarmas.
        pre = await db.fetchone(
            "SELECT is_own, is_ally FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?",
            (nombre, interaction.guild_id),
        )
        was_trusted = bool(pre and (pre["is_own"] == 1 or pre["is_ally"] == 1))

        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE name = ? AND guild_id = ?", (nombre, interaction.guild_id)
        )
        deleted = cursor.rowcount
        await db.commit()

        if deleted > 0:
            if was_trusted:
                self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
            await interaction.response.send_message(
                t("tribu.desfijar.done", lang, nombre=nombre), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t("tribu.desfijar.not_found", lang, nombre=nombre), ephemeral=True
            )

    @tribu.command(
        name="fusionar",
        description="[Admin] Fusiona toda la identidad de un nombre antiguo (origen) hacia el definitivo (destino).",
    )
    @app_commands.describe(
        origen="Nombre antiguo/secundario que ya no se usa (ej: 123_1)",
        destino="Nombre oficial y definitivo que absorberá el historial (ej: 123)",
    )
    async def tribu_fusionar(self, interaction: discord.Interaction, origen: str, destino: str):
        """Unifica DOS identidades en una. Superset de los antiguos /fusionar_perfiles
        y /k4ultra_merge: encadena player_identities_link, traslada sesiones, suma
        playtimes, reasigna relaciones del radar, preserva notas de blacklist y
        limpia alias/log. Tras esto, las futuras conexiones del nombre antiguo se
        reasignan al definitivo."""
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        origen = origen.strip()
        destino = destino.strip()
        if origen.lower() == destino.lower():
            await interaction.response.send_message(t("tribu.merge.same", lang), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild_id
        db = self.bot.db

        # 1. Encadenar identidades: cualquier alias que apuntaba a 'origen' pasa a 'destino'.
        await db.execute(
            "UPDATE player_identities_link SET primary_name = ? WHERE primary_name = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )
        await db.execute(
            "INSERT OR REPLACE INTO player_identities_link (guild_id, secondary_name, primary_name) VALUES (?, ?, ?)",
            (guild_id, origen, destino),
        )

        # 2. Trasladar sesiones (activas e inactivas).
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )

        # 3. Fusión de playtimes (suma por mapa) + métricas para el embed.
        old_playtimes = await db.fetchall(
            "SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (origen, guild_id),
        )
        transferred_minutes = sum(int(p["total_minutes"] or 0) for p in old_playtimes)
        transferred_maps = sorted({p["map_name"] for p in old_playtimes if p["map_name"]})
        for p in old_playtimes:
            prim_row = await db.fetchone(
                "SELECT total_minutes FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                (destino, p["map_name"], guild_id),
            )
            if prim_row:
                await db.execute(
                    "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = max(last_seen, ?) "
                    "WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (prim_row["total_minutes"] + p["total_minutes"], p["last_seen"], destino, p["map_name"], guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (guild_id, destino, p["map_name"], p["total_minutes"], p["last_seen"]),
                )
        await db.execute(
            "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (origen, guild_id)
        )

        # 4. Personajes in-game (alts).
        await db.execute(
            "UPDATE tribe_characters SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )

        # 5. Reasignar relaciones del radar y limpiar auto-relaciones.
        await db.execute(
            "UPDATE k4ultra_relationships SET player1 = ? WHERE player1 = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )
        await db.execute(
            "UPDATE k4ultra_relationships SET player2 = ? WHERE player2 = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )
        await db.execute(
            "DELETE FROM k4ultra_relationships WHERE player1 = player2 AND guild_id = ?", (guild_id,)
        )

        # 6. Preservar notas de blacklist al fusionar.
        row_bl = await db.fetchone(
            "SELECT notes FROM blacklist WHERE player = ? AND guild_id = ?", (origen, guild_id)
        )
        if row_bl:
            row_p_bl = await db.fetchone(
                "SELECT id, notes FROM blacklist WHERE player = ? AND guild_id = ?", (destino, guild_id)
            )
            if row_p_bl:
                combined = f"{row_p_bl['notes']} | [De {origen}]: {row_bl['notes']}"
                await db.execute("UPDATE blacklist SET notes = ? WHERE id = ?", (combined, row_p_bl["id"]))
            else:
                new_note = f"[Heredado de {origen}]: {row_bl['notes']}"
                await db.execute(
                    "UPDATE blacklist SET player = ?, notes = ? WHERE player = ? AND guild_id = ?",
                    (destino, new_note, origen, guild_id),
                )
        await db.execute("DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (origen, guild_id))

        # 7. Limpieza de alias y log del nombre antiguo.
        await db.execute(
            "DELETE FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?", (origen, guild_id)
        )
        await db.execute(
            "UPDATE k4ultra_players_log SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (destino, origen, guild_id),
        )

        # 8. Dedup de personajes que ambos pudieran compartir.
        await db.execute("""
            DELETE FROM tribe_characters
            WHERE rowid NOT IN (
                SELECT max(rowid) FROM tribe_characters GROUP BY player_name, character_name, guild_id
            )
        """)

        await db.commit()

        h_total, m_total = divmod(transferred_minutes, 60)
        horas_str = f"{h_total}h {m_total}m" if h_total else f"{m_total}m"
        mapas_str = ", ".join(transferred_maps) if transferred_maps else "—"
        embed = discord.Embed(title=t("tribu.fusionar.title", lang), color=discord.Color.brand_green())
        embed.description = t(
            "tribu.fusionar.desc",
            lang,
            origen=origen,
            destino=destino,
            horas=horas_str,
            nmaps=len(transferred_maps),
            mapas=mapas_str,
        )
        embed.set_footer(text=t("tribu.fusionar.footer", lang))
        await interaction.followup.send(embed=embed)
        self.bot.dispatch(bus.BLACKLIST_UPDATED, guild_id)

    @tribu.command(
        name="separar",
        description="[Admin] Separa la sesión actual de un jugador (origen) hacia un nuevo perfil (destino).",
    )
    @app_commands.describe(
        origen="Jugador que está conectado AHORA (ej: 123_1)",
        destino="Nuevo perfil donde moverlo (ej: 123_2)",
    )
    async def k4ultra_split(self, interaction: discord.Interaction, origen: str, destino: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        origen = origen.strip()
        destino = destino.strip()

        if origen == destino:
            await interaction.response.send_message(t("tribu.merge.same", lang), ephemeral=True)
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
            await interaction.followup.send(t("tribu.separar.no_session", lang, origen=origen), ephemeral=True)
            return

        if len(active_sessions) > 1:
            await interaction.followup.send(t("tribu.separar.multi", lang, origen=origen), ephemeral=True)
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
            t("tribu.separar.done", lang, origen=origen, destino=destino), ephemeral=True
        )

    # ------------------------------------------------------------------
    # /tribu miembro — registra la ficha de un miembro (antes /perfil_tribu)
    # ------------------------------------------------------------------
    @tribu.command(
        name="miembro",
        description="Registra la ficha completa de un miembro (Discord, Personaje, Steam, Apodo).",
    )
    @app_commands.describe(
        usuario="Usuario de Discord del jugador",
        personaje="Nombre exacto in-game del personaje en ARK",
        steam="Nombre de Steam (Como aparece en la lista de jugadores)",
        apodo="Apodo interno (Se usará de forma predeterminada si no se indica)",
        idioma="Idioma personal del usuario para las respuestas del bot (ES/EN).",
    )
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="🇪🇸 Español", value="es"),
            app_commands.Choice(name="🇬🇧 English", value="en"),
        ]
    )
    async def tribu_miembro(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        personaje: str,
        steam: str = None,
        apodo: str = None,
        idioma: app_commands.Choice[str] = None,
    ):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        jugador_nombre = usuario.display_name
        apodo_final = apodo if apodo else jugador_nombre
        steam_safe = steam if steam else "No Registrado"

        db = self.bot.db
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tribe_profiles (
                guild_id INTEGER,
                discord_id INTEGER,
                ark_character TEXT,
                steam_id TEXT,
                alias TEXT,
                UNIQUE(guild_id, discord_id)
            )
        """)
        await db.execute(
            """
            INSERT INTO tribe_profiles (guild_id, discord_id, ark_character, steam_id, alias)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, discord_id) DO UPDATE SET
                ark_character=excluded.ark_character,
                steam_id=excluded.steam_id,
                alias=excluded.alias
        """,
            (interaction.guild_id, usuario.id, personaje, steam_safe, apodo_final),
        )

        await db.execute(
            """
            INSERT INTO tribe_characters (guild_id, character_name, player_name)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, character_name) DO UPDATE SET player_name = excluded.player_name
            """,
            (interaction.guild_id, personaje, jugador_nombre),
        )
        await db.execute(
            "INSERT OR IGNORE INTO tribe_kda (guild_id, player_name, kills, deaths) VALUES (?, ?, 0, 0)",
            (interaction.guild_id, jugador_nombre),
        )
        await db.execute(
            "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, ?, ?) ON CONFLICT(guild_id, player_name) DO UPDATE SET alias=excluded.alias",
            (interaction.guild_id, personaje, apodo_final),
        )

        # Preferencia de idioma personal (opcional).
        idioma_txt = ""
        if idioma is not None:
            await db.execute(
                "INSERT INTO user_language (guild_id, user_id, lang) VALUES (?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET lang = excluded.lang",
                (interaction.guild_id, usuario.id, idioma.value),
            )
            flag = "🇪🇸" if idioma.value == "es" else "🇬🇧"
            idioma_txt = f"\n> 🌐 **Idioma:** {flag} `{idioma.value}`"

        await db.commit()

        embed = discord.Embed(title=t("tribu.miembro.title", lang), color=discord.Color.green())
        embed.description = (
            f"> 👤 **Usuario:** {usuario.mention}\n"
            f"> 📛 **In-Game:** `{personaje}`\n"
            f"> 🎭 **Apodo:** `{apodo_final}`\n"
            f"> 🎮 **Steam:** `{steam_safe}`"
            f"{idioma_txt}"
        )
        embed.set_footer(text=t("tribu.miembro.footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=False)
        self.bot.dispatch(bus.KDA_UPDATED, interaction.guild_id)

    # ------------------------------------------------------------------
    # /tribu aliada — tribus aliadas (antes /aliados)
    # ------------------------------------------------------------------
    @aliada.command(name="crear", description="[Admin] Registra una tribu aliada (no dispara alarmas).")
    @app_commands.describe(
        nombre="Nombre de la tribu aliada",
        jugadores="Jugadores aliados (separados por comas)",
    )
    async def aliada_crear(self, interaction: discord.Interaction, nombre: str, jugadores: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        miembros = [j.strip() for j in jugadores.split(",") if j.strip()]
        if not miembros:
            await interaction.response.send_message(t("tribu.aliada.no_players", lang), ephemeral=True)
            return

        db = self.bot.db
        await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE guild_id = ? AND name = ?",
            (interaction.guild_id, nombre),
        )
        await db.execute(
            "INSERT INTO k4ultra_fixed_tribes (guild_id, name, members_json, is_own, is_ally) "
            "VALUES (?, ?, ?, 0, 1)",
            (interaction.guild_id, nombre, json.dumps(miembros)),
        )
        await db.commit()
        self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
        plural = "" if len(miembros) == 1 else ("s" if lang == "en" else "es")
        await interaction.response.send_message(
            t(
                "tribu.aliada.created",
                lang,
                nombre=nombre,
                n=len(miembros),
                s=plural,
                jugadores=", ".join(miembros),
            ),
            ephemeral=True,
        )

    @aliada.command(name="modificar", description="[Admin] Modifica una tribu aliada existente.")
    @app_commands.describe(
        nombre="Nombre exacto de la tribu aliada a modificar",
        opcion="Tipo de modificación",
        valor="Nuevo nombre o jugador a añadir/quitar",
    )
    @app_commands.choices(
        opcion=[
            app_commands.Choice(name="Cambiar Nombre", value="nombre"),
            app_commands.Choice(name="Añadir Jugador", value="add"),
            app_commands.Choice(name="Quitar Jugador", value="remove"),
        ]
    )
    async def aliada_modificar(
        self,
        interaction: discord.Interaction,
        nombre: str,
        opcion: app_commands.Choice[str],
        valor: str,
    ):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        valor = valor.strip().strip("'\"")
        db = self.bot.db
        row = await db.fetchone(
            "SELECT id, name, members_json FROM k4ultra_fixed_tribes "
            "WHERE guild_id = ? AND name = ? AND is_ally = 1",
            (interaction.guild_id, nombre),
        )
        if not row:
            await interaction.response.send_message(
                t("tribu.aliada.not_exist", lang, nombre=nombre), ephemeral=True
            )
            return

        if opcion.value == "nombre":
            await db.execute("UPDATE k4ultra_fixed_tribes SET name = ? WHERE id = ?", (valor, row["id"]))
            await db.commit()
            await interaction.response.send_message(
                t("tribu.aliada.renamed", lang, nombre=nombre, valor=valor), ephemeral=True
            )
            return

        miembros = json.loads(row["members_json"])
        if opcion.value == "add":
            if any(m.lower() == valor.lower() for m in miembros):
                await interaction.response.send_message(
                    t("tribu.aliada.already", lang, valor=valor, name=row["name"]), ephemeral=True
                )
                return
            miembros.append(valor)
            await db.execute(
                "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
                (json.dumps(miembros), row["id"]),
            )
            await db.commit()
            self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
            await interaction.response.send_message(
                t("tribu.aliada.added", lang, valor=valor, name=row["name"]), ephemeral=True
            )
            return

        original = len(miembros)
        miembros = [m for m in miembros if m.lower() != valor.lower()]
        if len(miembros) == original:
            await interaction.response.send_message(
                t("tribu.aliada.not_member", lang, valor=valor, name=row["name"]), ephemeral=True
            )
            return
        await db.execute(
            "UPDATE k4ultra_fixed_tribes SET members_json = ? WHERE id = ?",
            (json.dumps(miembros), row["id"]),
        )
        await db.commit()
        self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
        await interaction.response.send_message(
            t("tribu.aliada.removed", lang, valor=valor, name=row["name"]), ephemeral=True
        )

    @aliada.command(
        name="borrar", description="[Admin] Elimina una tribu aliada (volverán a disparar alarmas)."
    )
    @app_commands.describe(nombre="Nombre exacto de la tribu aliada a borrar")
    async def aliada_borrar(self, interaction: discord.Interaction, nombre: str):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message(t("common.denied", lang), ephemeral=True)
            return

        db = self.bot.db
        cursor = await db.execute(
            "DELETE FROM k4ultra_fixed_tribes WHERE guild_id = ? AND name = ? AND is_ally = 1",
            (interaction.guild_id, nombre),
        )
        await db.commit()
        if cursor.rowcount == 0:
            await interaction.response.send_message(
                t("tribu.aliada.not_exist_short", lang, nombre=nombre), ephemeral=True
            )
            return
        self.bot.dispatch(bus.TRUSTED_MEMBERS_CHANGED, interaction.guild_id)
        await interaction.response.send_message(
            t("tribu.aliada.deleted", lang, nombre=nombre), ephemeral=True
        )

    @aliada.command(name="lista", description="Muestra las tribus aliadas registradas en el servidor.")
    async def aliada_lista(self, interaction: discord.Interaction):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        db = self.bot.db
        rows = await db.fetchall(
            "SELECT name, members_json FROM k4ultra_fixed_tribes "
            "WHERE guild_id = ? AND is_ally = 1 ORDER BY name",
            (interaction.guild_id,),
        )

        embed = discord.Embed(title=t("tribu.aliada.list_title", lang), color=discord.Color.from_rgb(80, 200, 120))
        if not rows:
            embed.description = t("tribu.aliada.list_empty", lang)
            embed.set_footer(text=t("tribu.aliada.list_empty_footer", lang))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        total_players = 0
        lines: list[str] = []
        for idx, tribe in enumerate(rows, start=1):
            try:
                members = json.loads(tribe["members_json"])
            except (json.JSONDecodeError, TypeError):
                members = []
            total_players += len(members)
            members_fmt = (
                ", ".join(f"`{m}`" for m in members)
                if members
                else t("tribu.aliada.list_empty_members", lang)
            )
            plural = "" if len(members) == 1 else ("s" if lang == "en" else "es")
            lines.append(t("tribu.aliada.list_item", lang, idx=idx, name=tribe["name"], n=len(members), s=plural))
            lines.append(f"  └ {members_fmt}")

        header = t("tribu.aliada.list_header", lang, n=len(rows), players=total_players)
        embed.description = header + "\n\n" + t("tribu.aliada.list_section", lang) + "\n" + "\n".join(lines)
        embed.set_footer(text=t("tribu.aliada.list_footer", lang))
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    # La tabla player_identities_link se crea en db/schema.py (init_db).
    await bot.add_cog(K4Ultra(bot))
