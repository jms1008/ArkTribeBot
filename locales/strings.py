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
        "common.min_2_players": "❌ Debes especificar al menos 2 jugadores válidos separados por comas.",
        "common.loading": "⏳ Cargando...",
        # --- /evento (encuesta LFG) ---
        "evento.min_options": "Debes proporcionar al menos 2 opciones de fecha/hora válidas para la encuesta.",
        "evento.deleted": "El evento ya no existe en la base de datos.",
        "evento.title": "📅 Evento: {titulo}",
        "evento.author": "Organizado por {name}",
        "evento.unknown_creator": "Desconocido",
        "evento.nobody": "*Nadie todavía*",
        "evento.votes": "votos",
        "evento.field_value": "`{bar}` **{pct}%** ({count} {votes})\n{voters}",
        "evento.field_init_name": "✅ {opt} (0 {votes})",
        "evento.footer": "Total de participantes: {total}",
        "evento.btn.cant": "No puedo asistir / Quitar voto",
        # --- /tribu (respuestas de comando) ---
        "tribu.fijar.done": "✅ Tribu fijada: **{nombre}** con los jugadores: {jugadores}.\nEl algoritmo no añadirá jugadores externos a este bloque.{tag}",
        "tribu.fijar.own_tag": "\n🌟 Ha sido marcada como TU TRIBU PROPIA.",
        "tribu.propia.crear_done": "✅ Se ha configurado **{nombre}** como tribu propia con los jugadores: {jugadores}.",
        "tribu.propia.none": "❌ No hay tribu propia configurada. Usa `/tribu propia crear` primero.",
        "tribu.propia.renamed": "✅ Se cambió el nombre de la tribu propia a **{valor}**.",
        "tribu.propia.already": "⚠️ **{valor}** ya está en la tribu propia (**{name}**).",
        "tribu.propia.added": "✅ Se añadió a **{valor}** a la tribu propia (**{name}**).",
        "tribu.propia.not_found": "❌ **{valor}** no fue encontrado en la tribu propia (**{name}**).",
        "tribu.propia.removed": "✅ Se eliminó a **{valor}** de la tribu propia (**{name}**).",
        "tribu.propia.need_sure": "❌ Debes seleccionar `seguro: True` para borrar la tribu propia definitivamente.",
        "tribu.propia.none_registered": "❌ No hay tribu propia registrada actualmente.",
        "tribu.propia.deleted": "✅ Has borrado permanentemente la tribu propia del servidor.",
        "tribu.desfijar.done": "✅ Tribu **{nombre}** ha sido eliminada de las fijadas. Sus miembros volverán a agruparse automáticamente.",
        "tribu.desfijar.not_found": "❌ No se encontró ninguna tribu fijada con el nombre **{nombre}**.",
        "tribu.limpiar.none": "✅ No se encontraron perfiles duplicados para fusionar.",
        "tribu.limpiar.done": "✅ Limpieza completada. Se han fusionado **{n}** perfiles duplicados con sus nombres base.",
        "tribu.merge.same": "❌ El origen y el destino no pueden ser el mismo.",
        "tribu.fusionar.title": "✅ IDENTIDADES FUSIONADAS",
        "tribu.fusionar.desc": "`{origen}`  ➡️  `{destino}`\n\n> 📊 **Horas transferidas:** `{horas}`\n> 🗺️ **Mapas afectados:** `{nmaps}` ({mapas})\n> 📅 **Registros movidos:** sesiones, relaciones, blacklist y alias del K4Ultra",
        "tribu.fusionar.footer": "El bot convertirá automáticamente las próximas conexiones del nombre antiguo.",
        "tribu.separar.no_session": "❌ El jugador **{origen}** NO tiene ninguna sesión activa en este momento. Este comando solo sirve para separar a un impostor mientras está conectado.",
        "tribu.separar.multi": "⚠️ **{origen}** tiene múltiples sesiones activas extrañas. Contacta al soporte técnico.",
        "tribu.separar.done": "✅ ¡Sesión separada!\nEl impostor que estaba usando **{origen}** ahora es rastreado como **{destino}**.\nLa sesión actual ya ha sido purgada del historial de **{origen}**.",
        "tribu.miembro.title": "✅ PERFIL DE TRIBU CONFIGURADO",
        "tribu.miembro.footer": "Vinculado al Rancómetro y al Radar K4Ultra  •  /ranking para ver tu posición",
        "tribu.miembro.no_profile": "❌ {user} no tiene ficha registrada en este servidor.",
        "tribu.miembro.borrar_done": "🗑️ Ficha de {user} eliminada:\n{items}",
        "tribu.miembro.removed.profile": "• Perfil de tribu (Discord ↔ personaje)",
        "tribu.miembro.removed.character": "• Personaje `{char}` desvinculado del ranking",
        "tribu.miembro.removed.alias": "• Alias del Radar K4Ultra",
        "tribu.miembro.removed.lang": "• Preferencia de idioma personal",
        "tribu.miembro.removed.own_tribe": "• `{steam}` retirado de la tribu propia (volverá a disparar alarmas)",
        "tribu.lista.title": "🏰 TRIBUS REGISTRADAS",
        "tribu.lista.empty": (
            "📭 No hay tribus registradas aún.\n\n"
            "💡 `/tribu propia crear` para la tuya · `/tribu aliada crear` para aliados · "
            "`/tribu fijar` para tribus conocidas."
        ),
        "tribu.lista.header": "⭐ `{own}` Propia  ·  🤝 `{allies}` Aliadas  ·  📌 `{pinned}` Fijadas  ·  👥 `{players}` Jugadores",
        "tribu.lista.section.own": "## ⭐ TRIBU PROPIA",
        "tribu.lista.section.allies": "## 🤝 ALIADAS",
        "tribu.lista.section.pinned": "## 📌 FIJADAS",
        "tribu.lista.footer": "⭐ no dispara alarmas · 🤝 no dispara alarmas · 📌 solo etiqueta en el radar",
        "tribu.aliada.no_players": "❌ Debes indicar al menos un jugador.",
        "tribu.aliada.created": "🤝 Tribu aliada **{nombre}** registrada con {n} jugador{s}: {jugadores}.\nEstos jugadores ya no dispararán alarmas de intrusos.",
        "tribu.aliada.not_exist": "❌ No existe la tribu aliada **{nombre}**. Usa `/tribu aliada lista` para ver las registradas.",
        "tribu.aliada.renamed": "✅ Tribu aliada renombrada de **{nombre}** a **{valor}**.",
        "tribu.aliada.already": "⚠️ **{valor}** ya está en la tribu aliada **{name}**.",
        "tribu.aliada.added": "✅ Se añadió a **{valor}** a la tribu aliada **{name}**.",
        "tribu.aliada.not_member": "❌ **{valor}** no está en la tribu aliada **{name}**.",
        "tribu.aliada.removed": "✅ Se eliminó a **{valor}** de la tribu aliada **{name}**.",
        "tribu.aliada.not_exist_short": "❌ No existe la tribu aliada **{nombre}**.",
        "tribu.aliada.deleted": "🗑️ Tribu aliada **{nombre}** eliminada. Sus jugadores volverán a disparar alarmas.",
        "tribu.aliada.list_title": "🤝 TRIBUS ALIADAS",
        "tribu.aliada.list_empty": "💤 No hay tribus aliadas registradas.\n\n💡 Un admin puede añadir una con `/tribu aliada crear nombre:X jugadores:a,b,c`.",
        "tribu.aliada.list_empty_footer": "Los jugadores de tribus aliadas no disparan alarmas de intrusos.",
        "tribu.aliada.list_header": "🤝 `{n:02d}` Tribus aliadas  ·  👥 `{players:02d}` Jugadores cubiertos",
        "tribu.aliada.list_section": "## 🤝 ALIADOS REGISTRADOS",
        "tribu.aliada.list_item": "`#{idx:02d}` 🤝 **{name}**  ·  👥 `{n}` jugador{s}",
        "tribu.aliada.list_empty_members": "*(vacía)*",
        "tribu.aliada.list_footer": "Los jugadores aquí listados NO dispararán alarmas al entrar en mapas vigilados.",
        # --- /admin ---
        "admin.config.updated": "✅ **Configuración actualizada correctamente.**",
        "admin.config.not_setup": "❌ Este servidor no está configurado. Usa `/inicio_ark` primero.",
        "admin.wipe.done": "✅ **BASE DE DATOS BORRADA.**\nTodos los registros han sido eliminados y los contadores reiniciados.",
        "admin.wipe.error": "❌ Error al borrar DB: {err}",
        "admin.clear.done": "✅ **DASHBOARDS LIMPIOS.** Si los mensajes viejos siguen existiendo en Discord, bórralos a mano.\nEl bot ya LOS HA OLVIDADO y no intentará editarlos más.",
        "admin.clear.error": "❌ Error al limpiar dashboards: {err}",
        "admin.log.empty": "No hay registros de comandos en esta sesión.",
        "admin.log.error": "Error leyendo logs: {err}",
        "admin.backup.done": "✅ Backup creado: `{file}` ({size} KB). Antiguos podados: {removed}.",
        "admin.backup.error": "❌ Error: `{err}`",
        "config.title": "⚙️ Configuración de ArkTribeBot",
        "config.subtitle": "Estado actual de la vinculación y parámetros del bot.",
        "config.footer": "ID Servidor: {guild_id}",
        "config.f.channels": "📡 Canales del Sistema",
        "config.channels_value": "🚨 **Alertas SOS:** <#{sos}>\n📜 **Lector Logs:** <#{log}>\n📁 **Repositorio:** <#{upload}>",
        "config.f.auth": "🛡️ Autorización",
        "config.auth_full": "👤 **Owner:** <@{owner}>\n🛡️ **Admin Role:** <@&{role}>",
        "config.auth_norole": "🛡️ **Admin Role:** No configurado",
        "config.f.modules": "📊 Módulos",
        "config.modules_value": "⏱️ **Actualización:** {interval} min\n🪙 **Puntos Diarios:** {status}",
        "config.f.tribe": "👨‍👩‍👧‍👦 Tribu",
        "config.tribe_value": "👥 **Miembros:** {n}",
        "config.no_servers_linked": "Sin servidores vinculados",
        "config.f.cluster": "🎮 Cluster (BattleMetrics)",
        # --- /puntos (puntos diarios) ---
        "puntos.cmd.hour_invalid": "❌ La hora debe estar entre 0 y 23.",
        "puntos.cmd.disabled_server": "🔕 El sistema de puntos diarios está **desactivado** en este servidor.",
        "puntos.cmd.enabled": "✅ **Notificaciones activadas.** Te avisaré todos los días a las **{hora:02d}:00** (Hora de {zona}) para votar.",
        "puntos.cmd.enable_error": "❌ Error al activar: {err}",
        "puntos.cmd.disabled": "🔕 **Notificaciones desactivadas.** Ya no te enviaré mensajes diarios.",
        "puntos.cmd.disable_error": "❌ Error al desactivar: {err}",
        "puntos.zone.es": "España",
        "puntos.zone.mx": "México",
        "puntos.config.sys_on": "✅ Sistema activado",
        "puntos.config.sys_off": "🔕 Sistema desactivado",
        "puntos.config.urls_updated": "🔗 **URLs de voto actualizadas:**\n{links}",
        "puntos.config.status": "**Estado actual del sistema de Puntos Diarios:**\n• Sistema: {enabled}\n• URLs de voto:\n{urls}",
        "puntos.config.active": "✅ Activo",
        "puntos.config.inactive": "🔕 Desactivado",
        "puntos.config.updated": "✅ **Config actualizada:**\n{changes}",
        # --- /alarma (respuestas de comando) ---
        "alarm.cmd.map_not_found": "❌ El mapa `{map}` no existe en la configuración actual.",
        "alarm.cmd.off": "🔕 Alarma para **{map}** desactivada.",
        "alarm.cmd.on": (
            "🚨 **Alarma activada** para `{map}`. Te avisaré por **mensaje privado (DM)** "
            "cuando entre un intruso. 🔔\n⚠️ Asegúrate de tener los DMs abiertos para este servidor."
        ),
        "alarm.cmd.error": "❌ Ocurrió un error al procesar la alarma: {err}",
        "alarm.dm.header": "⚠️ **Alerta de intrusos** en `{map}`",
        "alarm.dm.entry": "• **{name}**  ·  ⏱️ `{time}`",
        "alarm.dm.footer": "-# Este mensaje se actualiza si entran más intrusos · Pulsa Silenciar para descartarlo",
        # --- To-Do dashboard ---
        "todo.title": "📋 LISTA DE TAREAS",
        "todo.empty": (
            "✅ ¡Sin tareas pendientes! La tribu está al día. 🎉\n\n"
            "*Pulsa **Añadir Tarea** o usa `/todo add` para crear una nueva.*"
        ),
        "todo.empty_footer": "Página 1/1 • 0 tareas",
        "todo.badges": "🔨 `{progress:02d}` En Progreso  ·  ⏳ `{pending:02d}` Pendientes  ·  📊 `{total:02d}` Total",
        "todo.section.progress": "## 🔨 EN PROGRESO",
        "todo.section.pending": "## ⏳ PENDIENTES",
        "todo.unassigned": "*Sin asignar*",
        "todo.footer": "Página {page}/{pages} • {total} tareas totales • /todo add para añadir",
        "todo.btn.add": "Añadir Tarea",
        "todo.btn.claim": "Reclamar Tarea",
        "todo.btn.delete": "Eliminar Tarea",
        "todo.cmd.added": "✅ Tarea añadida: **{tarea}**",
        # --- Blacklist dashboard ---
        "blacklist.title": "☠️ BLACKLIST DE TRIBU",
        "blacklist.empty": (
            "La lista está limpia. No hay jugadores registrados.\n"
            "💡 Usa el botón **Añadir** para registrar el primero."
        ),
        "blacklist.badges": "🔴 `{enemies}` Enemigos  ·  ⚪ `{neutrals}` Neutrales  ·  📊 `{total}` Total",
        "blacklist.section.enemies": "## 🔴 ENEMIGOS (KOS)",
        "blacklist.section.neutrals": "## ⚪ REGISTROS (NEUTRALES)",
        "blacklist.footer": "Página {page}/{pages} • {total} entradas totales • /blacklist editar para modificar",
        "blacklist.btn.add": "Añadir",
        "blacklist.btn.modify": "Modificar",
        "blacklist.btn.delete": "Eliminar",
        "bl.editar.added": "📥 **Añadido** a la Blacklist (no existía)",
        "bl.editar.field.tribe": "🏠 **Tribu** → {v}",
        "bl.editar.field.map": "🗺️ **Mapa** → {v}",
        "bl.editar.field.char": "🧑 **Personaje** → {v}",
        "bl.editar.field.notes": "📝 **Notas** → {v}",
        "bl.editar.field.enemy": "⚔️ **Enemigo** → {v}",
        "bl.editar.yes": "Sí",
        "bl.editar.no": "No",
        "bl.editar.no_changes": "⚠️ No has proporcionado ningún campo para actualizar.",
        "bl.editar.updated": "✅ **{jugador}** actualizado:\n{changes}",
        # --- Ficha de jugador (build_player_detail_embed) ---
        "pd.title": "👤 Expediente: {name}",
        "pd.title_alias": "👤 Expediente: {name} [{alias}]",
        "pd.old_names": "⚠️ **Antiguos nombres de Steam:** `{names}`\n*(Progreso fusionado automáticamente a este perfil)*",
        "pd.status.passive": "⚪ Registro Pasivo (K4Ultra)",
        "pd.status.member": "🟢 Miembro de la Tribu",
        "pd.status.enemy": "🔴 Marcado en Blacklist (Enemigo)",
        "pd.status.neutral": "⚪ Marcado en Blacklist (Neutral)",
        "pd.notes_none": "Ninguna",
        "pd.field.tribe": "🏠 Tribu",
        "pd.tribe_unknown": "Desconocida",
        "pd.field.origin_map": "🗺️ Mapa Origen",
        "pd.map_unknown": "Desconocido",
        "pd.field.notes": "📝 Notas",
        "pd.not_in_blacklist": "Este jugador no está en la blacklist manual.",
        "pd.online": "🟢 **En línea** (en {map} desde {since})",
        "pd.offline_seen": "🔴 **Desconectado** (Visto en {map})",
        "pd.offline": "🔴 **Desconectado**",
        "pd.field.status": "🔌 Estado Actual",
        "pd.field.total_time": "⏱️ Tiempo Total",
        "pd.hours": "{h} horas",
        "pd.field.orbit": "🛰️ Órbita (Últimos Mapas)",
        "pd.vuln.undetermined": "Indeterminada",
        "pd.vuln.dawn": "Madrugada / Variable",
        "pd.vuln.between": "Entre {a}:00 y {b}:00",
        "pd.field.vuln": "🕒 Ventana Vulnerable",
        "pd.field.prob": "📈 Prob. Conexión (1h)",
        "pd.chars_none": "Ninguno",
        "pd.field.deaths": "⚔️ Ficha de Muertes",
        "pd.deaths_value": "**Deaths Totales (Rancómetro):** {deaths}",
        "pd.field.alts": "🧑‍🤝‍🧑 Alts / Personajes",
        "pd.field.threat": "🔥 Grado de Peligro",
        "pd.field.record_type": "📑 Tipo de Registro",
        "pd.allies_none": "Sin aliados conocidos.",
        "pd.field.allies": "🤝 Aliados Cercanos",
        # --- KDA / Ranking de muertes dashboard ---
        "kda.title": "☠️ EL SALÓN DE LA INFAMIA",
        "kda.empty_title": "☠️ El Salón de la Infamia",
        "kda.empty_desc": "Todavía no hay registros de mortalidad en la tribu. ¡Seguid así! 🛡️",
        "kda.empty_footer": "💡 Los perfiles se vinculan con /tribu miembro crear",
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
            "💡 Selecciona un mapa en el menú inferior o usa `/alarma activar mapa:X estado:on` para activar la tuya."
        ),
        "alarm.empty_footer": "El bot te avisa por DM cuando entra un jugador desconocido al mapa vigilado.",
        "alarm.badges": "🗺️ `{maps:02d}` Mapas vigilados  ·  👥 `{unique:02d}` Vigilantes únicos  ·  📊 `{subs:02d}` Suscripciones",
        "alarm.section": "## 🟢 MAPAS BAJO VIGILANCIA",
        "alarm.map_line": "`#{idx:02d}` 🟢 **{map}**  ·  👥 `{count}` {word}",
        "alarm.watcher_one": "vigilante",
        "alarm.watcher_many": "vigilantes",
        "alarm.footer": "Selecciona un mapa en el menú inferior para activar/desactivar tu alarma  •  /alarma activar para comando directo",
        "alarm.select_placeholder": "Selecciona un mapa del clúster...",
        "alarm.btn.refresh": "Refrescar",
        # --- K4Ultra dashboard (radar) ---
        "k4.cmd.no_snapshot": "❌ No se encontró un snapshot para la semana {semana}.",
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
        "status.footer": "Auto-actualizado cada 2 minutos  •  /status mapa para ver un mapa concreto",
        "status.cmd.not_configured": "❌ Servidor no configurado. Usa `/inicio_ark` para añadir tus servidores.",
        "status.cmd.gen_error": "❌ Error al generar el estado inicial.",
        # --- /help (manual interactivo) ---
        "help.title": "📚 MANUAL DE USUARIO — ARKTRIBEBOT",
        "help.intro": (
            "Selecciona una sección del menú inferior para conocer los comandos y "
            "funcionamiento de cada módulo.\n\n"
            "## 🚀 Empezar\n"
            "> 💡 **Nuevo miembro:** usa `/tribu miembro crear` para registrarte (necesario para "
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
        "common.min_2_players": "❌ You must specify at least 2 valid players separated by commas.",
        "common.loading": "⏳ Loading...",
        # --- /evento (LFG poll) ---
        "evento.min_options": "You must provide at least 2 valid date/time options for the poll.",
        "evento.deleted": "The event no longer exists in the database.",
        "evento.title": "📅 Event: {titulo}",
        "evento.author": "Organized by {name}",
        "evento.unknown_creator": "Unknown",
        "evento.nobody": "*Nobody yet*",
        "evento.votes": "votes",
        "evento.field_value": "`{bar}` **{pct}%** ({count} {votes})\n{voters}",
        "evento.field_init_name": "✅ {opt} (0 {votes})",
        "evento.footer": "Total participants: {total}",
        "evento.btn.cant": "Can't attend / Remove vote",
        # --- /tribu (command replies) ---
        "tribu.fijar.done": "✅ Tribe pinned: **{nombre}** with players: {jugadores}.\nThe algorithm won't add external players to this block.{tag}",
        "tribu.fijar.own_tag": "\n🌟 It has been marked as YOUR OWN TRIBE.",
        "tribu.propia.crear_done": "✅ **{nombre}** set as your own tribe with players: {jugadores}.",
        "tribu.propia.none": "❌ No own tribe configured. Use `/tribu propia crear` first.",
        "tribu.propia.renamed": "✅ Own tribe renamed to **{valor}**.",
        "tribu.propia.already": "⚠️ **{valor}** is already in your own tribe (**{name}**).",
        "tribu.propia.added": "✅ Added **{valor}** to your own tribe (**{name}**).",
        "tribu.propia.not_found": "❌ **{valor}** was not found in your own tribe (**{name}**).",
        "tribu.propia.removed": "✅ Removed **{valor}** from your own tribe (**{name}**).",
        "tribu.propia.need_sure": "❌ You must select `seguro: True` to permanently delete your own tribe.",
        "tribu.propia.none_registered": "❌ No own tribe currently registered.",
        "tribu.propia.deleted": "✅ You've permanently deleted the server's own tribe.",
        "tribu.desfijar.done": "✅ Tribe **{nombre}** has been removed from pinned. Its members will auto-group again.",
        "tribu.desfijar.not_found": "❌ No pinned tribe found with the name **{nombre}**.",
        "tribu.limpiar.none": "✅ No duplicate profiles found to merge.",
        "tribu.limpiar.done": "✅ Cleanup complete. Merged **{n}** duplicate profiles with their base names.",
        "tribu.merge.same": "❌ Source and destination can't be the same.",
        "tribu.fusionar.title": "✅ IDENTITIES MERGED",
        "tribu.fusionar.desc": "`{origen}`  ➡️  `{destino}`\n\n> 📊 **Hours transferred:** `{horas}`\n> 🗺️ **Maps affected:** `{nmaps}` ({mapas})\n> 📅 **Records moved:** sessions, relationships, blacklist and K4Ultra aliases",
        "tribu.fusionar.footer": "The bot will automatically convert the old name's future connections.",
        "tribu.separar.no_session": "❌ Player **{origen}** has NO active session right now. This command only works to split an impostor while connected.",
        "tribu.separar.multi": "⚠️ **{origen}** has multiple strange active sessions. Contact technical support.",
        "tribu.separar.done": "✅ Session split!\nThe impostor who was using **{origen}** is now tracked as **{destino}**.\nThe current session has been purged from **{origen}**'s history.",
        "tribu.miembro.title": "✅ TRIBE PROFILE CONFIGURED",
        "tribu.miembro.footer": "Linked to the Noob-o-meter and the K4Ultra Radar  •  /ranking to see your position",
        "tribu.miembro.no_profile": "❌ {user} has no profile registered on this server.",
        "tribu.miembro.borrar_done": "🗑️ Profile of {user} deleted:\n{items}",
        "tribu.miembro.removed.profile": "• Tribe profile (Discord ↔ character)",
        "tribu.miembro.removed.character": "• Character `{char}` unlinked from the ranking",
        "tribu.miembro.removed.alias": "• K4Ultra Radar alias",
        "tribu.miembro.removed.lang": "• Personal language preference",
        "tribu.miembro.removed.own_tribe": "• `{steam}` removed from your own tribe (will trigger alarms again)",
        "tribu.lista.title": "🏰 REGISTERED TRIBES",
        "tribu.lista.empty": (
            "📭 No tribes registered yet.\n\n"
            "💡 `/tribu propia crear` for yours · `/tribu aliada crear` for allies · "
            "`/tribu fijar` for known tribes."
        ),
        "tribu.lista.header": "⭐ `{own}` Own  ·  🤝 `{allies}` Allied  ·  📌 `{pinned}` Pinned  ·  👥 `{players}` Players",
        "tribu.lista.section.own": "## ⭐ OWN TRIBE",
        "tribu.lista.section.allies": "## 🤝 ALLIED",
        "tribu.lista.section.pinned": "## 📌 PINNED",
        "tribu.lista.footer": "⭐ no alarms · 🤝 no alarms · 📌 radar label only",
        "tribu.aliada.no_players": "❌ You must specify at least one player.",
        "tribu.aliada.created": "🤝 Allied tribe **{nombre}** registered with {n} player{s}: {jugadores}.\nThese players will no longer trigger intruder alarms.",
        "tribu.aliada.not_exist": "❌ Allied tribe **{nombre}** doesn't exist. Use `/tribu aliada lista` to see the registered ones.",
        "tribu.aliada.renamed": "✅ Allied tribe renamed from **{nombre}** to **{valor}**.",
        "tribu.aliada.already": "⚠️ **{valor}** is already in allied tribe **{name}**.",
        "tribu.aliada.added": "✅ Added **{valor}** to allied tribe **{name}**.",
        "tribu.aliada.not_member": "❌ **{valor}** is not in allied tribe **{name}**.",
        "tribu.aliada.removed": "✅ Removed **{valor}** from allied tribe **{name}**.",
        "tribu.aliada.not_exist_short": "❌ Allied tribe **{nombre}** doesn't exist.",
        "tribu.aliada.deleted": "🗑️ Allied tribe **{nombre}** deleted. Its players will trigger alarms again.",
        "tribu.aliada.list_title": "🤝 ALLIED TRIBES",
        "tribu.aliada.list_empty": "💤 No allied tribes registered.\n\n💡 An admin can add one with `/tribu aliada crear nombre:X jugadores:a,b,c`.",
        "tribu.aliada.list_empty_footer": "Players from allied tribes don't trigger intruder alarms.",
        "tribu.aliada.list_header": "🤝 `{n:02d}` Allied tribes  ·  👥 `{players:02d}` Covered players",
        "tribu.aliada.list_section": "## 🤝 REGISTERED ALLIES",
        "tribu.aliada.list_item": "`#{idx:02d}` 🤝 **{name}**  ·  👥 `{n}` player{s}",
        "tribu.aliada.list_empty_members": "*(empty)*",
        "tribu.aliada.list_footer": "The players listed here will NOT trigger alarms when entering watched maps.",
        # --- /admin ---
        "admin.config.updated": "✅ **Configuration updated successfully.**",
        "admin.config.not_setup": "❌ This server is not configured. Use `/inicio_ark` first.",
        "admin.wipe.done": "✅ **DATABASE WIPED.**\nAll records have been deleted and counters reset.",
        "admin.wipe.error": "❌ Error wiping DB: {err}",
        "admin.clear.done": "✅ **DASHBOARDS CLEARED.** If the old messages still exist in Discord, delete them by hand.\nThe bot has FORGOTTEN them and won't try to edit them anymore.",
        "admin.clear.error": "❌ Error clearing dashboards: {err}",
        "admin.log.empty": "No command records in this session.",
        "admin.log.error": "Error reading logs: {err}",
        "admin.backup.done": "✅ Backup created: `{file}` ({size} KB). Old ones pruned: {removed}.",
        "admin.backup.error": "❌ Error: `{err}`",
        "config.title": "⚙️ ArkTribeBot Configuration",
        "config.subtitle": "Current binding status and bot parameters.",
        "config.footer": "Server ID: {guild_id}",
        "config.f.channels": "📡 System Channels",
        "config.channels_value": "🚨 **SOS Alerts:** <#{sos}>\n📜 **Log Reader:** <#{log}>\n📁 **Repository:** <#{upload}>",
        "config.f.auth": "🛡️ Authorization",
        "config.auth_full": "👤 **Owner:** <@{owner}>\n🛡️ **Admin Role:** <@&{role}>",
        "config.auth_norole": "🛡️ **Admin Role:** Not configured",
        "config.f.modules": "📊 Modules",
        "config.modules_value": "⏱️ **Update:** {interval} min\n🪙 **Daily Points:** {status}",
        "config.f.tribe": "👨‍👩‍👧‍👦 Tribe",
        "config.tribe_value": "👥 **Members:** {n}",
        "config.no_servers_linked": "No servers linked",
        "config.f.cluster": "🎮 Cluster (BattleMetrics)",
        # --- /puntos (daily points) ---
        "puntos.cmd.hour_invalid": "❌ The hour must be between 0 and 23.",
        "puntos.cmd.disabled_server": "🔕 The daily points system is **disabled** on this server.",
        "puntos.cmd.enabled": "✅ **Notifications enabled.** I'll remind you every day at **{hora:02d}:00** ({zona} time) to vote.",
        "puntos.cmd.enable_error": "❌ Error enabling: {err}",
        "puntos.cmd.disabled": "🔕 **Notifications disabled.** I'll no longer send you daily messages.",
        "puntos.cmd.disable_error": "❌ Error disabling: {err}",
        "puntos.zone.es": "Spain",
        "puntos.zone.mx": "Mexico",
        "puntos.config.sys_on": "✅ System enabled",
        "puntos.config.sys_off": "🔕 System disabled",
        "puntos.config.urls_updated": "🔗 **Vote URLs updated:**\n{links}",
        "puntos.config.status": "**Current Daily Points status:**\n• System: {enabled}\n• Vote URLs:\n{urls}",
        "puntos.config.active": "✅ Active",
        "puntos.config.inactive": "🔕 Disabled",
        "puntos.config.updated": "✅ **Config updated:**\n{changes}",
        # --- /alarma (command replies) ---
        "alarm.cmd.map_not_found": "❌ The map `{map}` does not exist in the current config.",
        "alarm.cmd.off": "🔕 Alarm for **{map}** disabled.",
        "alarm.cmd.on": (
            "🚨 **Alarm enabled** for `{map}`. I'll warn you via **direct message (DM)** "
            "when an intruder shows up. 🔔\n⚠️ Make sure your DMs are open for this server."
        ),
        "alarm.cmd.error": "❌ An error occurred while processing the alarm: {err}",
        "alarm.dm.header": "⚠️ **Intruder alert** on `{map}`",
        "alarm.dm.entry": "• **{name}**  ·  ⏱️ `{time}`",
        "alarm.dm.footer": "-# This message updates if more intruders enter · Press Silence to dismiss it",
        # --- To-Do dashboard ---
        "todo.title": "📋 TASK LIST",
        "todo.empty": (
            "✅ No pending tasks! The tribe is all caught up. 🎉\n\n"
            "*Press **Add Task** or use `/todo add` to create a new one.*"
        ),
        "todo.empty_footer": "Page 1/1 • 0 tasks",
        "todo.badges": "🔨 `{progress:02d}` In Progress  ·  ⏳ `{pending:02d}` Pending  ·  📊 `{total:02d}` Total",
        "todo.section.progress": "## 🔨 IN PROGRESS",
        "todo.section.pending": "## ⏳ PENDING",
        "todo.unassigned": "*Unassigned*",
        "todo.footer": "Page {page}/{pages} • {total} tasks total • /todo add to add",
        "todo.btn.add": "Add Task",
        "todo.btn.claim": "Claim Task",
        "todo.btn.delete": "Delete Task",
        "todo.cmd.added": "✅ Task added: **{tarea}**",
        # --- Blacklist dashboard ---
        "blacklist.title": "☠️ TRIBE BLACKLIST",
        "blacklist.empty": (
            "The list is clean. No players registered.\n"
            "💡 Use the **Add** button to register the first one."
        ),
        "blacklist.badges": "🔴 `{enemies}` Enemies  ·  ⚪ `{neutrals}` Neutrals  ·  📊 `{total}` Total",
        "blacklist.section.enemies": "## 🔴 ENEMIES (KOS)",
        "blacklist.section.neutrals": "## ⚪ RECORDS (NEUTRALS)",
        "blacklist.footer": "Page {page}/{pages} • {total} total entries • /blacklist editar to edit",
        "blacklist.btn.add": "Add",
        "blacklist.btn.modify": "Edit",
        "blacklist.btn.delete": "Delete",
        "bl.editar.added": "📥 **Added** to the Blacklist (didn't exist)",
        "bl.editar.field.tribe": "🏠 **Tribe** → {v}",
        "bl.editar.field.map": "🗺️ **Map** → {v}",
        "bl.editar.field.char": "🧑 **Character** → {v}",
        "bl.editar.field.notes": "📝 **Notes** → {v}",
        "bl.editar.field.enemy": "⚔️ **Enemy** → {v}",
        "bl.editar.yes": "Yes",
        "bl.editar.no": "No",
        "bl.editar.no_changes": "⚠️ You didn't provide any field to update.",
        "bl.editar.updated": "✅ **{jugador}** updated:\n{changes}",
        # --- Player dossier (build_player_detail_embed) ---
        "pd.title": "👤 Dossier: {name}",
        "pd.title_alias": "👤 Dossier: {name} [{alias}]",
        "pd.old_names": "⚠️ **Old Steam names:** `{names}`\n*(Progress automatically merged into this profile)*",
        "pd.status.passive": "⚪ Passive Record (K4Ultra)",
        "pd.status.member": "🟢 Tribe Member",
        "pd.status.enemy": "🔴 Marked in Blacklist (Enemy)",
        "pd.status.neutral": "⚪ Marked in Blacklist (Neutral)",
        "pd.notes_none": "None",
        "pd.field.tribe": "🏠 Tribe",
        "pd.tribe_unknown": "Unknown",
        "pd.field.origin_map": "🗺️ Origin Map",
        "pd.map_unknown": "Unknown",
        "pd.field.notes": "📝 Notes",
        "pd.not_in_blacklist": "This player is not in the manual blacklist.",
        "pd.online": "🟢 **Online** (on {map} since {since})",
        "pd.offline_seen": "🔴 **Offline** (Seen on {map})",
        "pd.offline": "🔴 **Offline**",
        "pd.field.status": "🔌 Current Status",
        "pd.field.total_time": "⏱️ Total Time",
        "pd.hours": "{h} hours",
        "pd.field.orbit": "🛰️ Orbit (Recent Maps)",
        "pd.vuln.undetermined": "Undetermined",
        "pd.vuln.dawn": "Late night / Variable",
        "pd.vuln.between": "Between {a}:00 and {b}:00",
        "pd.field.vuln": "🕒 Vulnerable Window",
        "pd.field.prob": "📈 Connection Prob. (1h)",
        "pd.chars_none": "None",
        "pd.field.deaths": "⚔️ Death Sheet",
        "pd.deaths_value": "**Total Deaths (Noob-o-meter):** {deaths}",
        "pd.field.alts": "🧑‍🤝‍🧑 Alts / Characters",
        "pd.field.threat": "🔥 Danger Level",
        "pd.field.record_type": "📑 Record Type",
        "pd.allies_none": "No known allies.",
        "pd.field.allies": "🤝 Close Allies",
        # --- KDA / Death ranking dashboard ---
        "kda.title": "☠️ THE HALL OF INFAMY",
        "kda.empty_title": "☠️ The Hall of Infamy",
        "kda.empty_desc": "No mortality records in the tribe yet. Keep it up! 🛡️",
        "kda.empty_footer": "💡 Profiles are linked with /tribu miembro crear",
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
            "💡 Pick a map in the menu below or use `/alarma activar mapa:X estado:on` to enable yours."
        ),
        "alarm.empty_footer": "The bot DMs you when an unknown player enters a watched map.",
        "alarm.badges": "🗺️ `{maps:02d}` Watched maps  ·  👥 `{unique:02d}` Unique watchers  ·  📊 `{subs:02d}` Subscriptions",
        "alarm.section": "## 🟢 MAPS UNDER WATCH",
        "alarm.map_line": "`#{idx:02d}` 🟢 **{map}**  ·  👥 `{count}` {word}",
        "alarm.watcher_one": "watcher",
        "alarm.watcher_many": "watchers",
        "alarm.footer": "Pick a map in the menu below to toggle your alarm  •  /alarma activar for the direct command",
        "alarm.select_placeholder": "Pick a cluster map...",
        "alarm.btn.refresh": "Refresh",
        # --- K4Ultra dashboard (radar) ---
        "k4.cmd.no_snapshot": "❌ No snapshot found for week {semana}.",
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
        "status.footer": "Auto-updated every 2 minutes  •  /status mapa to view a specific map",
        "status.cmd.not_configured": "❌ Server not configured. Use `/inicio_ark` to add your servers.",
        "status.cmd.gen_error": "❌ Error generating the initial status.",
        # --- /help (interactive manual) ---
        "help.title": "📚 USER MANUAL — ARKTRIBEBOT",
        "help.intro": (
            "Pick a section from the menu below to learn the commands and how each "
            "module works.\n\n"
            "## 🚀 Getting started\n"
            "> 💡 **New member:** use `/tribu miembro crear` to register (required for the "
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
