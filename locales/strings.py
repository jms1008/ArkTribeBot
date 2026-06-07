"""Catálogo de cadenas de UI cortas, indexado por idioma.

Estructura: ``STRINGS[lang][key] = "plantilla"``. Las plantillas pueden contener
placeholders de ``str.format`` (ej. ``"{total} tareas"``).

Convención de claves: ``modulo.subclave`` (ej. ``todo.title``, ``blacklist.footer``).

Este catálogo se rellena de forma incremental según avanzan las fases del soporte
bilingüe. La función ``utils.i18n.t`` cae a español si falta una clave en inglés.
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "es": {
        # --- To-Do dashboard ---
        "todo.title": "📋 LISTA DE TAREAS",
        "todo.empty": (
            "✅ ¡Sin tareas pendientes! La tribu está al día. 🎉\n\n"
            "*Pulsa **Añadir Tarea** o usa `/todo_add` para crear una nueva.*"
        ),
        "todo.empty_footer": "Página 1/1 • 0 tareas",
        "todo.badges": "🔨 `{progress:02d}` En Progreso  ·  ⏳ `{pending:02d}` Pendientes  ·  📊 `{total:02d}` Total",
        "todo.section.progress": "## 🔨 EN PROGRESO",
        "todo.section.pending": "## ⏳ PENDIENTES",
        "todo.unassigned": "*Sin asignar*",
        "todo.footer": "Página {page}/{pages} • {total} tareas totales • /todo_add para añadir",
        "todo.btn.add": "Añadir Tarea",
        "todo.btn.claim": "Reclamar Tarea",
        "todo.btn.delete": "Eliminar Tarea",
        # --- Blacklist dashboard ---
        "blacklist.title": "☠️ BLACKLIST DE TRIBU",
        "blacklist.empty": (
            "La lista está limpia. No hay jugadores registrados.\n"
            "💡 Usa el botón **Añadir** para registrar el primero."
        ),
        "blacklist.badges": "🔴 `{enemies}` Enemigos  ·  ⚪ `{neutrals}` Neutrales  ·  📊 `{total}` Total",
        "blacklist.section.enemies": "## 🔴 ENEMIGOS (KOS)",
        "blacklist.section.neutrals": "## ⚪ REGISTROS (NEUTRALES)",
        "blacklist.footer": "Página {page}/{pages} • {total} entradas totales • /bl_editar para modificar",
        "blacklist.btn.add": "Añadir",
        "blacklist.btn.modify": "Modificar",
        "blacklist.btn.delete": "Eliminar",
        # --- KDA / Ranking de muertes dashboard ---
        "kda.title": "☠️ EL SALÓN DE LA INFAMIA",
        "kda.empty_title": "☠️ El Salón de la Infamia",
        "kda.empty_desc": "Todavía no hay registros de mortalidad en la tribu. ¡Seguid así! 🛡️",
        "kda.empty_footer": "💡 Los perfiles se vinculan con /perfil_tribu",
        "kda.rank.1": "Novato Inocente",
        "kda.rank.2": "Pienso de Dodo",
        "kda.rank.3": "Ceviche de Raptor",
        "kda.rank.4": "Saco de Dormir Humano",
        "kda.rank.5": "Leyenda del Respawn",
        "kda.rank.6": "ALPHA MANCO SUPREMO",
        "kda.king": "## 🏆 Rey de los Mancos: **{name}**",
        "kda.king_desc": "> Con **{deaths}** muertes ostenta el trono de la vergüenza.",
        "kda.king_line": "> {emoji} **{rank}** — `{bar}` {pct}%{peak}",
        "kda.king_peak": " · 🔥 Pico: `{peak}`/h",
        "kda.total_deaths": "Muertes totales de la tribu: **{total}** 📉",
        "kda.entry_name": "**{medal} #{idx} {player}**",
        "kda.entry_line": "  {emoji} *{rank}*  ·  `{bar}` **{deaths}** ({pct}%){peak}",
        "kda.entry_peak": " · 🔥`{peak}`/h",
        "kda.footer": "💡 {phrase} • 🔥/h = pico máximo en 1 hora",
        "kda.footer_phrases": (
            "Morir es de guapos, y nosotros somos modelos.\n"
            "¿Para qué farmear si puedes donar tu loot al suelo?\n"
            "El verdadero endgame es el respawn.\n"
            "No estamos muriendo, estamos practicando.\n"
            "Cada muerte nos hace más fuertes... mentalmente.\n"
            "Tribu líder en donación involuntaria de inventario.\n"
            "Respawneamos más rápido que los dinos salvajes."
        ),
        # --- /idioma ---
        "idioma.denied": "❌ Acceso denegado. Necesitas permisos de administrador.",
        "idioma.set.es": (
            "🌐 Idioma configurado: **Español**.\n"
            "Todo el bot se mostrará en español."
        ),
        "idioma.set.en_periodic": (
            "🌐 Idioma configurado: **Inglés (solo dashboards)**.\n"
            "Los paneles automáticos pasarán a inglés; los comandos y mensajes "
            "seguirán en español."
        ),
    },
    "en": {
        # --- To-Do dashboard ---
        "todo.title": "📋 TASK LIST",
        "todo.empty": (
            "✅ No pending tasks! The tribe is all caught up. 🎉\n\n"
            "*Press **Add Task** or use `/todo_add` to create a new one.*"
        ),
        "todo.empty_footer": "Page 1/1 • 0 tasks",
        "todo.badges": "🔨 `{progress:02d}` In Progress  ·  ⏳ `{pending:02d}` Pending  ·  📊 `{total:02d}` Total",
        "todo.section.progress": "## 🔨 IN PROGRESS",
        "todo.section.pending": "## ⏳ PENDING",
        "todo.unassigned": "*Unassigned*",
        "todo.footer": "Page {page}/{pages} • {total} tasks total • /todo_add to add",
        "todo.btn.add": "Add Task",
        "todo.btn.claim": "Claim Task",
        "todo.btn.delete": "Delete Task",
        # --- Blacklist dashboard ---
        "blacklist.title": "☠️ TRIBE BLACKLIST",
        "blacklist.empty": (
            "The list is clean. No players registered.\n"
            "💡 Use the **Add** button to register the first one."
        ),
        "blacklist.badges": "🔴 `{enemies}` Enemies  ·  ⚪ `{neutrals}` Neutrals  ·  📊 `{total}` Total",
        "blacklist.section.enemies": "## 🔴 ENEMIES (KOS)",
        "blacklist.section.neutrals": "## ⚪ RECORDS (NEUTRALS)",
        "blacklist.footer": "Page {page}/{pages} • {total} total entries • /bl_editar to edit",
        "blacklist.btn.add": "Add",
        "blacklist.btn.modify": "Edit",
        "blacklist.btn.delete": "Delete",
        # --- KDA / Death ranking dashboard ---
        "kda.title": "☠️ THE HALL OF INFAMY",
        "kda.empty_title": "☠️ The Hall of Infamy",
        "kda.empty_desc": "No mortality records in the tribe yet. Keep it up! 🛡️",
        "kda.empty_footer": "💡 Profiles are linked with /perfil_tribu",
        "kda.rank.1": "Innocent Rookie",
        "kda.rank.2": "Dodo Feed",
        "kda.rank.3": "Raptor Ceviche",
        "kda.rank.4": "Human Sleeping Bag",
        "kda.rank.5": "Respawn Legend",
        "kda.rank.6": "SUPREME ALPHA NOOB",
        "kda.king": "## 🏆 King of Noobs: **{name}**",
        "kda.king_desc": "> With **{deaths}** deaths he holds the throne of shame.",
        "kda.king_line": "> {emoji} **{rank}** — `{bar}` {pct}%{peak}",
        "kda.king_peak": " · 🔥 Peak: `{peak}`/h",
        "kda.total_deaths": "Tribe total deaths: **{total}** 📉",
        "kda.entry_name": "**{medal} #{idx} {player}**",
        "kda.entry_line": "  {emoji} *{rank}*  ·  `{bar}` **{deaths}** ({pct}%){peak}",
        "kda.entry_peak": " · 🔥`{peak}`/h",
        "kda.footer": "💡 {phrase} • 🔥/h = highest peak in 1 hour",
        "kda.footer_phrases": (
            "Dying is for the cool kids, and we're supermodels.\n"
            "Why farm when you can donate your loot to the floor?\n"
            "The real endgame is the respawn screen.\n"
            "We're not dying, we're practicing.\n"
            "Every death makes us stronger... mentally.\n"
            "Tribe leader in involuntary inventory donation.\n"
            "We respawn faster than wild dinos."
        ),
        # --- /idioma ---
        "idioma.set.en_total": (
            "🌐 Language set: **English (everything)**.\n"
            "The entire bot — dashboards, command replies and messages — will now "
            "be shown in English."
        ),
    },
}
