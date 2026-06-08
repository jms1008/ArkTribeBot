import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from locales.guides_en import INFO_TEXTS_EN
from locales.guides_es import INFO_TEXTS
from utils import bus
from utils.i18n import resolve_lang, t

logger = logging.getLogger("ArkTribeBot")


def get_info_texts(lang: str = "es") -> dict:
    """Devuelve el diccionario de guías de /info y /help para el idioma dado."""
    return INFO_TEXTS_EN if lang == "en" else INFO_TEXTS


class TodoView(discord.ui.View):
    def __init__(self, bot, page: int = 0, total_rows: int = 0, lang: str = "es"):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = page
        self.total_rows = total_rows
        self.lang = lang

        # Etiquetas traducibles de los botones de acción.
        self.add_task_btn.label = t("todo.btn.add", lang)
        self.claim_task.label = t("todo.btn.claim", lang)
        self.delete_task.label = t("todo.btn.delete", lang)

        # Deshabilitar botones de paginación si procede
        total_pages = max(1, (self.total_rows + 10 - 1) // 10)
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= total_pages - 1

    @discord.ui.button(
        label="Añadir Tarea",
        style=discord.ButtonStyle.success,
        custom_id="todo_add_btn",
    )
    async def add_task_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddTaskModal(self.bot))

    @discord.ui.button(
        label="Reclamar Tarea",
        style=discord.ButtonStyle.primary,
        custom_id="todo_claim",
    )
    async def claim_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ClaimTaskModal(self.bot))

    @discord.ui.button(
        label="Eliminar Tarea",
        style=discord.ButtonStyle.danger,
        custom_id="todo_delete",
    )
    async def delete_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteTaskModal(self.bot))

    @discord.ui.button(
        label="◀️",
        style=discord.ButtonStyle.blurple,
        custom_id="todo_prev_btn",
    )
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re

        current_page = 0
        if interaction.message.embeds and interaction.message.embeds[0].footer.text:
            # Language-agnostic: extrae el patrón "N/N" sin depender de "Página"/"Page".
            m = re.search(r"(\d+)/(\d+)", interaction.message.embeds[0].footer.text)
            if m:
                current_page = int(m.group(1)) - 1
        new_page = max(0, current_page - 1)
        await self._update_page(interaction, new_page)

    @discord.ui.button(
        label="▶️",
        style=discord.ButtonStyle.blurple,
        custom_id="todo_next_btn",
    )
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re

        current_page = 0
        total_pages = 1
        if interaction.message.embeds and interaction.message.embeds[0].footer.text:
            # Language-agnostic: extrae "N/N" sin depender del literal "Página"/"Page".
            m = re.search(r"(\d+)/(\d+)", interaction.message.embeds[0].footer.text)
            if m:
                current_page = int(m.group(1)) - 1
                total_pages = int(m.group(2))
        new_page = min(total_pages - 1, current_page + 1)
        await self._update_page(interaction, new_page)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        db = self.bot.db
        cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (interaction.guild_id,))
        rows = await cursor.fetchall()

        lang = await resolve_lang(self.bot, interaction.guild_id, "periodic")
        embed, page, view = build_todo_embed_view(self.bot, rows, new_page, lang=lang)
        await interaction.response.edit_message(embed=embed, view=view)


def _format_assignees(raw: str | None, lang: str = "es") -> str:
    """Normaliza el campo asignado_a a una cadena de menciones Discord."""
    if not raw:
        return t("todo.unassigned", lang)
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    fixed = []
    for p in parts:
        core = p.replace("<@", "").replace(">", "")
        if core.isdigit():
            fixed.append(f"<@{core}>")
        else:
            fixed.append(core)
    return ", ".join(fixed) if fixed else t("todo.unassigned", lang)


def _render_todo_item(row, lang: str = "es") -> list[str]:
    """Renderiza una tarea como 2 líneas: encabezado + asignado.

    Patrón visual unificado con Blacklist/Scouting:
    ``#ID + emoji + **tarea**`` y debajo ``└ 👤 mention``.
    """
    icon = "🔨" if row["estado"] != "Pendiente" else "⏳"
    return [
        f"`#{row['id']:03d}` {icon} **{row['tarea']}**",
        f"  └ 👤 {_format_assignees(row['asignado_a'], lang)}",
    ]


def build_todo_embed_view(bot, rows: list, page: int = 0, lang: str = "es"):
    """Construye el embed del panel de To-Do con el patrón visual unificado.

    Diseño (consistente con Blacklist/Scouting/Ranking):
    - Header: emoji + título mayúscula
    - Badges de contador en code-block (`` `N` ``)
    - Secciones agrupadas por estado (🔨 EN PROGRESO primero, luego ⏳ PENDIENTES)
    - Items con jerarquía: ``#ID emoji tarea`` + ``└ 👤 asignado``
    - Footer: paginación + total + hint
    """
    page_size = 10
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))

    start = page * page_size
    chunk = rows[start : start + page_size]

    embed = discord.Embed(title=t("todo.title", lang), color=discord.Color.from_rgb(255, 165, 0))

    if not rows:
        embed.description = t("todo.empty", lang)
        embed.set_footer(text=t("todo.empty_footer", lang))
        view = TodoView(bot, page=0, total_rows=0, lang=lang)
        return embed, 0, view

    n_pending = sum(1 for r in rows if r["estado"] == "Pendiente")
    n_progress = total - n_pending

    # Cabecera con counter de badges en code-block (estilo Blacklist).
    lines: list[str] = [
        t("todo.badges", lang, progress=n_progress, pending=n_pending, total=total),
        "",
    ]

    # Separar por estado, manteniendo el orden original dentro de cada grupo.
    in_progress = [r for r in chunk if r["estado"] != "Pendiente"]
    pending = [r for r in chunk if r["estado"] == "Pendiente"]

    if in_progress:
        lines.append(t("todo.section.progress", lang))
        for row in in_progress:
            lines.extend(_render_todo_item(row, lang))
            lines.append("")

    if pending:
        if in_progress:
            lines.append("")  # separador extra entre secciones
        lines.append(t("todo.section.pending", lang))
        for row in pending:
            lines.extend(_render_todo_item(row, lang))
            lines.append("")

    embed.description = "\n".join(lines).strip()
    embed.set_footer(text=t("todo.footer", lang, page=page + 1, pages=total_pages, total=total))
    view = TodoView(bot, page=page, total_rows=total, lang=lang)
    return embed, page, view


async def update_all_dashboards(bot, guild_id: int, page: int = 0):
    """Actualiza todos los mensajes de lista de tareas registrados en el servidor actual."""
    # 1. Generación del nuevo Embed
    db = bot.db
    cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (guild_id,))
    rows = await cursor.fetchall()

    lang = await resolve_lang(bot, guild_id, "periodic")
    embed, current_page, view = build_todo_embed_view(bot, rows, page, lang=lang)
    # 2. Búsqueda y edición de mensajes registrados
    messages_to_remove = []
    db = bot.db
    cursor = await db.execute(
        "SELECT id, channel_id, message_id FROM todo_messages WHERE guild_id = ?", (guild_id,)
    )
    msg_rows = await cursor.fetchall()

    for row in msg_rows:
        try:
            channel = bot.get_channel(row["channel_id"]) or await bot.fetch_channel(row["channel_id"])
            if channel:
                message = await channel.fetch_message(row["message_id"])
                await message.edit(embed=embed, view=view)
            else:
                messages_to_remove.append(row["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(row["id"])  # Inaccesible (borrado o sin permisos)
        except Exception as e:
            logger.error(f"[Management] Error actualizando dashboard {row['id']}: {e}")

    # Limpieza de registros inactivos
    if messages_to_remove:
        for mid in messages_to_remove:
            await db.execute("DELETE FROM todo_messages WHERE id = ?", (mid,))
        await db.commit()


class AddTaskModal(discord.ui.Modal, title="Añadir Nueva Tarea"):
    tarea_content = discord.ui.TextInput(
        label="Descripción de la Tarea",
        style=discord.TextStyle.paragraph,
        placeholder="¿Qué hay que hacer?",
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        tarea = self.tarea_content.value
        db = self.bot.db
        await db.execute(
            "INSERT INTO todos (guild_id, tarea) VALUES (?, ?)",
            (
                interaction.guild_id,
                tarea,
            ),
        )
        await db.commit()

        await interaction.response.send_message(f"✅ Tarea añadida: **{tarea}**", ephemeral=False)
        await update_all_dashboards(self.bot, interaction.guild_id)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Management] Auto-delete falló (AddTaskModal): {e}")


class ClaimTaskModal(discord.ui.Modal, title="Reclamar Tarea"):
    task_id = discord.ui.TextInput(label="ID de la Tarea", placeholder="Introduce el número ID")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        t_id = self.task_id.value
        try:
            tid_int = int(t_id)
        except ValueError:
            await interaction.response.send_message("❌ El ID debe ser un número.", ephemeral=True)
            return

        db = self.bot.db
        # Verificar si la tarea existe y recuperar datos actuales
        cursor = await db.execute(
            "SELECT asignado_a FROM todos WHERE id = ? AND guild_id = ?",
            (tid_int, interaction.guild_id),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message(
                f"❌ La tarea **#{tid_int}** no existe en este servidor.",
                ephemeral=True,
            )
            return

        actual_assignee = row["asignado_a"]
        actual_assignee_str = str(actual_assignee) if actual_assignee else ""
        user_mention = f"<@{interaction.user.id}>"
        user_id_str = str(interaction.user.id)
        user_name = interaction.user.display_name

        assignees = [a.strip() for a in actual_assignee_str.split(",") if a.strip()]

        encontrado = False
        for a in assignees:
            core = a.replace("<@", "").replace(">", "")
            if core == user_id_str or core.lower() == user_name.lower():
                assignees.remove(a)
                encontrado = True
                break

        if not encontrado:
            assignees.append(user_mention)

        new_assignee = ", ".join(assignees)

        await db.execute(
            "UPDATE todos SET asignado_a = ?, estado = 'En Progreso' WHERE id = ? AND guild_id = ?",
            (new_assignee, tid_int, interaction.guild_id),
        )
        await db.commit()

        # Envío de feedback temporal
        await interaction.response.send_message(f"✅ Has reclamado la tarea **#{t_id}**.", ephemeral=False)

        # Actualización de dashboards
        await update_all_dashboards(self.bot, interaction.guild_id)

        # Borrado del mensaje de feedback tras 5 segundos
        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Management] Auto-delete falló (ClaimTaskModal): {e}")


class DeleteTaskModal(discord.ui.Modal, title="Eliminar Tarea"):
    task_id = discord.ui.TextInput(label="ID de la Tarea a Eliminar", placeholder="Introduce el número ID")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        t_id = self.task_id.value
        try:
            tid_int = int(t_id)
        except ValueError:
            await interaction.response.send_message("❌ El ID debe ser un número.", ephemeral=True)
            return

        db = self.bot.db
        # Verificar si la tarea existe y pertenece al servidor
        cursor = await db.execute(
            "SELECT id FROM todos WHERE id = ? AND guild_id = ?",
            (tid_int, interaction.guild_id),
        )
        if not await cursor.fetchone():
            await interaction.response.send_message(
                f"❌ La tarea **#{tid_int}** no existe en este servidor.",
                ephemeral=True,
            )
            return

        await db.execute(
            "DELETE FROM todos WHERE id = ? AND guild_id = ?",
            (
                tid_int,
                interaction.guild_id,
            ),
        )
        await db.commit()

        await interaction.response.send_message(f"🗑️ Tarea **#{t_id}** eliminada.", ephemeral=False)

        await update_all_dashboards(self.bot, interaction.guild_id)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Management] Auto-delete falló (DeleteTaskModal): {e}")


class Management(commands.Cog, name="Management"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_todo_updated(self, guild_id: int):
        """Refresca el dashboard de To-Do cuando algún cog lo modifica."""
        try:
            await update_all_dashboards(self.bot, guild_id)
        except Exception as e:
            logger.error(f"[Management] Refresh todo dashboards falló (guild {guild_id}): {e}")

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard del To-Do List y almacena su ID."""
        import asyncio

        info_embed = discord.Embed(
            description=INFO_TEXTS["todo_list"],
            color=discord.Color.from_rgb(43, 45, 49),
        )
        await channel.send(embed=info_embed)

        db = self.bot.db
        cursor = await db.execute(
            "SELECT * FROM todos WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cursor.fetchall()

        # Usar el builder unificado para consistencia visual con /todo_list.
        lang = await resolve_lang(self.bot, guild_id, "periodic")
        todo_embed, _page, view = build_todo_embed_view(self.bot, rows, page=0, lang=lang)
        msg = await channel.send(embed=todo_embed, view=view)
        await asyncio.sleep(0.5)

        db = self.bot.db
        await db.execute(
            "INSERT INTO todo_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (guild_id, channel.id, msg.id),
        )
        await db.commit()

    @app_commands.command(name="todo_add", description="Añade una nueva tarea a la lista.")
    @app_commands.describe(tarea="Descripción de la tarea")
    async def todo_add(self, interaction: discord.Interaction, tarea: str):
        db = self.bot.db
        await db.execute(
            "INSERT INTO todos (guild_id, tarea) VALUES (?, ?)",
            (
                interaction.guild_id,
                tarea,
            ),
        )
        await db.commit()

        # Envío de feedback
        await interaction.response.send_message(f"✅ Tarea añadida: **{tarea}**", ephemeral=False)

        # Actualización de listas (dashboards)
        await update_all_dashboards(self.bot, interaction.guild_id)

        # Borrado del mensaje de feedback
        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Management] Auto-delete falló (feedback): {e}")

    @app_commands.command(name="todo_list", description="Crea un panel de tareas auto-actualizable.")
    async def todo_list(self, interaction: discord.Interaction):
        # Generación del Embed inicial usando el builder unificado.
        db = self.bot.db
        cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (interaction.guild_id,))
        rows = await cursor.fetchall()

        lang = await resolve_lang(self.bot, interaction.guild_id, "periodic")
        embed, _page, view = build_todo_embed_view(self.bot, rows, page=0, lang=lang)
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Registro del mensaje para futuras actualizaciones
        db = self.bot.db
        await db.execute(
            "INSERT INTO todo_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (interaction.guild_id, interaction.channel_id, message.id),
        )
        await db.commit()

    @app_commands.command(
        name="info", description="Muestra la información y guía de uso de un módulo específico."
    )
    @app_commands.describe(
        modulo="Módulo del que quieres ver la guía.",
        idioma="Idioma en el que mostrar la guía (por defecto el tuyo / el del servidor).",
    )
    @app_commands.choices(
        modulo=[
            app_commands.Choice(name="🆘 SOS & Alertas", value="sos"),
            app_commands.Choice(name="🔔 Alarmas de Intrusos", value="alarmas"),
            app_commands.Choice(name="📝 To-Do List", value="todo_list"),
            app_commands.Choice(name="🧬 Líneas de Genética", value="lineas"),
            app_commands.Choice(name="☠️ Blacklist", value="blacklist"),
            app_commands.Choice(name="🛰️ Scouting", value="scouting"),
            app_commands.Choice(name="🟢 Status Servidores", value="status"),
            app_commands.Choice(name="👁️ K4Ultra Radar", value="k4ultra"),
            app_commands.Choice(name="🪦 Ranking de Muertes", value="ranking"),
            app_commands.Choice(name="🌅 Puntos Diarios", value="puntos_diarios"),
            app_commands.Choice(name="📆 Eventos LFG", value="eventos"),
            app_commands.Choice(name="🛡️ Setup & Admin", value="admin"),
            app_commands.Choice(name="💾 Backups DB", value="backup"),
        ],
        idioma=[
            app_commands.Choice(name="🇪🇸 Español", value="es"),
            app_commands.Choice(name="🇬🇧 English", value="en"),
        ],
    )
    async def info(
        self,
        interaction: discord.Interaction,
        modulo: app_commands.Choice[str],
        idioma: app_commands.Choice[str] = None,
    ):
        # Idioma: explícito si se pasa; si no, el idioma de comando del usuario/servidor.
        lang = idioma.value if idioma else await resolve_lang(
            self.bot, interaction.guild_id, "command", interaction.user.id
        )
        texts = get_info_texts(lang)
        not_found = "Information not found." if lang == "en" else "Información no encontrada."
        embed = discord.Embed(
            description=texts.get(modulo.value, not_found),
            color=discord.Color.from_rgb(43, 45, 49),  # Color invisible de Discord (oscuro)
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="bl_editar",
        description="Edita los campos de un jugador en la Blacklist (tribu, mapa, notas, etc.).",
    )
    @app_commands.describe(
        jugador="Nombre del jugador (nombre de Steam)",
        tribu="Nombre de la tribu",
        mapa="Mapa principal del jugador",
        personaje="Nombre del personaje en el juego (se puede usar varias veces para añadir alts)",
        notas="Notas o información relevante",
        enemigo="¿Es enemigo?",
    )
    @app_commands.choices(
        enemigo=[
            app_commands.Choice(name="Sí (Enemigo)", value="1"),
            app_commands.Choice(name="No (Neutral)", value="0"),
        ]
    )
    async def bl_editar(
        self,
        interaction: discord.Interaction,
        jugador: str,
        tribu: str = None,
        mapa: str = None,
        personaje: str = None,
        notas: str = None,
        enemigo: app_commands.Choice[str] = None,
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        db = self.bot.db

        # Verificar si el jugador existe en la blacklist
        cursor = await db.execute(
            "SELECT id FROM blacklist WHERE player = ? AND guild_id = ?",
            (jugador, interaction.guild_id),
        )
        bl_row = await cursor.fetchone()

        # Si no está en la blacklist, lo añadimos automáticamente
        if not bl_row:
            from datetime import datetime

            await db.execute(
                "INSERT INTO blacklist (guild_id, player, tribe, map, notes, is_enemy, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    interaction.guild_id,
                    jugador,
                    tribu or "Desconocido",
                    mapa or "Desconocido",
                    notas or "",
                    int(enemigo.value) if enemigo else 1,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db.commit()
            was_new = True
        else:
            was_new = False
            # Actualizar los campos proporcionados en blacklist
            updates = {}
            if tribu is not None:
                updates["tribe"] = tribu
            if mapa is not None:
                updates["map"] = mapa
            if notas is not None:
                updates["notes"] = notas
            if enemigo is not None:
                updates["is_enemy"] = int(enemigo.value)

            if updates:
                # Defensa en profundidad: verificar columnas contra whitelist antes de interpolar.
                from utils.parsing import ALLOWED_BLACKLIST_FIELDS

                safe_keys = [k for k in updates if k in ALLOWED_BLACKLIST_FIELDS]
                if safe_keys:
                    set_clause = ", ".join(f"{k} = ?" for k in safe_keys)
                    values = [updates[k] for k in safe_keys] + [bl_row["id"], interaction.guild_id]
                    await db.execute(
                        f"UPDATE blacklist SET {set_clause} WHERE id = ? AND guild_id = ?",
                        values,
                    )
                    await db.commit()

        # Gestión del personaje (nombre in-game) en tribe_characters
        if personaje is not None:
            try:
                cursor = await db.execute(
                    "SELECT character_name FROM tribe_characters WHERE player_name = ? AND character_name = ? AND guild_id = ?",
                    (jugador, personaje, interaction.guild_id),
                )
                if not await cursor.fetchone():
                    await db.execute(
                        "INSERT INTO tribe_characters (guild_id, player_name, character_name) VALUES (?, ?, ?)",
                        (interaction.guild_id, jugador, personaje),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"[bl_editar] Error al guardar personaje: {e}")

        # Resumen de cambios
        changes = []
        if was_new:
            changes.append("📥 **Añadido** a la Blacklist (no existía)")
        if tribu is not None:
            changes.append(f"🏠 **Tribu** → {tribu}")
        if mapa is not None:
            changes.append(f"🗺️ **Mapa** → {mapa}")
        if personaje is not None:
            changes.append(f"🧑 **Personaje** → {personaje}")
        if notas is not None:
            changes.append(f"📝 **Notas** → {notas}")
        if enemigo is not None:
            changes.append(f"⚔️ **Enemigo** → {'Sí' if enemigo.value == '1' else 'No'}")

        if not changes:
            await interaction.response.send_message(
                "⚠️ No has proporcionado ningún campo para actualizar.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ **{jugador}** actualizado:\n" + "\n".join(changes),
            ephemeral=True,
        )

        self.bot.dispatch(bus.BLACKLIST_UPDATED, interaction.guild_id)

    @app_commands.command(
        name="fusionar_perfiles",
        description="Une todo el historial cronológico y mapas visitados de un Nombre Antiguo a uno Nuevo (Principal).",
    )
    @app_commands.describe(
        secundario="Nombre de Steam antiguo o secundario que ya no se usa",
        primario="Nombre de Steam oficial y definitivo del jugador",
    )
    async def fusionar_perfiles(self, interaction: discord.Interaction, secundario: str, primario: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        secundario = secundario.strip()
        primario = primario.strip()

        if secundario.lower() == primario.lower():
            await interaction.response.send_message(
                "❌ El nombre original y secundario no pueden ser iguales.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild_id

        db = self.bot.db
        # 1. Resolver el encadenamiento (Si Z se convierte en Y, actualizar todos los X apuntando a Z para que apunten a Y)
        await db.execute(
            "UPDATE player_identities_link SET primary_name = ? WHERE primary_name = ? AND guild_id = ?",
            (primario, secundario, guild_id),
        )

        # 2. Insertar el nuevo alias
        await db.execute(
            "INSERT OR REPLACE INTO player_identities_link (guild_id, secondary_name, primary_name) VALUES (?, ?, ?)",
            (guild_id, secundario, primario),
        )

        # 3. Trasladar registro de sesiones completas (radar activo e inactivo)
        await db.execute(
            "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (primario, secundario, guild_id),
        )

        # 4. Fusión de Playtimes
        c_play = await db.execute(
            "SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (secundario, guild_id),
        )
        old_playtimes = await c_play.fetchall()
        # Métricas para el embed de confirmación.
        transferred_minutes = sum(int(p[1] or 0) for p in old_playtimes)
        transferred_maps = sorted({p[0] for p in old_playtimes if p[0]})

        for map_name, mins, last_seen in old_playtimes:
            c_prim = await db.execute(
                "SELECT total_minutes FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                (primario, map_name, guild_id),
            )
            prim_row = await c_prim.fetchone()
            if prim_row:
                new_mins = prim_row[0] + mins
                await db.execute(
                    "UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = max(last_seen, ?) WHERE player_name = ? AND map_name = ? AND guild_id = ?",
                    (new_mins, last_seen, primario, map_name, guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)",
                    (guild_id, primario, map_name, mins, last_seen),
                )

        await db.execute(
            "DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (secundario, guild_id)
        )

        # 5. Trasladar alts en In-Game
        await db.execute(
            "UPDATE tribe_characters SET player_name = ? WHERE player_name = ? AND guild_id = ?",
            (primario, secundario, guild_id),
        )

        # 6. Para blacklist, simplemente si tenía notas antiguas, no queremos perderlas
        c_bl = await db.execute(
            "SELECT notes FROM blacklist WHERE player = ? AND guild_id = ?", (secundario, guild_id)
        )
        row_bl = await c_bl.fetchone()
        if row_bl:
            old_note = row_bl[0]
            c_p_bl = await db.execute(
                "SELECT id, notes FROM blacklist WHERE player = ? AND guild_id = ?", (primario, guild_id)
            )
            row_p_bl = await c_p_bl.fetchone()
            if row_p_bl:
                combined_notes = f"{row_p_bl[1]} | [De {secundario}]: {old_note}"
                await db.execute("UPDATE blacklist SET notes = ? WHERE id = ?", (combined_notes, row_p_bl[0]))
            else:
                new_note = f"[Heredado de {secundario}]: {old_note}"
                await db.execute(
                    "UPDATE blacklist SET player = ?, notes = ? WHERE player = ? AND guild_id = ?",
                    (primario, new_note, secundario, guild_id),
                )

        await db.execute("DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (secundario, guild_id))

        # Eliminar duplicados en tribe_characters en caso de que ambos tuviesen ya los mismos in-games asignados
        await db.execute("""
            DELETE FROM tribe_characters
            WHERE rowid NOT IN (
                SELECT max(rowid) FROM tribe_characters GROUP BY player_name, character_name, guild_id
            )
        """)

        await db.commit()

        # Mensaje de confirmación detallado.
        h_total = transferred_minutes // 60
        m_total = transferred_minutes % 60
        horas_str = f"{h_total}h {m_total}m" if h_total else f"{m_total}m"
        mapas_str = ", ".join(transferred_maps) if transferred_maps else "—"

        embed = discord.Embed(
            title="✅ IDENTIDADES FUSIONADAS",
            color=discord.Color.brand_green(),
        )
        embed.description = (
            f"`{secundario}`  ➡️  `{primario}`\n\n"
            f"> 📊 **Horas transferidas:** `{horas_str}`\n"
            f"> 🗺️ **Mapas afectados:** `{len(transferred_maps)}` ({mapas_str})\n"
            f"> 📅 **Registros movidos:** sesiones, blacklist y alias del K4Ultra"
        )
        embed.set_footer(text="El bot convertirá automáticamente las próximas conexiones del nombre antiguo.")

        await interaction.followup.send(embed=embed)

        self.bot.dispatch(bus.BLACKLIST_UPDATED, guild_id)

    @app_commands.command(
        name="perfil_tribu",
        description="Registra la ficha completa de un miembro de tribu (Discord, Personaje, Steam, Apodo).",
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
    async def perfil_tribu(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        personaje: str,
        steam: str = None,
        apodo: str = None,
        idioma: app_commands.Choice[str] = None,
    ):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return

        jugador_nombre = usuario.display_name
        apodo_final = apodo if apodo else jugador_nombre
        steam_safe = steam if steam else "No Registrado"

        db = self.bot.db
        # 1. Tabla Unificada de Perfiles (para futura persistencia general de la tribu)
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

        # 2. Vínculo del Rancómetro (Warfare: tracker de muertes)
        await db.execute(
            """
            INSERT INTO tribe_characters (guild_id, character_name, player_name)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, character_name) DO UPDATE SET player_name = excluded.player_name
            """,
            (interaction.guild_id, personaje, jugador_nombre),
        )
        # Inicialización para el Rancómetro
        await db.execute(
            "INSERT OR IGNORE INTO tribe_kda (guild_id, player_name, kills, deaths) VALUES (?, ?, 0, 0)",
            (interaction.guild_id, jugador_nombre),
        )

        # 3. K4Ultra Radar Alias (Si tiene un apodo y nombre característico)
        await db.execute(
            "INSERT INTO k4ultra_aliases (guild_id, player_name, alias) VALUES (?, ?, ?) ON CONFLICT(guild_id, player_name) DO UPDATE SET alias=excluded.alias",
            (interaction.guild_id, personaje, apodo_final),
        )

        # 4. Preferencia de idioma personal (opcional). Sobrescribe el idioma de
        # servidor para las respuestas de comandos dirigidas a ESTE usuario.
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

        embed = discord.Embed(
            title="✅ PERFIL DE TRIBU CONFIGURADO",
            color=discord.Color.green(),
        )
        embed.description = (
            f"> 👤 **Usuario:** {usuario.mention}\n"
            f"> 📛 **In-Game:** `{personaje}`\n"
            f"> 🎭 **Apodo:** `{apodo_final}`\n"
            f"> 🎮 **Steam:** `{steam_safe}`"
            f"{idioma_txt}"
        )
        embed.set_footer(text="Vinculado al Rancómetro y al Radar K4Ultra  •  /ranking para ver tu posición")

        await interaction.response.send_message(embed=embed, ephemeral=False)

        # Puesto que actualizamos records, recargamos el dashboard de muertes vía bus.
        self.bot.dispatch(bus.KDA_UPDATED, interaction.guild_id)

    @app_commands.command(
        name="help",
        description="Muestra la guía completa de uso y comandos del bot.",
    )
    @app_commands.describe(idioma="Idioma de la guía (por defecto el tuyo / el del servidor).")
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="🇪🇸 Español", value="es"),
            app_commands.Choice(name="🇬🇧 English", value="en"),
        ]
    )
    async def help_cmd(
        self, interaction: discord.Interaction, idioma: app_commands.Choice[str] = None
    ):
        """Manual interactivo bilingüe que reutiliza las guías de ``locales/guides_*``.

        El idioma se elige explícitamente o se hereda del idioma de comando del
        usuario/servidor. El ``Select`` y las guías se renderizan en ese idioma.
        """
        lang = idioma.value if idioma else await resolve_lang(
            self.bot, interaction.guild_id, "command", interaction.user.id
        )

        # Orden y emoji de cada módulo; el label se traduce vía catálogo.
        _MODULES = [
            ("sos", "🆘"),
            ("alarmas", "🔔"),
            ("todo_list", "📝"),
            ("lineas", "🧬"),
            ("blacklist", "☠️"),
            ("scouting", "🛰️"),
            ("status", "🟢"),
            ("k4ultra", "👁️"),
            ("ranking", "🪦"),
            ("puntos_diarios", "🌅"),
            ("eventos", "📆"),
            ("admin", "🛡️"),
            ("backup", "💾"),
        ]

        class HelpView(discord.ui.View):
            def __init__(self, lang: str):
                super().__init__(timeout=180)
                self.lang = lang
                texts = get_info_texts(lang)
                options = [
                    discord.SelectOption(label=t(f"help.opt.{key}", lang), value=key, emoji=emoji)
                    for key, emoji in _MODULES
                    if key in texts  # filtro defensivo
                ]
                self.select = discord.ui.Select(
                    placeholder=t("help.placeholder", lang),
                    options=options,
                )
                self.select.callback = self.select_callback
                self.add_item(self.select)

            async def select_callback(self, i: discord.Interaction):
                val = self.select.values[0]
                text = get_info_texts(self.lang).get(val, t("help.construction", self.lang))
                emb = discord.Embed(description=text, color=discord.Color.blurple())
                await i.response.edit_message(embed=emb, view=self)

        embed_inicial = discord.Embed(
            title=t("help.title", lang),
            description=t("help.intro", lang),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed_inicial, view=HelpView(lang), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Management(bot))
