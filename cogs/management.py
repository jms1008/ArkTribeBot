import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio


class TodoView(discord.ui.View):
    def __init__(self, bot, page: int = 0, total_rows: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.page = page
        self.total_rows = total_rows
        
        # Deshabilitar botones de paginación si procede
        total_pages = max(1, (self.total_rows + 10 - 1) // 10)
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= total_pages - 1

    @discord.ui.button(
        label="Añadir Tarea",
        style=discord.ButtonStyle.success,
        custom_id="todo_add_btn",
    )
    async def add_task_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(AddTaskModal(self.bot))

    @discord.ui.button(
        label="Reclamar Tarea",
        style=discord.ButtonStyle.primary,
        custom_id="todo_claim",
    )
    async def claim_task(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(ClaimTaskModal(self.bot))

    @discord.ui.button(
        label="Eliminar Tarea",
        style=discord.ButtonStyle.danger,
        custom_id="todo_delete",
    )
    async def delete_task(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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
            m = re.search(r"Página (\d+)/\d+", interaction.message.embeds[0].footer.text)
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
            m = re.search(r"Página (\d+)/(\d+)", interaction.message.embeds[0].footer.text)
            if m:
                current_page = int(m.group(1)) - 1
                total_pages = int(m.group(2))
        new_page = min(total_pages - 1, current_page + 1)
        await self._update_page(interaction, new_page)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM todos")
            rows = await cursor.fetchall()
        
        embed, page, view = build_todo_embed_view(self.bot, rows, new_page)
        await interaction.response.edit_message(embed=embed, view=view)


def build_todo_embed_view(bot, rows: list, page: int = 0):
    page_size = 10
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    
    start = page * page_size
    chunk = rows[start : start + page_size]

    embed = discord.Embed(title="📝 Lista de Tareas", color=discord.Color.orange())
    if not rows:
        embed.description = "No hay tareas pendientes. ¡Buen trabajo! 🎉"
    else:
        text = ""
        for row in chunk:
            asignado = f"<@{row['asignado_a']}>" if row["asignado_a"] else "Nadie"
            estado_icon = "⏳" if row["estado"] == "Pendiente" else "🔨"
            text += f"**#{row['id']}** {estado_icon} - {row['tarea']}\n   Estado: {row['estado']} | Asignado: {asignado}\n\n"
        embed.description = text.strip()
        embed.set_footer(text=f"Página {page + 1}/{total_pages} • {total} tareas en total")

    view = TodoView(bot, page=page, total_rows=total)
    return embed, page, view


async def update_all_dashboards(bot, page: int = 0):
    """Actualiza todos los mensajes de lista de tareas registrados."""
    # 1. Generación del nuevo Embed
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM todos")
        rows = await cursor.fetchall()

    embed, current_page, view = build_todo_embed_view(bot, rows, page)
    # 2. Búsqueda y edición de mensajes registrados
    messages_to_remove = []
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, channel_id, message_id FROM todo_messages"
        )
        msg_rows = await cursor.fetchall()

        for row in msg_rows:
            try:
                channel = bot.get_channel(row["channel_id"]) or await bot.fetch_channel(
                    row["channel_id"]
                )
                if channel:
                    message = await channel.fetch_message(row["message_id"])
                    await message.edit(embed=embed, view=view)
                else:
                    messages_to_remove.append(row["id"])
            except (discord.NotFound, discord.Forbidden):
                messages_to_remove.append(
                    row["id"]
                )  # Inaccesible (borrado o sin permisos)
            except Exception as e:
                print(f"Error actualizando dashboard {row['id']}: {e}")

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
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute("INSERT INTO todos (tarea) VALUES (?)", (tarea,))
            await db.commit()

        await interaction.response.send_message(
            f"✅ Tarea añadida: **{tarea}**", ephemeral=False
        )
        await update_all_dashboards(self.bot)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


class ClaimTaskModal(discord.ui.Modal, title="Reclamar Tarea"):
    task_id = discord.ui.TextInput(
        label="ID de la Tarea", placeholder="Introduce el número ID"
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        t_id = self.task_id.value
        try:
            tid_int = int(t_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT id FROM todos WHERE id = ?", (tid_int,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message(
                    "❌ Tarea no encontrada.", ephemeral=True
                )
                return

            await db.execute(
                "UPDATE todos SET asignado_a = ?, estado = 'En Progreso' WHERE id = ?",
                (interaction.user.id, tid_int),
            )
            await db.commit()

        # Envío de feedback temporal
        await interaction.response.send_message(
            f"✅ Has reclamado la tarea **#{t_id}**.", ephemeral=False
        )

        # Actualización de dashboards
        await update_all_dashboards(self.bot)

        # Borrado del mensaje de feedback tras 5 segundos
        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


class DeleteTaskModal(discord.ui.Modal, title="Eliminar Tarea"):
    task_id = discord.ui.TextInput(
        label="ID de la Tarea a Eliminar", placeholder="Introduce el número ID"
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        t_id = self.task_id.value
        try:
            tid_int = int(t_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT id FROM todos WHERE id = ?", (tid_int,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message(
                    "❌ Tarea no encontrada.", ephemeral=True
                )
                return

            await db.execute("DELETE FROM todos WHERE id = ?", (tid_int,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Tarea **#{t_id}** eliminada.", ephemeral=False
        )

        await update_all_dashboards(self.bot)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


class Management(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="todo_add", description="Añade una nueva tarea a la lista."
    )
    @app_commands.describe(tarea="Descripción de la tarea")
    async def todo_add(self, interaction: discord.Interaction, tarea: str):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute("INSERT INTO todos (tarea) VALUES (?)", (tarea,))
            await db.commit()

        # Envío de feedback
        await interaction.response.send_message(
            f"✅ Tarea añadida: **{tarea}**", ephemeral=False
        )

        # Actualización de listas (dashboards)
        await update_all_dashboards(self.bot)

        # Borrado del mensaje de feedback
        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    @app_commands.command(
        name="todo_list", description="Crea un panel de tareas auto-actualizable."
    )
    async def todo_list(self, interaction: discord.Interaction):
        # Generación del Embed inicial
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM todos")
            rows = await cursor.fetchall()

        embed = discord.Embed(title="📝 Lista de Tareas", color=discord.Color.orange())
        if not rows:
            embed.description = "No hay tareas pendientes. ¡Buen trabajo! 🎉"
        else:
            text = ""
            for row in rows:
                asignado = f"<@{row['asignado_a']}>" if row["asignado_a"] else "Nadie"
                estado_icon = "⏳" if row["estado"] == "Pendiente" else "🔨"
                text += f"**#{row['id']}** {estado_icon} - {row['tarea']}\n   Estado: {row['estado']} | Asignado: {asignado}\n\n"
                if len(text) > 3800:
                    text += "... (lista truncada)"
                    break
            embed.description = text

        view = TodoView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Registro del mensaje para futuras actualizaciones
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO todo_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
            )
            await db.commit()


async def setup(bot):
    await bot.add_cog(Management(bot))
