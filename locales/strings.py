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
        # --- Scouting dashboard ---
        "scout.title": "🛰️ SCOUTING: {map}",
        "scout.empty": "No hay reportes de bases enemigas.\n💡 Usa `/scout_add` para registrar una.",
        "scout.badges": "📊 `{total}` bases registradas",
        "scout.footer": "Página {page}/{pages} • /scout_add_image [id] para foto",
        "scout.btn.add": "Añadir Scout",
        "scout.btn.modify": "Modificar Scout",
        "scout.btn.delete": "Eliminar Scout",
        # --- Breeding / Líneas dashboard ---
        "breeding.title": "🧬 LÍNEAS DE CRIANZA (Top Stats)",
        "breeding.empty": (
            "📭 No hay líneas registradas aún.\n\n"
            "💡 Usa `/linea_add dino:Rex estadistica:HP puntos:50` para empezar."
        ),
        "breeding.empty_footer": "Página 1/1 • 0 especies",
        "breeding.badges": "📊 `{total:02d}` especies registradas  ·  📄 Página `{page}/{pages}`",
        "breeding.section": "## 🦖 ESPECIES",
        "breeding.footer": (
            "Página {page}/{pages}  •  {total} especies totales  "
            "•  ❤️HP ⚔️Melee ⚡Stam ⚖️Peso 🫧Oxy 🍖Food 💨Speed  •  /linea_add"
        ),
        "breeding.btn.muta": "Nueva muta",
        "breeding.btn.alarms": "Alarmas",
        "breeding.btn.logs": "Ver Logs Muta",
        # --- Alarmas dashboard (panel compartido) ---
        "alarm.title": "🔔 PANEL DE ALARMAS DE LA TRIBU",
        "alarm.empty": (
            "💤 Nadie en la tribu tiene alarmas activas ahora mismo.\n\n"
            "💡 Selecciona un mapa en el menú inferior o usa `/alarma mapa:X estado:on` para activar la tuya."
        ),
        "alarm.empty_footer": "El bot avisa en el canal cuando entra un jugador desconocido al mapa vigilado.",
        "alarm.badges": "🗺️ `{maps:02d}` Mapas vigilados  ·  👥 `{unique:02d}` Vigilantes únicos  ·  📊 `{subs:02d}` Suscripciones",
        "alarm.section": "## 🟢 MAPAS BAJO VIGILANCIA",
        "alarm.map_line": "`#{idx:02d}` 🟢 **{map}**  ·  👥 `{count}` {word}",
        "alarm.watcher_one": "vigilante",
        "alarm.watcher_many": "vigilantes",
        "alarm.footer": "Selecciona un mapa en el menú inferior para activar/desactivar tu alarma  •  /alarma para comando directo",
        "alarm.select_placeholder": "Selecciona un mapa del clúster...",
        "alarm.btn.refresh": "Refrescar",
        # --- K4Ultra dashboard (radar) ---
        "k4.radar.title": "🌐 TRACKER K4ULTRA — Radar en Vivo",
        "k4.radar.header": "📡 `{online:02d}` Online  ·  🏆 `{total:02d}` En ranking  ·  📄 Página `{page}/{pages}`",
        "k4.radar.online_section": "## 📡 EN LÍNEA AHORA",
        "k4.radar.online_item": "🟢 **{name}**{alias}  ·  🗺️ {map}  ·  ⏱️ desde {since}",
        "k4.radar.nobody_online": "*Ningún jugador conectado ahora mismo.*",
        "k4.radar.top_section": "## 🏆 TOP JUGADORES",
        "k4.radar.top_section_cont": "## 🏆 TOP JUGADORES (Cont.)",
        "k4.radar.no_activity": "  └ *(sin actividad reciente)*",
        "k4.radar.no_data": "*No hay datos suficientes.*",
        "k4.radar.footer_single": "Radar  •  Página 1/1  •  Usa el selector para ver detalle de un jugador",
        "k4.radar.footer": "Radar  •  Página {page}/{pages}  •  Usa ◀️ ▶️ para navegar o el selector para ver detalle",
        # --- K4Ultra dashboard (tribus) ---
        "k4.tribes.title": "🌐 TRACKER K4ULTRA — Tribus y Grupos",
        "k4.tribes.header": (
            "🏰 `{own:02d}` Nuestras  ·  🛡️ `{fixed:02d}` Fijadas  ·  "
            "🔗 `{pred:02d}` Predichas  ·  🟢 `{online:02d}` online"
        ),
        "k4.tribes.own_section": "## 🏰 NUESTRA TRIBU",
        "k4.tribes.fixed_section": "## 🛡️ TRIBUS FIJADAS",
        "k4.tribes.pred_section": "## 🔗 GRUPOS PREDICHOS",
        "k4.tribes.tribe_header": "**{name}**  ·  👥 `{count:02d}`  ·  🟢 `{online:02d}` online{map_info}",
        "k4.tribes.group_name": "Grupo {i}",
        "k4.tribes.group_header": (
            "**{group}**  ·  👥 `{count:02d}`  ·  🟢 `{online:02d}` online{map_info}  ·  📊 `{bar}` {score}%"
        ),
        "k4.tribes.more_groups": "*… y {n} grupos más con menor confianza.*",
        "k4.tribes.empty": "📭 No hay tribus registradas ni grupos predecidos aún.",
        "k4.tribes.empty_hint": "💡 Usa `/tribu_propia crear` para marcar tu base, o `/fijar_tribu` para conocidas.",
        "k4.tribes.footer": (
            "Total jugadores conocidos: {total}  •  ⚫ Offline · 🟢 Online  •  /tribu_propia · /fijar_tribu"
        ),
        # --- Status global dashboard ---
        "status.title": "🌐 ESTADO GLOBAL DE SERVIDORES",
        "status.no_servers": "⚠️ No hay servidores configurados. Usa `/inicio_ark` para añadirlos.",
        "status.nobody": "Nadie conectado.",
        "status.total_players": "👥 **Total de jugadores en la red:** {occupancy}",
        "status.no_data": "*sin datos*",
        "status.badges": "🟢 `{pop:02d}` Activos  ·  🟡 `{empty:02d}` Vacíos  ·  🔴 `{off:02d}` Offline",
        "status.section.active": "## 🟢 SERVIDORES ACTIVOS",
        "status.section.empty": "## 🟡 SERVIDORES VACÍOS",
        "status.section.offline": "## 🔴 SERVIDORES OFFLINE / TIMEOUT",
        "status.footer": "Auto-actualizado cada 2 minutos  •  /status para ver un mapa concreto",
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
        # --- Scouting dashboard ---
        "scout.title": "🛰️ SCOUTING: {map}",
        "scout.empty": "No enemy base reports.\n💡 Use `/scout_add` to register one.",
        "scout.badges": "📊 `{total}` registered bases",
        "scout.footer": "Page {page}/{pages} • /scout_add_image [id] for photo",
        "scout.btn.add": "Add Scout",
        "scout.btn.modify": "Edit Scout",
        "scout.btn.delete": "Delete Scout",
        # --- Breeding / Lines dashboard ---
        "breeding.title": "🧬 BREEDING LINES (Top Stats)",
        "breeding.empty": (
            "📭 No lines registered yet.\n\n"
            "💡 Use `/linea_add dino:Rex estadistica:HP puntos:50` to start."
        ),
        "breeding.empty_footer": "Page 1/1 • 0 species",
        "breeding.badges": "📊 `{total:02d}` registered species  ·  📄 Page `{page}/{pages}`",
        "breeding.section": "## 🦖 SPECIES",
        "breeding.footer": (
            "Page {page}/{pages}  •  {total} species total  "
            "•  ❤️HP ⚔️Melee ⚡Stam ⚖️Weight 🫧Oxy 🍖Food 💨Speed  •  /linea_add"
        ),
        "breeding.btn.muta": "New mutation",
        "breeding.btn.alarms": "Alarms",
        "breeding.btn.logs": "View Mut. Logs",
        # --- Alarms dashboard (shared panel) ---
        "alarm.title": "🔔 TRIBE INTRUDER ALARMS PANEL",
        "alarm.empty": (
            "💤 Nobody in the tribe has active alarms right now.\n\n"
            "💡 Pick a map in the menu below or use `/alarma mapa:X estado:on` to enable yours."
        ),
        "alarm.empty_footer": "The bot warns in the channel when an unknown player enters a watched map.",
        "alarm.badges": "🗺️ `{maps:02d}` Watched maps  ·  👥 `{unique:02d}` Unique watchers  ·  📊 `{subs:02d}` Subscriptions",
        "alarm.section": "## 🟢 MAPS UNDER WATCH",
        "alarm.map_line": "`#{idx:02d}` 🟢 **{map}**  ·  👥 `{count}` {word}",
        "alarm.watcher_one": "watcher",
        "alarm.watcher_many": "watchers",
        "alarm.footer": "Pick a map in the menu below to toggle your alarm  •  /alarma for the direct command",
        "alarm.select_placeholder": "Pick a cluster map...",
        "alarm.btn.refresh": "Refresh",
        # --- K4Ultra dashboard (radar) ---
        "k4.radar.title": "🌐 K4ULTRA TRACKER — Live Radar",
        "k4.radar.header": "📡 `{online:02d}` Online  ·  🏆 `{total:02d}` Ranked  ·  📄 Page `{page}/{pages}`",
        "k4.radar.online_section": "## 📡 ONLINE NOW",
        "k4.radar.online_item": "🟢 **{name}**{alias}  ·  🗺️ {map}  ·  ⏱️ since {since}",
        "k4.radar.nobody_online": "*No players connected right now.*",
        "k4.radar.top_section": "## 🏆 TOP PLAYERS",
        "k4.radar.top_section_cont": "## 🏆 TOP PLAYERS (Cont.)",
        "k4.radar.no_activity": "  └ *(no recent activity)*",
        "k4.radar.no_data": "*Not enough data.*",
        "k4.radar.footer_single": "Radar  •  Page 1/1  •  Use the selector to view a player's detail",
        "k4.radar.footer": "Radar  •  Page {page}/{pages}  •  Use ◀️ ▶️ to navigate or the selector for detail",
        # --- K4Ultra dashboard (tribes) ---
        "k4.tribes.title": "🌐 K4ULTRA TRACKER — Tribes & Groups",
        "k4.tribes.header": (
            "🏰 `{own:02d}` Ours  ·  🛡️ `{fixed:02d}` Pinned  ·  "
            "🔗 `{pred:02d}` Predicted  ·  🟢 `{online:02d}` online"
        ),
        "k4.tribes.own_section": "## 🏰 OUR TRIBE",
        "k4.tribes.fixed_section": "## 🛡️ PINNED TRIBES",
        "k4.tribes.pred_section": "## 🔗 PREDICTED GROUPS",
        "k4.tribes.tribe_header": "**{name}**  ·  👥 `{count:02d}`  ·  🟢 `{online:02d}` online{map_info}",
        "k4.tribes.group_name": "Group {i}",
        "k4.tribes.group_header": (
            "**{group}**  ·  👥 `{count:02d}`  ·  🟢 `{online:02d}` online{map_info}  ·  📊 `{bar}` {score}%"
        ),
        "k4.tribes.more_groups": "*… and {n} more groups with lower confidence.*",
        "k4.tribes.empty": "📭 No tribes registered or groups predicted yet.",
        "k4.tribes.empty_hint": "💡 Use `/tribu_propia crear` to mark your base, or `/fijar_tribu` for known ones.",
        "k4.tribes.footer": (
            "Total known players: {total}  •  ⚫ Offline · 🟢 Online  •  /tribu_propia · /fijar_tribu"
        ),
        # --- Status global dashboard ---
        "status.title": "🌐 GLOBAL SERVER STATUS",
        "status.no_servers": "⚠️ No servers configured. Use `/inicio_ark` to add them.",
        "status.nobody": "Nobody connected.",
        "status.total_players": "👥 **Total players on the network:** {occupancy}",
        "status.no_data": "*no data*",
        "status.badges": "🟢 `{pop:02d}` Active  ·  🟡 `{empty:02d}` Empty  ·  🔴 `{off:02d}` Offline",
        "status.section.active": "## 🟢 ACTIVE SERVERS",
        "status.section.empty": "## 🟡 EMPTY SERVERS",
        "status.section.offline": "## 🔴 OFFLINE / TIMEOUT SERVERS",
        "status.footer": "Auto-updated every 2 minutes  •  /status to view a specific map",
        # --- /idioma ---
        "idioma.set.en_total": (
            "🌐 Language set: **English (everything)**.\n"
            "The entire bot — dashboards, command replies and messages — will now "
            "be shown in English."
        ),
    },
}
