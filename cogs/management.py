import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils import bus
from utils.embeds import apply_uniform_width

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
        db = self.bot.db
        cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (interaction.guild_id,))
        rows = await cursor.fetchall()

        embed, page, view = build_todo_embed_view(self.bot, rows, new_page)
        await interaction.response.edit_message(embed=embed, view=view)


def _format_assignees(raw: str | None) -> str:
    """Normaliza el campo asignado_a a una cadena de menciones Discord."""
    if not raw:
        return "*Sin asignar*"
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    fixed = []
    for p in parts:
        core = p.replace("<@", "").replace(">", "")
        if core.isdigit():
            fixed.append(f"<@{core}>")
        else:
            fixed.append(core)
    return ", ".join(fixed) if fixed else "*Sin asignar*"


def _render_todo_item(row) -> list[str]:
    """Renderiza una tarea como 2 líneas: encabezado + asignado.

    Patrón visual unificado con Blacklist/Scouting:
    ``#ID + emoji + **tarea**`` y debajo ``└ 👤 mention``.
    """
    icon = "🔨" if row["estado"] != "Pendiente" else "⏳"
    return [
        f"`#{row['id']:03d}` {icon} **{row['tarea']}**",
        f"  └ 👤 {_format_assignees(row['asignado_a'])}",
    ]


def build_todo_embed_view(bot, rows: list, page: int = 0):
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

    embed = discord.Embed(title="📋 LISTA DE TAREAS", color=discord.Color.from_rgb(255, 165, 0))

    if not rows:
        embed.description = (
            "✅ ¡Sin tareas pendientes! La tribu está al día. 🎉\n\n"
            "*Pulsa **Añadir Tarea** o usa `/todo_add` para crear una nueva.*"
        )
        embed.set_footer(text="Página 1/1 • 0 tareas")
        apply_uniform_width(embed)
        view = TodoView(bot, page=0, total_rows=0)
        return embed, 0, view

    n_pending = sum(1 for r in rows if r["estado"] == "Pendiente")
    n_progress = total - n_pending

    # Cabecera con counter de badges en code-block (estilo Blacklist).
    lines: list[str] = [
        f"🔨 `{n_progress:02d}` En Progreso  ·  ⏳ `{n_pending:02d}` Pendientes  ·  📊 `{total:02d}` Total",
        "",
    ]

    # Separar por estado, manteniendo el orden original dentro de cada grupo.
    in_progress = [r for r in chunk if r["estado"] != "Pendiente"]
    pending = [r for r in chunk if r["estado"] == "Pendiente"]

    if in_progress:
        lines.append("## 🔨 EN PROGRESO")
        for row in in_progress:
            lines.extend(_render_todo_item(row))
            lines.append("")

    if pending:
        if in_progress:
            lines.append("")  # separador extra entre secciones
        lines.append("## ⏳ PENDIENTES")
        for row in pending:
            lines.extend(_render_todo_item(row))
            lines.append("")

    embed.description = "\n".join(lines).strip()
    embed.set_footer(text=f"Página {page + 1}/{total_pages} • {total} tareas totales • /todo_add para añadir")
    apply_uniform_width(embed)
    view = TodoView(bot, page=page, total_rows=total)
    return embed, page, view


async def update_all_dashboards(bot, guild_id: int, page: int = 0):
    """Actualiza todos los mensajes de lista de tareas registrados en el servidor actual."""
    # 1. Generación del nuevo Embed
    db = bot.db
    cursor = await db.execute("SELECT * FROM todos WHERE guild_id = ?", (guild_id,))
    rows = await cursor.fetchall()

    embed, current_page, view = build_todo_embed_view(bot, rows, page)
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


INFO_TEXTS = {
    "sos": """# :rotating_light: AMBULANCIAS A DOMICILIO Y SOS

Este canal es para **EMERGENCIAS REALES**. Úsalo con responsabilidad.

### :loudspeaker: Sistema de Alerta SOS
- **/sos**: Lanza una alerta masiva mencionando al rol de la tribu.
  - **Uso Rápido:** `/sos` (envía una alerta genérica de "AYUDA YA").
  - **Uso Detallado:** `/sos tipo:Raideo mapa:MainBase atacantes:10 defensores:2 notas:"En la cueva norte"`.
  - **Tipos disponibles:** :red_circle: Raideo · :orange_circle: FOB enemiga · :yellow_circle: Soaking · y más.
- Cada SOS publicado lleva un botón **✅ Solucionado** que cualquiera puede pulsar para borrar el mensaje cuando termine la emergencia.

### :man_police_officer: Chivatazo Silencioso (@policia)
Sistema pasivo de alarma. Si alguien en el juego mata a un dino cuyo nombre contiene `@policia`, el **Log Processor** lo detecta en el canal de logs y publica automáticamente un aviso aquí. Útil para detectar infiltrados silenciosos sin que el atacante sepa que le has cazado.

### :bell: Relación con Alarmas de Intrusos
El módulo **🔔 Alarmas de Intrusos** (`/info modulo:🔔 Alarmas`) complementa esto avisándote cuando un jugador no-tribal entra a un mapa que estés vigilando.

> :warning: El abuso del comando `/sos` para bromas está feo. Úsalo solo si nos están atacando de verdad.""",
    "todo_list": """# :pencil: TO-DO List

Añade tareas pendientes, reclama las que vayas a hacer tú y bórralas cuando estén completas.

### :white_check_mark: Gestión de Tareas
- **/todo_add**: Añade una nueva tarea a la lista "Pendiente".
  - *Uso:* `/todo_add tarea:"Farmear 50k de metal en Aberration"`
- **/todo_list**: Genera/renueva el panel interactivo de tareas (auto-actualizable).

### :mouse_three_button: Botones del Panel
1. **Añadir Tarea**: Abre un formulario para escribir una nueva tarea.
2. **Reclamar Tarea**: Te asigna una tarea y la marca "En Progreso" :hammer:.
   - *Es un toggle*: si vuelves a pulsar "Reclamar" con la misma tarea, te **quitas** de la lista.
   - Una tarea puede tener **varios asignados** simultáneos (se acumulan).
3. **Eliminar Tarea**: Borra una tarea de la faz de la tierra cuando esté terminada.
4. :arrow_backward: y :arrow_forward: **Paginación**: 10 tareas por página, infinitas páginas, sobrevive reinicios.

> :bell: Revisa este canal antes de preguntar "¿Qué hay que hacer?".""",
    "lineas": """# :dna: Líneas de Genética

Aquí registramos y controlamos las líneas (Top Stats) de nuestra tribu.

### :sauropod: Comandos de Crianza
- **/linea_add**: Registra un nuevo dino o actualiza una stat si la tuya es superior.
  - *Uso:* `/linea_add dino:Rex estadistica:HP puntos:50`
- **/linea_mod**: Modifica una estadística específica (por si te equivocaste o entró muta).
- **/linea_ver**: Consulta privada de todas las stats de una especie (mensaje oculto).
- **/lineas**: Renueva el Dashboard principal con todas las estadísticas y botones en vivo.
- **/log_mutas**: Muestra las últimas 20 mutaciones registradas en el servidor.

### :bar_chart: Stats Disponibles
HP · Estamina · Peso · Melee · Oxígeno · Comida · Velocidad · Mutaciones (contador puro).

### :mouse_three_button: Botones del Dashboard
1. :arrow_backward: :arrow_forward: **Paginación**: 10 especies por página, persistente entre reinicios.
2. **Nueva Muta**: Suma +2 a una stat de un dino y lo registra en el log de mutaciones automáticamente.
3. **Alarmas**: Programa temporizadores de impronta/crecimiento. Opciones: **1.5h · 2.5h · 4h · 10h**. Te avisa por mención en el canal cuando expire.
4. **Ver Logs Muta**: Equivalente al comando `/log_mutas` pero accesible con un click.
5. **Selector Individual**: Menú desplegable inferior para aislar a un dino concreto y ver su ficha detallada en privado.""",
    "blacklist": """# :skull_crossbones: Blacklist

Jugadores "Kill on Sight" (KOS). Si están aquí, son enemigos confirmados; cuanta más info mejor.

### :no_entry_sign: Sistema de Blacklist
- **/blacklist**: Genera y ancla el Dashboard interactivo de la Lista Negra (auto-actualizable).
- **/bl_editar**: Atajo directo al modal de edición sin pasar por el panel (útil para cambios rápidos).

### :mouse_three_button: Botones del Panel
1. **Añadir**: Formulario rápido (Tribu, Mapa, Notas) para crear un enemigo.
2. **Modificar**: Cambia notas/mapa/nombre, o **conmuta entre Enemigo y Neutral**.
3. **Eliminar**: Borra una entrada por ID.
4. :arrow_backward: :arrow_forward: **Paginación**: 10 entradas por página.

### :red_circle: Enemigos vs :white_circle: Neutrales
- :red_circle: **ENEMIGOS** (`is_enemy=1`): jugadores a neutralizar sí o sí.
- :white_circle: **REGISTROS / NEUTRALES** (`is_enemy=0`): jugadores auto-detectados por K4Ultra que aún no nos han hecho nada (control y seguimiento).

### :gear: Enriquecimiento Automático
Cada minuto, **K4Ultra** completa cada entrada con:
- **Horas totales** observadas en el cluster.
- **Última vez visto** + mapa donde estaba.
- **Tribu sospechada** (cuando hay datos de relaciones).
No tienes que rellenar nada a mano — el bot lo va completando en background.""",
    "scouting": """# :satellite_orbital: Scouting

Reporte de bases enemigas. La información es poder.

### :telescope: Comandos de Reconocimiento
- **/scout_add**: Registra una base enemiga con todos los detalles (acepta imagen como enlace).
  - *Campos:* `tribu`, `mapa`, `coords`, `amenaza` (1-5 :star:, validado), `imagen`, `notas`.
- **/scout_add_image**: Adjunta una imagen desde tu PC a un scout ya existente.
  - *Uso:* `/scout_add_image id:12 imagen:[adjuntar archivo]`.
- **/scout_list**: Abre el panel Dashboard.
  - *Sin argumentos:* lista **GLOBAL** paginada de todos los mapas.
  - *Con argumento `mapa:`*: filtro privado que te enseña solo las bases de ese mapa.
- **/scout_delete**: Elimina un reporte obsoleto por ID.

### :mouse_three_button: Botones y Menú del Panel
- **Añadir Scout**: formulario sin imagen (para agregarla luego con `/scout_add_image`).
- **Modificar / Eliminar Scout**: por ID.
- :arrow_backward: :arrow_forward: **Paginación** entre mapas.
- :pushpin: **Selector inferior**: clic en un scout listado y ves su ficha **completa con imagen** en mensaje privado.

> :bulb: Niveles de amenaza válidos: del **1 (baja)** al **5 (extrema)**. Cualquier otro valor lo rechaza.""",
    "status": """# :green_circle: Estado de los Servidores

Monitoriza en tiempo real si los servidores están online, quién está conectado y qué ping tienen.

### :computer: Comandos
- **/status mapa:Gen2**: Consulta puntual de un servidor (autocompleta con tus mapas).
- **/status_online**: Vista resumida de **todo el cluster** en un único embed.
- **/status_permanente mapa:Gen2**: Ancla un mensaje que se auto-actualiza cada 2 min indefinidamente.

### :arrows_counterclockwise: Auto-Update y Colores
Los paneles persistentes refrescan automáticamente y cambian de aspecto según el estado:
- :green_circle: **Verde** — servidor online con jugadores dentro (los lista).
- :yellow_circle: **Amarillo** — servidor online pero vacío.
- :red_circle: **Rojo** — servidor caído (timeout / sin respuesta A2S).

### :stopwatch: Detalle Técnico
Las consultas A2S se centralizan con un caché compartido de 90 s, lo que permite que **Status**, **K4Ultra** y **Alarmas** reutilicen el mismo sondeo sin bombardear los servidores.

### :bell: Alarmas de Intrusos (resumen)
- **/alarma mapa:Fjordur estado:on** activa la vigilancia de un mapa; **off** la desactiva.
- **/alarmas** abre el panel rápido con todas tus alarmas configurables.
- El bot te menciona cuando entra al mapa un jugador que NO es de tu tribu propia ni de los personajes registrados. Cada alerta lleva un botón **✅ Completado** para silenciarla.

> :bulb: Más detalle en `/info modulo:🔔 Alarmas de Intrusos`.""",
    "k4ultra": """# :eye: Tracker de Inteligencia (K4Ultra)

K4Ultra monitoriza de forma pasiva el cluster para calcular el comportamiento, sesiones y alianzas enemigas a partir del protocolo A2S (sin tocar Battlemetrics).

### :satellite: Modos de Visualización
- **/k4ultra**: Levanta el panel principal (modo Radar por defecto).
  - **Radar / Ranking**: jugadores online + top de horas jugadas (paginado :arrow_backward: :arrow_forward:).
  - **Tribus / Relaciones**: grafo de alianzas predictivo. Cada par de jugadores acumula puntos por minutos compartidos en el mismo mapa, logins/logouts sincronizados y transferencias simultáneas. Decae **5% al día** si dejan de coincidir.

### :crown: Identificación de tu propia tribu
- **/tribu_propia crear nombre:"MiTribu" jugadores:"a, b, c"** — marca tu base.
- **/tribu_propia modificar opcion:... valor:...** — añade/quita miembros o renombra.
- **/tribu_propia borrar seguro:True** — limpia el registro.
- **/fijar_tribu / /unfijar_tribu** — para marcar **otras** tribus conocidas (enemigos confirmados, aliados, etc.) y que aparezcan etiquetadas en el modo Tribus.

### :busts_in_silhouette: Gestión de Identidades
Imprescindible para que el ranking y la blacklist no se llenen de duplicados:
- **/perfil_tribu usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registra un miembro completo en una sola llamada.
- **/fusionar_perfiles secundario:NombreViejo primario:NombreNuevo** — todo lo que el bot registró bajo el nombre antiguo (horas, mapas, sesiones) se reasigna al nuevo de forma perpetua.
- **/k4ultra_merge origen:"123_1" destino:"123"** — fusiona perfiles duplicados manualmente.
- **/k4ultra_split origen:... destino:...** — separa un perfil que el bot agrupó por error.
- **/k4ultra_cleanup** — [Admin] limpieza masiva: une todos los `nombre_1`/`_2` con su base.

### :mouse_three_button: Botones del Panel
- **➕ Añadir Relación / ➖ Eliminar Relación**: declarar/desdeclarar alianzas manuales (no decaen).
- **✏️ Renombrar Tribu**: asigna un alias persistente a una tribu detectada (ej. "Cluster A" → "Los Alfas").
- **Selector de Jugador**: clic en un jugador → expediente completo (perfil unificado con KDA + horas + mapas) en privado.""",
    "ranking": """# :skull_crossbones: EL SALÓN DE LA INFAMIA (Rancómetro)

El bot usa un **Log Processor** que escucha 24/7 el canal de Logs del servidor y parsea cada muerte.

### :chart_with_downwards_trend: Funcionamiento
- **Detección automática:** cada `fue 🔪` o `was :knife:` en los logs incrementa el contador de muertes del personaje. Las kills se ignoran a propósito (solo contamos muertes).
- **Anti-fuego-amigo:** si el asesino también es miembro registrado de tu tribu (vía `/perfil_tribu`), la muerte NO suma — solo se queda en el log con un aviso de "fuego amigo".
- **Sarcasmos:** el bot responde a cada muerte con una frase aleatoria + emoji aleatorio (💀🤡🪦🥚🍗🧻🗑️).
- **Hitos especiales:** las muertes números **1, 10, 50, 69, 100, 300, 420, 666, 777, 1000** y todos los múltiplos de 100 disparan mensajes con GIF dedicado. Vete acumulando.

### :busts_in_silhouette: Configuración Obligatoria
Para que el sistema pueda atribuir muertes:
- **/perfil_tribu usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registra a un miembro.
- **/ranking** — Dashboard del Death Counter ordenado por bajas.

### :sunrise: Recordatorios de Votos
El módulo de **Puntos Diarios** (`/info modulo:🌅 Puntos Diarios`) es opcional y complementario — te avisa por DM cada día para que canjees los votos del cluster.""",
    "alarmas": """# :bell: Alarmas de Intrusos por Mapa

Sistema de defensa pasiva: el bot vigila los mapas que elijas y te **menciona** cuando entra un jugador que NO esté en tu tribu propia ni registrado como personaje conocido.

### :gear: Comandos
- **/alarma mapa:Fjordur estado:on** — Activa la vigilancia de un mapa.
- **/alarma mapa:Fjordur estado:off** — La desactiva.
- **/alarmas** — Abre el **panel interactivo** con todas las alarmas configurables del cluster (más cómodo que el comando suelto).

### :brain: Cómo decide si alguien es intruso
Cada minuto el bot lee el caché de Status (no genera tráfico extra) y compara contra el último snapshot del mapa. Para cada jugador NUEVO:
1. Si está en tu tribu propia (`/tribu_propia`) → ignora.
2. Si está registrado como personaje conocido (`/perfil_tribu`) → ignora.
3. Si no → :rotating_light: **alarma**: te menciona en el canal donde activaste la alarma con la lista de intrusos.

### :pushpin: Detalle
- Las alarmas son **por usuario** y por mapa: cada miembro puede tener su propia lista.
- Multi-mapa: puedes vigilar varios mapas a la vez sin coste extra.
- El mensaje de alarma incluye un botón **✅ Completado** para silenciarlo.""",
    "puntos_diarios": """# :sunrise: Puntos Diarios de Voto

Recordatorio personal por DM para que canjees los puntos diarios votando tu cluster en los rankings públicos.

### :gear: Comandos de Usuario
- **/puntos_diarios estado:on hora:8 zona:España** — Activa el recordatorio diario a la hora indicada.
  - Zonas soportadas: **España (es)** y **México (mx)**.
  - Hora válida: **0-23** (defecto 8).
- **/puntos_diarios estado:off** — Cancela los recordatorios.

### :man_office_worker: Comandos de Admin
- **/config_puntos estado:on|off vote_links:"Mapa1|URL1,Mapa2|URL2"** — Activa/desactiva el sistema para todo el servidor y personaliza los URLs de voto.
- **/config_puntos** (sin args) — Muestra el estado actual y los URLs configurados.

### :white_check_mark: Cómo Funciona
1. A la hora elegida el bot te manda un DM con los enlaces de voto del cluster.
2. El DM incluye un botón **✅ Completado** que marca el día como hecho (visual, no toca tu cuenta de ARK).
3. Al día siguiente vuelve a avisarte automáticamente.

> :bulb: Si el admin desactiva el sistema para todo el servidor con `/config_puntos estado:off`, deja de mandar avisos aunque tengas la suscripción activa.""",
    "eventos": """# :calendar_spiral: Gestión de Eventos LFG

Planifica asaltos, defensas, jefes o farmeos coordinados con votación grupal.

### :calendar: Comando Único
- **/evento titulo:"Dragon Alpha" descripcion:"Traer 10 rexes" opcion_1:"Vie 22:00" opcion_2:"Sáb 18:00" opcion_3:... opcion_4:...**
  - Mínimo **2 opciones** válidas; opcion_3 y opcion_4 son opcionales.

### :ballot_box: Votación
El bot crea un embed con un botón por opción y un botón extra **❌ No puedo asistir**.
- Cada usuario puede votar **una sola opción** (votar otra reemplaza la anterior automáticamente).
- El embed se refresca con cuentas y barras de progreso en vivo.
- Los nombres de los votantes se listan bajo cada opción.

### :pushpin: Persistencia
Los eventos se guardan en la base de datos y los botones siguen funcionando aunque reinicies el bot.""",
    "admin": """# :shield: Configuración y Administración

Comandos reservados a administradores del servidor o al rol/usuario marcado como propietario en `guild_config`.

### :rocket: Setup Inicial
- **/inicio_ark** — Asistente que vincula el bot al servidor:
  - Canales: SOS, Logs, Uploads.
  - Roles admin, propietario.
  - Cluster: `battlemetrics_urls` con formato `Mapa1|IP:PORT,Mapa2|IP:PORT2`.
  - Crea automáticamente los hilos/canales de los dashboards.
- **/config** — Mismo formulario que `/inicio_ark` pero para **editar** la configuración existente sin recrear los dashboards. Sin argumentos, muestra el estado actual.
- **/bind_k4ultra message_id:... channel_id:...** — Asocia un mensaje existente al dashboard de K4Ultra (útil tras reinstalar el bot).

### :recycle: Mantenimiento
- **/clear_updates** — Borra solo los registros de mensajes/dashboards (no toca datos). Útil cuando los dashboards se han desincronizado.
- **/wipe_db** — :radioactive: Borra **TODOS** los datos del servidor (scouts, blacklist, todo-list, líneas, etc.). Acción destructiva — pide confirmación. Solo el propietario.

### :memo: Diagnóstico
- **/log** — Muestra los últimos comandos ejecutados en la sesión actual del bot.
- **/guia** — Guía completa textual del bot (resumen de todos los módulos).
- **/info modulo:...** — Esta misma ayuda contextual por módulo.""",
    "backup": """# :floppy_disk: Backups de la Base de Datos

El bot guarda automáticamente una copia diaria de `tribe_data.db` para recuperar el estado tras incidentes.

### :alarm_clock: Backup Automático
- Se ejecuta **todos los días a las 04:00 UTC**.
- Los archivos se guardan en `backups/tribe_data_YYYY-MM-DD.db`.
- **Retención: 7 días**: los backups con más de una semana se borran automáticamente.

### :gear: Backup Manual
- **/db_backup** — Genera un backup **al instante**. Útil antes de cambios destructivos (`/wipe_db`, migración de versión, etc.).
  - Devuelve el nombre del archivo y el tamaño en KB.
  - Aplica también la retención de 7 días.

### :information_source: Recuperación
Si necesitas restaurar un backup, copia el `.db` deseado encima de `tribe_data.db` con el bot **detenido** (`systemctl stop arkbot`). Al arrancar, el esquema se valida y migra automáticamente vía `db/schema.py`.

> :warning: Los backups son **locales al servidor del bot**. Si pierdes el servidor entero, pierdes la DB. Considera mantener una copia externa cada cierto tiempo.""",
}


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
        todo_embed, _page, view = build_todo_embed_view(self.bot, rows, page=0)
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

        embed, _page, view = build_todo_embed_view(self.bot, rows, page=0)
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
        ]
    )
    async def info(self, interaction: discord.Interaction, modulo: app_commands.Choice[str]):
        embed = discord.Embed(
            description=INFO_TEXTS.get(modulo.value, "Información no encontrada."),
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

        # Mensaje de confirmación detallado
        embed = discord.Embed(
            title="✅ Identidades Fusionadas",
            description=f"El perfil histórico de **{secundario}** ha sido traspasado y fusionado de manera perpetua a **{primario}**.",
            color=discord.Color.brand_green(),
        )
        embed.set_footer(
            text="A partir de ahora, el bot convertirá automáticamente a este jugador si se conecta usando su viejo nombre de Steam."
        )

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
    )
    async def perfil_tribu(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        personaje: str,
        steam: str = None,
        apodo: str = None,
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

        await db.commit()

        embed = discord.Embed(
            title="✅ Perfil de Tribu Configurado",
            description=f"El jugador {usuario.mention} ha sido registrado globalmente en la base de datos.",
            color=discord.Color.green(),
        )
        embed.add_field(name="📛 In-Game", value=f"`{personaje}`", inline=True)
        embed.add_field(name="👤 Apodo", value=f"`{apodo_final}`", inline=True)
        embed.add_field(name="🎮 Steam", value=f"`{steam_safe}`", inline=True)
        embed.set_footer(text="Vinculado al Rancómetro y al Radar K4Ultra con éxito.")

        await interaction.response.send_message(embed=embed, ephemeral=False)

        # Puesto que actualizamos records, recargamos el dashboard de muertes vía bus.
        self.bot.dispatch(bus.KDA_UPDATED, interaction.guild_id)

    @app_commands.command(
        name="guia",
        description="Muestra la guía completa de uso y comandos del bot.",
    )
    async def guia(self, interaction: discord.Interaction):
        """Manual interactivo que reutiliza las secciones de ``INFO_TEXTS``.

        Las etiquetas y emojis se mantienen alineados con las ``Choice`` de
        ``/info`` para que el usuario reconozca el mismo módulo en ambos
        comandos. Si añades una entrada a ``INFO_TEXTS``, añade aquí su
        ``SelectOption`` con la clave coincidente (Discord limita a 25 opciones).
        """

        class GuiaView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                # NOTA: ``value`` debe coincidir con una clave de INFO_TEXTS o
                # la opción se descarta silenciosamente por el filtro de abajo.
                options = [
                    discord.SelectOption(label="SOS & Alertas", value="sos", emoji="🆘"),
                    discord.SelectOption(label="Alarmas de Intrusos", value="alarmas", emoji="🔔"),
                    discord.SelectOption(label="To-Do List", value="todo_list", emoji="📝"),
                    discord.SelectOption(label="Líneas de Genética", value="lineas", emoji="🧬"),
                    discord.SelectOption(label="Blacklist", value="blacklist", emoji="☠️"),
                    discord.SelectOption(label="Scouting", value="scouting", emoji="🛰️"),
                    discord.SelectOption(label="Status Servidores", value="status", emoji="🟢"),
                    discord.SelectOption(label="K4Ultra Radar", value="k4ultra", emoji="👁️"),
                    discord.SelectOption(label="Ranking de Muertes", value="ranking", emoji="🪦"),
                    discord.SelectOption(label="Puntos Diarios", value="puntos_diarios", emoji="🌅"),
                    discord.SelectOption(label="Eventos LFG", value="eventos", emoji="📆"),
                    discord.SelectOption(label="Setup & Admin", value="admin", emoji="🛡️"),
                    discord.SelectOption(label="Backups DB", value="backup", emoji="💾"),
                ]
                # Filtro defensivo: solo opciones con clave existente en INFO_TEXTS.
                valid = [opt for opt in options if opt.value in INFO_TEXTS]
                self.select = discord.ui.Select(
                    placeholder="Selecciona una sección de la guía...",
                    options=valid,
                )
                self.select.callback = self.select_callback
                self.add_item(self.select)

            async def select_callback(self, i: discord.Interaction):
                val = self.select.values[0]
                text = INFO_TEXTS.get(val, "Sección en construcción.")
                emb = discord.Embed(description=text, color=discord.Color.blurple())
                await i.response.edit_message(embed=emb, view=self)

        embed_inicial = discord.Embed(
            title="📚 Manual de Usuario - ArkTribeBot",
            description=(
                "Selecciona una sección del menú inferior para conocer los comandos y "
                "funcionamiento de cada módulo.\n\n"
                "💡 **Si acabas de llegar:** usa `/perfil_tribu` para registrarte en el "
                "sistema (necesario para el ranking de muertes y K4Ultra).\n"
                "⚙️ **Si eres admin:** empieza por la sección *Setup & Admin* para "
                "configurar el bot con `/inicio_ark`."
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed_inicial, view=GuiaView(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Management(bot))
