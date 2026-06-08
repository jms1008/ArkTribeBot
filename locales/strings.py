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
        # --- Comunes (reutilizadas por varios comandos) ---
        "common.denied": "❌ Acceso denegado.",
        "common.no_servers": "❌ No hay servidores configurados. Usa `/inicio_ark` primero.",
        # --- /alarma (respuestas de comando) ---
        "alarm.cmd.map_not_found": "❌ El mapa `{map}` no existe en la configuración actual.",
        "alarm.cmd.off": "🔕 Alarma para **{map}** desactivada.",
        "alarm.cmd.on": (
            "🚨 **Alarma activada** para `{map}`. Te mencionaré en este canal "
            "cuando entre un intruso. 🔔"
        ),
        "alarm.cmd.error": "❌ Ocurrió un error al procesar la alarma: {err}",
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
        "kda.empty_footer": "💡 Los perfiles se vinculan con /tribu miembro",
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
        "scout.empty": "No hay reportes de bases enemigas.\n💡 Usa `/scout add` para registrar una.",
        "scout.badges": "📊 `{total}` bases registradas",
        "scout.footer": "Página {page}/{pages} • /scout imagen [id] para foto",
        "scout.btn.add": "Añadir Scout",
        "scout.btn.modify": "Modificar Scout",
        "scout.btn.delete": "Eliminar Scout",
        "scout.cmd.added": "✅ Base de **{tribu}** ({mapa}) registrada. [Scout **#{id}**]",
        "scout.cmd.not_found": "❌ No existe ningún registro de scout con ID **{id}**.",
        "scout.cmd.no_perms": "❌ No tienes permisos para modificar el Scout **#{id}** (pertenece a otro servidor).",
        "scout.cmd.image_added": "✅ Imagen adjuntada satisfactoriamente al Scout **#{id}** ({tribu}).",
        "scout.cmd.delete_not_found": "❌ ID {id} no encontrado o no tienes permisos.",
        "scout.cmd.deleted": "🗑️ Registro #{id} eliminado.",
        # --- Breeding / Líneas dashboard ---
        "breeding.title": "🧬 LÍNEAS DE CRIANZA (Top Stats)",
        "breeding.empty": (
            "📭 No hay líneas registradas aún.\n\n"
            "💡 Usa `/linea add dino:Rex estadistica:HP puntos:50` para empezar."
        ),
        "breeding.empty_footer": "Página 1/1 • 0 especies",
        "breeding.badges": "📊 `{total:02d}` especies registradas  ·  📄 Página `{page}/{pages}`",
        "breeding.section": "## 🦖 ESPECIES",
        "breeding.footer": (
            "Página {page}/{pages}  •  {total} especies totales  "
            "•  ❤️HP ⚔️Melee ⚡Stam ⚖️Peso 🫧Oxy 🍖Food 💨Speed  •  /linea add"
        ),
        "breeding.btn.muta": "Nueva muta",
        "breeding.btn.alarms": "Alarmas",
        "breeding.btn.logs": "Ver Logs Muta",
        # --- /linea (respuestas de comando) ---
        "linea.action.created": "registrada (nueva línea)",
        "linea.action.updated": "stats actualizados",
        "linea.cmd.add": "✅ 🧬 **{dino}** con **{puntos}** en **{stat}** {action}.",
        "linea.cmd.mod": "✅ Estadística modificada: **{dino}** -> **{stat}**: {puntos}.",
        "linea.cmd.not_found": "❌ No se encontró la especie **{dino}**.",
        "linea.ver.title": "🧬 STATS: {dino}",
        "linea.ver.registered": "🔢 Stats registradas: `{n}/7`",
        "linea.ver.footer": "💡 Usa /linea add para añadir o actualizar una stat",
        "linea.stat.hp": "HP",
        "linea.stat.melee": "Melee",
        "linea.stat.stam": "Stam",
        "linea.stat.weight": "Peso",
        "linea.stat.oxy": "Oxígeno",
        "linea.stat.food": "Comida",
        "linea.stat.speed": "Speed",
        "linea.log.no_logs": "No hay logs de mutaciones para este servidor.",
        "linea.log.none": "No se han registrado mutaciones históricamente.",
        "linea.log.double": "Doble muta",
        "linea.log.single": "Muta",
        "linea.log.entry": "⏰ `{ts}`: **{kind}** 🧬 **{dino}** en **{stat}**",
        "linea.log.title": "🧬 REGISTRO DE MUTACIONES",
        "linea.log.header": "📊 `{total}` mutaciones totales · mostrando las `{shown}` más recientes",
        "linea.log.footer": "💡 Usa el botón 'Nueva muta' del dashboard para registrar una",
        "linea.log.error": "Error leyendo logs: {err}",
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
        "k4.tribes.empty_hint": "💡 Usa `/tribu propia crear` para marcar tu base, o `/tribu fijar` para conocidas.",
        "k4.tribes.footer": (
            "Total jugadores conocidos: {total}  •  ⚫ Offline · 🟢 Online  •  /tribu propia · /tribu fijar"
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
        # --- /help (manual interactivo) ---
        "help.title": "📚 MANUAL DE USUARIO — ARKTRIBEBOT",
        "help.intro": (
            "Selecciona una sección del menú inferior para conocer los comandos y "
            "funcionamiento de cada módulo.\n\n"
            "## 🚀 Empezar\n"
            "> 💡 **Nuevo miembro:** usa `/tribu miembro` para registrarte (necesario para "
            "el ranking de muertes y el radar K4Ultra).\n"
            "> ⚙️ **Admin del servidor:** comienza por la sección *Setup & Admin* para "
            "configurar el bot con `/inicio_ark`."
        ),
        "help.placeholder": "Selecciona una sección de la guía...",
        "help.construction": "Sección en construcción.",
        "help.opt.sos": "SOS & Alertas",
        "help.opt.alarmas": "Alarmas de Intrusos",
        "help.opt.todo_list": "To-Do List",
        "help.opt.lineas": "Líneas de Genética",
        "help.opt.blacklist": "Blacklist",
        "help.opt.scouting": "Scouting",
        "help.opt.status": "Status Servidores",
        "help.opt.k4ultra": "K4Ultra Radar",
        "help.opt.ranking": "Ranking de Muertes",
        "help.opt.puntos_diarios": "Puntos Diarios",
        "help.opt.eventos": "Eventos LFG",
        "help.opt.admin": "Setup & Admin",
        "help.opt.backup": "Backups DB",
        # --- Ranking de muertes: hitos y sarcasmos (log_processor) ---
        "death.friendly_fire": "fuego amigo",
        # --- /sos ---
        "sos.title": "🚨 ALERTA SOS · {tipo}",
        "sos.generic_label": "AYUDA INMEDIATA",
        "sos.enemies": "enemigos",
        "sos.allies": "aliados",
        "sos.requester": "> **Solicitante:** {user}",
        "sos.general_call": "> *Llamada general — entrad al canal de voz YA.*",
        "sos.notes_header": "## 📝 Notas",
        "sos.footer": "¡Dejad lo que estéis haciendo y venid!",
        "sos.sent": "✅ Alerta SOS enviada.",
        "death.milestone.1": "¡Bienvenido a ARK! Tu primera muerte oficial de muchas... 🎉",
        "death.milestone.10": "Doble dígito de muertes... Ya eres un veterano en besar el suelo. 🥉",
        "death.milestone.50": "¡Medio centenar de muertes! 🥈 Estás a medias de convertirte en el mayor donante de loot del servidor.",
        "death.milestone.69": "69 muertes... Nice. Pero sigues estando muerto. 😏",
        "death.milestone.100": "¡100 MUERTES! 🥇 Oficialmente eres el jugador más manco de la tribu. Eres leyenda.",
        "death.milestone.300": "¡ESTO ES ESPARTA! Y tú eres el mensajero que acaban de tirar al pozo. 300 muertes.",
        "death.milestone.420": "420 muertes... 🌿 Demasiado humo en esa base, ¡deja de fumar flor rara!",
        "death.milestone.666": "666 muertes... 😈 Has invocado al Demonio de la Inutilidad. Vas directo al infierno.",
        "death.milestone.777": "¡VEGETTA777! ⛏️ Muy bonito, pero te acaba de farmear un dodo por la espalda.",
        "death.milestone.1000": "1000 MUERTES. 🏆 Hemos contactado con Wildcard. Te vamos a borrar el juego de Steam para que dejes de sufrir.",
        "death.milestone.century": "Sigues sumando de 100 en 100... ¿no te cansas? Ya van **{n}** muertes. 💀",
        "death.sarcasm": (
            "Estás pendejo... ya te moriste **{n}** veces...\n"
            "¡Felicidades! Has desbloqueado el logro: *Morir por {n}ª vez*. 🏆\n"
            "¿Otra vez? A este ritmo te van a cobrar alquiler en el respawn. (Muertes: **{n}**)\n"
            "Tranquilo, la **{n}ª** es la vencida... o no. 🤡\n"
            "Eres como un dodo, pero con menos instinto de supervivencia. (Total: **{n}**)\n"
            "¡Míralo! Si es que no se le puede dejar solo... Muertes: **{n}** 🤦‍♂️\n"
            "¿Has probado lo de no morir? Dicen que funciona bastante bien. (Contador: **{n}**)\n"
            "A este paso vas a amansar a los dinos salvajes a base de darles de comer tu propio cadáver. (**{n}** muertes)\n"
            "En el menú del servidor hoy toca: Carpaccio de {victim}. Ya llevas **{n}** muertes.\n"
            "Ni un mosco en verano muere tantas veces... Contador sube a **{n}**.\n"
            "Vete preparando saco, porque la cama ya la has derretido del uso. (Total: **{n}**)\n"
            "Tus padres no te criaron para feedear de esta manera tan vergonzosa. (**{n}** ☠️)\n"
            "Si la tribu dependiera de ti, seguiríamos con herramientas de piedra. (**{n}** veces)\n"
            "Muertes totales: **{n}**. El servidor está empezando a sentir lástima por ti.\n"
            "Bob the Builder construía mejor y moría menos que tú. (**{n}** defunciones)\n"
            "Tómate un respiro, ve a beber agua, porque madre mía la que estás liando... (**{n}**)\n"
            "Cuidado de no tropezar con una piedra y resbalar, que igual mueres por **{n}ª** vez consecutiva.\n"
            "Oye, que en este servidor no dan premio por ser el que más veces mira la pantalla de muerte. (**{n}**)\n"
            "Hasta un Triceratops despistado vive más tiempo que tú. Y eso que extinguieron hace milenios. (**{n}** bajas)\n"
            "¿Quién dejó la puerta abierta? Ah, no, que fuiste tú intentando huir... otra vez. (**{n}** muertes)"
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
        # --- Common (reused across commands) ---
        "common.denied": "❌ Access denied.",
        "common.no_servers": "❌ No servers configured. Use `/inicio_ark` first.",
        # --- /alarma (command replies) ---
        "alarm.cmd.map_not_found": "❌ The map `{map}` does not exist in the current config.",
        "alarm.cmd.off": "🔕 Alarm for **{map}** disabled.",
        "alarm.cmd.on": (
            "🚨 **Alarm enabled** for `{map}`. I'll mention you in this channel "
            "when an intruder shows up. 🔔"
        ),
        "alarm.cmd.error": "❌ An error occurred while processing the alarm: {err}",
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
        "kda.empty_footer": "💡 Profiles are linked with /tribu miembro",
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
        "scout.empty": "No enemy base reports.\n💡 Use `/scout add` to register one.",
        "scout.badges": "📊 `{total}` registered bases",
        "scout.footer": "Page {page}/{pages} • /scout imagen [id] for photo",
        "scout.btn.add": "Add Scout",
        "scout.btn.modify": "Edit Scout",
        "scout.btn.delete": "Delete Scout",
        "scout.cmd.added": "✅ Base of **{tribu}** ({mapa}) registered. [Scout **#{id}**]",
        "scout.cmd.not_found": "❌ No scout record exists with ID **{id}**.",
        "scout.cmd.no_perms": "❌ You don't have permission to edit Scout **#{id}** (it belongs to another server).",
        "scout.cmd.image_added": "✅ Image successfully attached to Scout **#{id}** ({tribu}).",
        "scout.cmd.delete_not_found": "❌ ID {id} not found or you lack permission.",
        "scout.cmd.deleted": "🗑️ Record #{id} deleted.",
        # --- Breeding / Lines dashboard ---
        "breeding.title": "🧬 BREEDING LINES (Top Stats)",
        "breeding.empty": (
            "📭 No lines registered yet.\n\n"
            "💡 Use `/linea add dino:Rex estadistica:HP puntos:50` to start."
        ),
        "breeding.empty_footer": "Page 1/1 • 0 species",
        "breeding.badges": "📊 `{total:02d}` registered species  ·  📄 Page `{page}/{pages}`",
        "breeding.section": "## 🦖 SPECIES",
        "breeding.footer": (
            "Page {page}/{pages}  •  {total} species total  "
            "•  ❤️HP ⚔️Melee ⚡Stam ⚖️Weight 🫧Oxy 🍖Food 💨Speed  •  /linea add"
        ),
        "breeding.btn.muta": "New mutation",
        "breeding.btn.alarms": "Alarms",
        "breeding.btn.logs": "View Mut. Logs",
        # --- /linea (command replies) ---
        "linea.action.created": "registered (new line)",
        "linea.action.updated": "stats updated",
        "linea.cmd.add": "✅ 🧬 **{dino}** with **{puntos}** in **{stat}** {action}.",
        "linea.cmd.mod": "✅ Stat modified: **{dino}** -> **{stat}**: {puntos}.",
        "linea.cmd.not_found": "❌ Species **{dino}** not found.",
        "linea.ver.title": "🧬 STATS: {dino}",
        "linea.ver.registered": "🔢 Registered stats: `{n}/7`",
        "linea.ver.footer": "💡 Use /linea add to add or update a stat",
        "linea.stat.hp": "HP",
        "linea.stat.melee": "Melee",
        "linea.stat.stam": "Stam",
        "linea.stat.weight": "Weight",
        "linea.stat.oxy": "Oxygen",
        "linea.stat.food": "Food",
        "linea.stat.speed": "Speed",
        "linea.log.no_logs": "No mutation logs for this server.",
        "linea.log.none": "No mutations recorded historically.",
        "linea.log.double": "Double mutation",
        "linea.log.single": "Mutation",
        "linea.log.entry": "⏰ `{ts}`: **{kind}** 🧬 **{dino}** in **{stat}**",
        "linea.log.title": "🧬 MUTATION LOG",
        "linea.log.header": "📊 `{total}` total mutations · showing the `{shown}` most recent",
        "linea.log.footer": "💡 Use the 'New mutation' button on the dashboard to record one",
        "linea.log.error": "Error reading logs: {err}",
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
        "k4.tribes.empty_hint": "💡 Use `/tribu propia crear` to mark your base, or `/tribu fijar` for known ones.",
        "k4.tribes.footer": (
            "Total known players: {total}  •  ⚫ Offline · 🟢 Online  •  /tribu propia · /tribu fijar"
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
        # --- /help (interactive manual) ---
        "help.title": "📚 USER MANUAL — ARKTRIBEBOT",
        "help.intro": (
            "Pick a section from the menu below to learn the commands and how each "
            "module works.\n\n"
            "## 🚀 Getting started\n"
            "> 💡 **New member:** use `/tribu miembro` to register (required for the "
            "death ranking and the K4Ultra radar).\n"
            "> ⚙️ **Server admin:** start with the *Setup & Admin* section to "
            "configure the bot with `/inicio_ark`."
        ),
        "help.placeholder": "Pick a guide section...",
        "help.construction": "Section under construction.",
        "help.opt.sos": "SOS & Alerts",
        "help.opt.alarmas": "Intruder Alarms",
        "help.opt.todo_list": "To-Do List",
        "help.opt.lineas": "Breeding Lines",
        "help.opt.blacklist": "Blacklist",
        "help.opt.scouting": "Scouting",
        "help.opt.status": "Server Status",
        "help.opt.k4ultra": "K4Ultra Radar",
        "help.opt.ranking": "Death Ranking",
        "help.opt.puntos_diarios": "Daily Points",
        "help.opt.eventos": "LFG Events",
        "help.opt.admin": "Setup & Admin",
        "help.opt.backup": "DB Backups",
        # --- Death ranking: milestones and sarcasm (log_processor) ---
        "death.friendly_fire": "friendly fire",
        # --- /sos ---
        "sos.title": "🚨 SOS ALERT · {tipo}",
        "sos.generic_label": "IMMEDIATE HELP",
        "sos.enemies": "enemies",
        "sos.allies": "allies",
        "sos.requester": "> **Requested by:** {user}",
        "sos.general_call": "> *General call — get in voice NOW.*",
        "sos.notes_header": "## 📝 Notes",
        "sos.footer": "Drop what you're doing and get over here!",
        "sos.sent": "✅ SOS alert sent.",
        "death.milestone.1": "Welcome to ARK! Your first official death of many... 🎉",
        "death.milestone.10": "Double-digit deaths... You're a veteran ground-kisser now. 🥉",
        "death.milestone.50": "Half a hundred deaths! 🥈 You're halfway to being the server's biggest loot donor.",
        "death.milestone.69": "69 deaths... Nice. But you're still dead. 😏",
        "death.milestone.100": "100 DEATHS! 🥇 Officially the clumsiest player in the tribe. You're a legend.",
        "death.milestone.300": "THIS IS SPARTA! And you're the messenger they just kicked down the well. 300 deaths.",
        "death.milestone.420": "420 deaths... 🌿 Too much smoke in that base, stop smoking the rare flower!",
        "death.milestone.666": "666 deaths... 😈 You've summoned the Demon of Uselessness. Straight to hell.",
        "death.milestone.777": "VEGETTA777! ⛏️ Very nice, but a dodo just farmed you from behind.",
        "death.milestone.1000": "1000 DEATHS. 🏆 We've contacted Wildcard. We're deleting the game from your Steam so you stop suffering.",
        "death.milestone.century": "Still racking them up 100 at a time... don't you get tired? Already **{n}** deaths. 💀",
        "death.sarcasm": (
            "You're hopeless... you've already died **{n}** times...\n"
            "Congrats! You unlocked the achievement: *Die for the {n}th time*. 🏆\n"
            "Again? At this rate they'll charge you rent at the respawn. (Deaths: **{n}**)\n"
            "Relax, the **{n}th** time's the charm... or not. 🤡\n"
            "You're like a dodo, but with less survival instinct. (Total: **{n}**)\n"
            "Look at this one! Can't be left alone for a second... Deaths: **{n}** 🤦‍♂️\n"
            "Have you tried just not dying? They say it works pretty well. (Counter: **{n}**)\n"
            "At this rate you'll tame wild dinos by feeding them your own corpse. (**{n}** deaths)\n"
            "Today's server menu: Carpaccio of {victim}. You're up to **{n}** deaths.\n"
            "Not even a summer mosquito dies this much... Counter climbs to **{n}**.\n"
            "Better get a sleeping bag ready, you've melted the bed from overuse. (Total: **{n}**)\n"
            "Your parents didn't raise you to feed this shamefully. (**{n}** ☠️)\n"
            "If the tribe depended on you, we'd still have stone tools. (**{n}** times)\n"
            "Total deaths: **{n}**. The server is starting to feel sorry for you.\n"
            "Bob the Builder built better and died less than you. (**{n}** demises)\n"
            "Take a breather, drink some water, because oh boy what a mess... (**{n}**)\n"
            "Careful not to trip on a rock and slip, you might die for the **{n}th** time in a row.\n"
            "Hey, this server gives no prize for staring at the death screen the most. (**{n}**)\n"
            "Even a clueless Triceratops lives longer than you. And they went extinct ages ago. (**{n}** casualties)\n"
            "Who left the door open? Oh wait, it was you trying to flee... again. (**{n}** deaths)"
        ),
        # --- /idioma ---
        "idioma.set.en_total": (
            "🌐 Language set: **English (everything)**.\n"
            "The entire bot — dashboards, command replies and messages — will now "
            "be shown in English."
        ),
    },
}
