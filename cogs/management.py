import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import logging

logger = logging.getLogger("ArkTribeBot")


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
            cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (interaction.guild_id,))
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


async def update_all_dashboards(bot, guild_id: int, page: int = 0):
    """Actualiza todos los mensajes de lista de tareas registrados en el servidor actual."""
    # 1. Generación del nuevo Embed
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (guild_id,))
        rows = await cursor.fetchall()

    embed, current_page, view = build_todo_embed_view(bot, rows, page)
    # 2. Búsqueda y edición de mensajes registrados
    messages_to_remove = []
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, channel_id, message_id FROM todo_messages WHERE guild_id = ?", (guild_id,)
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
            await db.execute("INSERT INTO todos (guild_id, tarea) VALUES (?, ?)", (interaction.guild_id, tarea,))
            await db.commit()

        await interaction.response.send_message(
            f"✅ Tarea añadida: **{tarea}**", ephemeral=False
        )
        await update_all_dashboards(self.bot, interaction.guild_id)

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
                "UPDATE todos SET asignado_a = ?, estado = 'En Progreso' WHERE id = ? AND guild_id = ?",
                (interaction.user.name, tid_int, interaction.guild_id),
            )
            await db.commit()

        # Envío de feedback temporal
        await interaction.response.send_message(
            f"✅ Has reclamado la tarea **#{t_id}**.", ephemeral=False
        )

        # Actualización de dashboards
        await update_all_dashboards(self.bot, interaction.guild_id)

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

            await db.execute("DELETE FROM todos WHERE id = ? AND guild_id = ?", (tid_int, interaction.guild_id,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Tarea **#{t_id}** eliminada.", ephemeral=False
        )

        await update_all_dashboards(self.bot, interaction.guild_id)

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

### :satellite: Modos de Visualización (Paginados)
- **/k4ultra**: Levanta el panel principal. Ahora dispone de un selector `modo=radar` o `modo=tribus`:
  - **Radar (Ranking):** Muestra jugadores online y el top de horas jugado. Dividido automáticamente en varias páginas interactivas :arrow_backward: :arrow_forward: .
  - **Tribus (Relaciones):** Mapa predictivo con los grupos de alianzas. Permite marcar nuestra base con `/tribu_propia` para fijarla arriba del todo.

### :clipboard: Espionaje Localizado (Menú Desplegable)
Selecciona a un jugador del menú inferior de K4Ultra para ver su expediente:
1. **Últimas Bajas:** Muestra el historial de sus 10 mapas más visitados.
2. **Sessions:** Tiempos de conexión exactos.
3. **Horas Totales:** Suma acumulada de tiempo por mapa.""",

    "ranking": """# ☠️ EL SALÓN DE LA INFAMIA (Mortality Hub)

El sistema de mortalidad rastrea quién es el miembro más "manco" de la tribu basándose en las muertes registradas en los logs.

### 📉 Funcionamiento del Ránking

- **Detección Automática:** El bot lee los logs de la tribu en tiempo real. Si un miembro muere (por un enemigo, un dino, hambre o caída), el contador sube.
- **Vinculación Requerida:** Para que tus muertes cuenten, debes vincular tu nombre de personaje de ARK con tu usuario de Discord.
  - *Comando:* `/ranking_char_add jugador:@Usuario personaje:TuNombreEnARK`
- **/ranking**: Genera o refresca el Dashboard de mortalidad.

### 🏅 Rangos de "Mancura"

El sistema te asigna un grado basado en tu historial:
1. **Pienso de Dodo 🥚**: (0-10 muertes) Todavía tienes dignidad.
2. **Ceviche de Raptor Rex 🦖**: (11-50 muertes) Empiezas a ser comida fácil.
3. **Saco de Dormir Humano 🛌**: (51-120 muertes) Tu utilidad principal es reaparecer.
4. **ALPHA MANCO SUPREMO 👑**: (>120 muertes) Eres una leyenda del feed.

> 💡 **Tip:** El ránking se ordena de **MAYOR a MENOR** número de muertes. ¡El #1 es el que más veces ha besado el suelo!"""
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
            await db.execute("INSERT INTO todos (guild_id, tarea) VALUES (?, ?)", (interaction.guild_id, tarea,))
            await db.commit()

        # Envío de feedback
        await interaction.response.send_message(
            f"✅ Tarea añadida: **{tarea}**", ephemeral=False
        )

        # Actualización de listas (dashboards)
        await update_all_dashboards(self.bot, interaction.guild_id)

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
            cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (interaction.guild_id,))
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
                "INSERT INTO todo_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (interaction.guild_id, interaction.channel_id, message.id),
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
            app_commands.Choice(name="☠️ Ránking de Muertes", value="ranking"),
        ]
    )
    async def info(self, interaction: discord.Interaction, modulo: app_commands.Choice[str]):
        embed = discord.Embed(
            description=INFO_TEXTS.get(modulo.value, "Información no encontrada."),
            color=discord.Color.from_rgb(43, 45, 49)  # Color invisible de Discord (oscuro)
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
            await interaction.response.send_message(
                "❌ Acceso denegado.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row

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
                    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                    values = list(updates.values()) + [bl_row["id"], interaction.guild_id]
                    await db.execute(
                        f"UPDATE blacklist SET {set_clause} WHERE id = ? AND guild_id = ?",
                        values,
                    )
                    await db.commit()

            # Gestión del personaje (nombre in-game) en tribe_characters
            if personaje is not None:
                try:
                    cursor = await db.execute(
                        "SELECT id FROM tribe_characters WHERE player_name = ? AND character_name = ? AND guild_id = ?",
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

        from cogs.warfare import update_blacklist_dashboards
        await update_blacklist_dashboards(self.bot, interaction.guild_id)

    @app_commands.command(
        name="fusionar_perfiles",
        description="Une todo el historial cronológico y mapas visitados de un Nombre Antiguo a uno Nuevo (Principal)."
    )
    @app_commands.describe(
        secundario="Nombre de Steam antiguo o secundario que ya no se usa",
        primario="Nombre de Steam oficial y definitivo del jugador"
    )
    async def fusionar_perfiles(self, interaction: discord.Interaction, secundario: str, primario: str):
        if not await interaction.client.is_authorized_admin(interaction):
            await interaction.response.send_message("❌ Acceso denegado.", ephemeral=True)
            return
            
        secundario = secundario.strip()
        primario = primario.strip()
        
        if secundario.lower() == primario.lower():
            await interaction.response.send_message("❌ El nombre original y secundario no pueden ser iguales.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild_id
        
        async with aiosqlite.connect(self.bot.db_name) as db:
            # 1. Resolver el encadenamiento (Si Z se convierte en Y, actualizar todos los X apuntando a Z para que apunten a Y)
            await db.execute(
                "UPDATE player_identities_link SET primary_name = ? WHERE primary_name = ? AND guild_id = ?",
                (primario, secundario, guild_id)
            )
            
            # 2. Insertar el nuevo alias
            await db.execute(
                "INSERT OR REPLACE INTO player_identities_link (guild_id, secondary_name, primary_name) VALUES (?, ?, ?)",
                (guild_id, secundario, primario)
            )
            
            # 3. Trasladar registro de sesiones completas (radar activo e inactivo)
            await db.execute(
                "UPDATE k4ultra_sessions SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (primario, secundario, guild_id)
            )
            
            # 4. Fusión de Playtimes
            c_play = await db.execute("SELECT map_name, total_minutes, last_seen FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (secundario, guild_id))
            old_playtimes = await c_play.fetchall()
            
            for map_name, mins, last_seen in old_playtimes:
                c_prim = await db.execute("SELECT total_minutes FROM k4ultra_playtime WHERE player_name = ? AND map_name = ? AND guild_id = ?", (primario, map_name, guild_id))
                prim_row = await c_prim.fetchone()
                if prim_row:
                    new_mins = prim_row[0] + mins
                    await db.execute("UPDATE k4ultra_playtime SET total_minutes = ?, last_seen = max(last_seen, ?) WHERE player_name = ? AND map_name = ? AND guild_id = ?", (new_mins, last_seen, primario, map_name, guild_id))
                else:
                    await db.execute("INSERT INTO k4ultra_playtime (guild_id, player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?, ?)", (guild_id, primario, map_name, mins, last_seen))
            
            await db.execute("DELETE FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?", (secundario, guild_id))
            
            # 5. Trasladar alts en In-Game
            await db.execute(
                "UPDATE tribe_characters SET player_name = ? WHERE player_name = ? AND guild_id = ?",
                (primario, secundario, guild_id)
            )
            
            # 6. Para blacklist, simplemente si tenía notas antiguas, no queremos perderlas
            c_bl = await db.execute("SELECT notes FROM blacklist WHERE player = ? AND guild_id = ?", (secundario, guild_id))
            row_bl = await c_bl.fetchone()
            if row_bl:
                old_note = row_bl[0]
                c_p_bl = await db.execute("SELECT id, notes FROM blacklist WHERE player = ? AND guild_id = ?", (primario, guild_id))
                row_p_bl = await c_p_bl.fetchone()
                if row_p_bl:
                    combined_notes = f"{row_p_bl[1]} | [De {secundario}]: {old_note}"
                    await db.execute("UPDATE blacklist SET notes = ? WHERE id = ?", (combined_notes, row_p_bl[0]))
                else:
                    new_note = f"[Heredado de {secundario}]: {old_note}"
                    await db.execute("UPDATE blacklist SET player = ?, notes = ? WHERE player = ? AND guild_id = ?", (primario, new_note, secundario, guild_id))
            
            await db.execute("DELETE FROM blacklist WHERE player = ? AND guild_id = ?", (secundario, guild_id))
            
            # Eliminar duplicados en tribe_characters en caso de que ambos tuviesen ya los mismos in-games asignados
            await db.execute("""
                DELETE FROM tribe_characters 
                WHERE rowid NOT IN (
                    SELECT max(rowid) FROM tribe_characters GROUP BY player_name, character_name, guild_id
                )
            """)
            
            await db.commit()
            
        # Mensaje de confirmación detallado
        embed = discord.Embed(
            title="✅ Identidades Fusionadas",
            description=f"El perfil histórico de **{secundario}** ha sido traspasado y fusionado de manera perpetua a **{primario}**.",
            color=discord.Color.brand_green()
        )
        embed.set_footer(text="A partir de ahora, el bot convertirá automáticamente a este jugador si se conecta usando su viejo nombre de Steam.")
        
        await interaction.followup.send(embed=embed)
        
        from cogs.warfare import update_blacklist_dashboards
        await update_blacklist_dashboards(self.bot, guild_id)


async def setup(bot):
    await bot.add_cog(Management(bot))
