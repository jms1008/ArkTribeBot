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


INFO_TEXTS = {
    "sos": """# :rotating_light: AMBULANCIAS A DOMICILIO Y SOS

Este canal es para **EMERGENCIAS REALES**. Úsalo con responsabilidad.

### :loudspeaker: Sistema de Alerta SOS

- **/sos**: Lanza una alerta masiva mencionando al rol de la tribu.
  - **Uso Rápido:** `/sos` (Envía una alerta genérica de "AYUDA YA").
  - **Uso Detallado:** `/sos tipo:Raideo mapa:MainBase atacantes:10+` (Envía un informe de situación completo).

### :man_police_officer: Sistema de Chivatazo Silencioso (@policia)
Tenemos implementado un sistema pasivo de alarma. Si alguien dentro del juego mata a un dino que se llame o contenga `@policia` en el nombre, el bot leerá la línea de muerte en los *logs* de la tribu y mandará automáticamente un mensaje de alarma en este canal para avisar de infiltrados.

> :warning: **IMPORTANTE:** El abuso del comando `/sos` para bromas está feo. Úsalos solo si nos están atacando.""",

    "todo_list": """# :pencil: TO-DO List

Añade tareas pendientes, reclama las que vayas a hacer tú y bórralas cuando estén completas.

### :white_check_mark: Gestión de Tareas

- **/todo_add**: Añade una nueva tarea a la lista "Pendiente".
  - *Uso:* `/todo_add tarea:"Farmear 50k de metal en Abberation"`
- **/todo_list**: Genera el panel interactivo de tareas.

### :mouse_three_button: Botones del Panel

El panel tiene botones para gestionar las tareas sin usar comandos:
1. **Añadir Tarea**: Abre un formulario para escribir una nueva tarea.
2. **Reclamar Tarea**: Te asigna una tarea y la marca "En Progreso" :hammer: apuntando tu nombre en ella.
3. **Eliminar Tarea**: Borra una tarea de la faz de la tierra cuando esté terminada.
4. :arrow_backward: y :arrow_forward: **(Paginación)**: Si hay más de 10 tareas pendientes, puedes navegar por las diferentes páginas de las listas de tareas.

> :bell: Revisa este canal antes de preguntar "¿Qué hay que hacer?".""",

    "lineas": """# :dna: Líneas de Genética

Aquí registramos y controlamos las líneas (Top Stats) de nuestra tribu.

### :sauropod: Comandos de Crianza

- **/linea_add**: Registra un nuevo dino o actualiza una stat si la tuya es superior.
  - *Uso:* `/linea_add dino:Rex estadistica:HP puntos:50`
- **/linea_mod**: Modifica una estadística específica (por si te equivocaste o salió muta).
  - *Uso:* `/linea_mod dino:Giga estadistica:Melee puntos:255`
- **/linea_ver**: Consulta rápida de todas las stats de una especie (solo tú lo ves en un mensaje oculto).
  - *Uso:* `/linea_ver dino:Shadowmane`
- **/lineas**: Muestra/Renueva el Dashboard principal con todas las estadísticas y botones en vivo.

### :mouse_three_button: Botones del Dashboard
El panel de `/lineas` ahora incluye herramientas clickeables:
1. :arrow_backward: y :arrow_forward: **(Paginación)**: Navega por un máximo de 10 especies por página sin necesidad de tirar comandos. Infinito y a prueba de reinicios.
2. **Nueva Muta:** Te permite sumar un +2 directamente a un dino y registrarlo en los logs cómodamente.
3. **Alarmas:** Programa temporizadores para que el bot te avise de la impronta o el crecimiento.
4. **Ver Logs Muta:** Log que informa de qué stat y de qué dino se modificaron los puntos.
5. **Selector Individual:** Usa el menú desplegable inferior para aislar a un dino concreto y ver su ficha detallada de forma privada.""",

    "blacklist": """# :skull_crossbones: Blacklist

Jugadores "Kill on Sight" (KOS). Si están aquí, son enemigos confirmados, cuanta más info mejor.

### :no_entry_sign: Sistema de Blacklist

- **/blacklist**: Genera y actualiza el Dashboard interactivo de la Lista Negra. Todo se gestiona por medio de botones, no hay que recordar comandos.

### :mouse_three_button: Botones del Panel
1. **Añadir:** Permite rellenar un formulario rápido (Tribu, Notas, Mapa) para crear un enemigo.
2. **Modificar:** Cambia las notas o el nombre de una entrada, y **te permite cambiar de estado "Neutral" a manual**.
3. **Eliminar:** Borra una entrada de la base de datos pidiéndote el ID correspondiente.

### :red_circle: Enemigos vs :white_circle: Neutrales
El panel incorpora iconos inteligentes:
- :red_circle: **ENEMIGOS:** Jugadores a neutralizar sí o sí.
- :white_circle: **REGISTROS (NEUTRALES):** Jugadores auto-detectados por el radar que todavía no nos han hecho nada (sólo control y seguimiento de pasaportes).""",

    "scouting": """# :satellite_orbital: Scouting

Reporte de bases enemigas. La información es poder.

### :telescope: Comandos de Reconocimiento

- **/scout_add**: Registra una base enemiga manualmente con detalles y la puntuación de amenaza.
  - *Campos:* `tribu`, `mapa`, `coords`, `amenaza` (1-5 :star:), `imagen` (Enlace), `notas`.
- **/scout_add_image**: Si subiste una base mediante botones y quieres sumarle una foto desde tu PC.
  - *Uso:* `/scout_add_image id:12 imagen:[Adjuntar Archivo]`
- **/scout_list**: Genera el panel Dashboard.
  - *Sin argumentos:* Lista **GLOBAL** paginada de todos los mapas (:arrow_backward: :arrow_forward:).
  - *Con mapa:* Filtra de forma secreta para enseñarte solo las bases de ese mapa.
- **/scout_delete**: Elimina un reporte obsoleto o de una base limpia. Requiere el ID del reporte.

> :bulb: **Tip:** Desde el propio panel con botones generado por `/scout_list` también puedes Añadir, Modificar o Eliminar bases completando el formulario.""",

    "status": """# :green_circle: Estado de los Servidores

Monitorea en tiempo real si los servidores están online, quién está conectado y qué ping tienen.

### :computer: Tablones y Comandos

- **/status**: Consulta el estado de un único servidor, autocompletando con la lista de tus mapas.
  - *Uso:* `/status mapa:Gen2`
- **/status_online**: Consulta general que te devuelve una lista del estado de **todos** tus servidores  del cluster a la vez.
- **/status_permanente**: Genera y ancla un mensaje que se actualiza a sí mismo indefinidamente.

> :arrows_counterclockwise: **Auto-Update:** Los mensajes estáticos de `/status_permanente` cambian de color a :red_circle: Rojo si el servidor cae bajo un Timeout, :yellow_circle: Amarillo si está vivo pero Vacío y :green_circle: Verde si hay gente dentro, listándolos abajo.""",

    "k4ultra": """# :eye: Tracker de Inteligencia (K4Ultra)

K4Ultra monitoriza de forma pasiva las redes para calcular el comportamiento y sesiones enemigas.

### :satellite: Panel Global
- **/k4ultra**: Levanta el panel principal. Muestra la clasificación de horas de todo el clúster.

### :clipboard: Espionaje Localizado (Menú Desplegable)
Si un jugador aparece rankeado en el menú desplegable inferior del Dashboard de K4Ultra, podrás seleccionarlo para que el bot devuelva su expediente completo:
- **:green_circle: Actividad Inmediata:** Te marca si está `Online Ahora` (y en qué mapa) u `Offline`.
- **:crossed_swords: K/D/A y Letalidad:** Su historial de bajas PVP en el servidor.
- **:people_holding_hands: Nombres ingame:** Destapa qué otros nombres de personaje comparten esta ID en el clúster.
- **:stopwatch: Patrones horarios y Antigüedad:** Indica cuántas horas lleva desde que el radar lo vio por primera vez y a qué hora en punto del día es su momento frecuente de inicio de sesión."""
}

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

    @app_commands.command(
        name="info", description="Muestra la información y guía de uso de un módulo específico."
    )
    @app_commands.choices(
        modulo=[
            app_commands.Choice(name="🆘 SOS & Alertas", value="sos"),
            app_commands.Choice(name="📝 To-Do List", value="todo_list"),
            app_commands.Choice(name="🧬 Líneas de Genética", value="lineas"),
            app_commands.Choice(name="☠️ Blacklist", value="blacklist"),
            app_commands.Choice(name="🛰️ Scouting", value="scouting"),
            app_commands.Choice(name="🟢 Status Servidores", value="status"),
            app_commands.Choice(name="👁️ K4Ultra Radar", value="k4ultra"),
        ]
    )
    async def info(self, interaction: discord.Interaction, modulo: app_commands.Choice[str]):
        embed = discord.Embed(
            description=INFO_TEXTS.get(modulo.value, "Información no encontrada."),
            color=discord.Color.from_rgb(43, 45, 49)  # Color invisible de Discord (oscuro)
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Management(bot))
