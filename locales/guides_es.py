"""Guías largas de /info y /help en español.

Movido aquí desde cogs/management.py para separar la prosa de la lógica y
permitir mantener la versión en inglés (``guides_en.INFO_TEXTS_EN``) en paralelo.

Las claves coinciden con los ``value`` de las Choice de /info y las SelectOption
de /help. Si añades un módulo, añade su clave en AMBOS diccionarios (es/en).
"""

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
- **/todo add**: Añade una nueva tarea a la lista "Pendiente".
  - *Uso:* `/todo add tarea:"Farmear 50k de metal en Aberration"`
- **/todo panel**: Genera/renueva el panel interactivo de tareas (auto-actualizable).

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
- **/linea add**: Registra un nuevo dino o actualiza una stat si la tuya es superior.
  - *Uso:* `/linea add dino:Rex estadistica:HP puntos:50`
- **/linea mod**: Modifica una estadística específica (por si te equivocaste o entró muta).
- **/linea ver**: Consulta privada de todas las stats de una especie (mensaje oculto).
- **/linea panel**: Renueva el Dashboard principal con todas las estadísticas y botones en vivo.
- **/linea log**: Muestra las últimas 20 mutaciones registradas en el servidor.

### :bar_chart: Stats Disponibles
HP · Estamina · Peso · Melee · Oxígeno · Comida · Velocidad · Mutaciones (contador puro).

### :mouse_three_button: Botones del Dashboard
1. :arrow_backward: :arrow_forward: **Paginación**: 10 especies por página, persistente entre reinicios.
2. **Nueva Muta**: Suma +2 a una stat de un dino y lo registra en el log de mutaciones automáticamente.
3. **Alarmas**: Programa temporizadores de impronta/crecimiento. Opciones: **1.5h · 2.5h · 4h · 10h**. Te avisa por mención en el canal cuando expire.
4. **Ver Logs Muta**: Equivalente al comando `/linea log` pero accesible con un click.
5. **Selector Individual**: Menú desplegable inferior para aislar a un dino concreto y ver su ficha detallada en privado.""",
    "blacklist": """# :skull_crossbones: Blacklist

Jugadores "Kill on Sight" (KOS). Si están aquí, son enemigos confirmados; cuanta más info mejor.

### :no_entry_sign: Sistema de Blacklist
- **/blacklist panel**: Genera y ancla el Dashboard interactivo de la Lista Negra (auto-actualizable).
- **/blacklist editar**: Atajo directo al modal de edición sin pasar por el panel (útil para cambios rápidos).

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
- **/scout add**: Registra una base enemiga con todos los detalles (acepta imagen como enlace).
  - *Campos:* `tribu`, `mapa`, `coords`, `amenaza` (1-5 :star:, validado), `imagen`, `notas`.
- **/scout imagen**: Adjunta una imagen desde tu PC a un scout ya existente.
  - *Uso:* `/scout imagen id:12 imagen:[adjuntar archivo]`.
- **/scout lista**: Consulta **PRIVADA** paginada (todas las bases, o solo las de un mapa con `mapa:`).
- **/scout panel**: Crea/renueva el Dashboard **PÚBLICO** auto-actualizable.
- **/scout borrar**: Elimina un reporte obsoleto por ID.

### :mouse_three_button: Botones y Menú del Panel
- **Añadir Scout**: formulario sin imagen (para agregarla luego con `/scout imagen`).
- **Modificar / Eliminar Scout**: por ID.
- :arrow_backward: :arrow_forward: **Paginación** entre mapas.
- :pushpin: **Selector inferior**: clic en un scout listado y ves su ficha **completa con imagen** en mensaje privado.

> :bulb: Niveles de amenaza válidos: del **1 (baja)** al **5 (extrema)**. Cualquier otro valor lo rechaza.""",
    "status": """# :green_circle: Estado de los Servidores

Monitoriza en tiempo real si los servidores están online, quién está conectado y qué ping tienen.

### :computer: Comandos
- **/status mapa**: Consulta puntual de un servidor (autocompleta con tus mapas).
- **/status cluster**: Vista resumida de **todo el cluster** en un único embed.
- **/status fijar mapa:Gen2**: Ancla un mensaje que se auto-actualiza cada 2 min indefinidamente.

### :arrows_counterclockwise: Auto-Update y Colores
Los paneles persistentes refrescan automáticamente y cambian de aspecto según el estado:
- :green_circle: **Verde** — servidor online con jugadores dentro (los lista).
- :yellow_circle: **Amarillo** — servidor online pero vacío.
- :red_circle: **Rojo** — servidor caído (timeout / sin respuesta A2S).

### :stopwatch: Detalle Técnico
Las consultas A2S se centralizan con un caché compartido de 90 s, lo que permite que **Status**, **K4Ultra** y **Alarmas** reutilicen el mismo sondeo sin bombardear los servidores.

### :bell: Alarmas de Intrusos (resumen)
- **/alarma activar mapa:Fjordur estado:on** activa la vigilancia de un mapa; **off** la desactiva.
- **/alarma panel** abre el panel rápido con todas tus alarmas configurables.
- El bot te avisa por **DM** cuando entra al mapa un jugador que NO es de tu tribu propia ni de los personajes registrados. Cada alerta lleva un botón **✅ Silenciar** para descartarla.

> :bulb: Más detalle en `/info modulo:🔔 Alarmas de Intrusos`.""",
    "k4ultra": """# :eye: Tracker de Inteligencia (K4Ultra)

K4Ultra monitoriza de forma pasiva el cluster para calcular el comportamiento, sesiones y alianzas enemigas a partir del protocolo A2S (sin tocar Battlemetrics).

### :satellite: Modos de Visualización
- **/k4ultra**: Levanta el panel principal (modo Radar por defecto).
  - **Radar / Ranking**: jugadores online + top de horas jugadas (paginado :arrow_backward: :arrow_forward:).
  - **Tribus / Relaciones**: grafo de alianzas predictivo. Cada par de jugadores acumula puntos por minutos compartidos en el mismo mapa, logins/logouts sincronizados y transferencias simultáneas. Decae **5% al día** si dejan de coincidir.

### :crown: Identificación de tu propia tribu
- **/tribu propia crear nombre:"MiTribu" jugadores:"a, b, c"** — marca tu base.
- **/tribu propia modificar opcion:... valor:...** — añade/quita miembros o renombra.
- **/tribu propia borrar seguro:True** — limpia el registro.
- **/tribu fijar / /tribu desfijar** — para marcar **otras** tribus conocidas (enemigos confirmados, aliados, etc.) y que aparezcan etiquetadas en el modo Tribus.

### :busts_in_silhouette: Gestión de Identidades
Imprescindible para que el ranking y la blacklist no se llenen de duplicados:
- **/tribu miembro crear usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registra un miembro completo en una sola llamada.
- **/tribu miembro borrar usuario:@x** — elimina la ficha completa de alguien que dejó la tribu (perfil, personaje, alias, idioma; lo saca de la tribu propia).
- **/tribu lista** — vista de TODAS las tribus registradas: ⭐ propia, 🤝 aliadas y 📌 fijadas con sus jugadores.
- **/tribu fusionar origen:NombreViejo destino:NombreNuevo** — todo lo que el bot registró bajo el nombre antiguo (horas, mapas, sesiones, relaciones, blacklist) se reasigna al nuevo de forma perpetua.
- **/tribu separar origen:... destino:...** — separa la sesión actual de un perfil que el bot agrupó por error.
- **/tribu limpiar** — [Admin] limpieza masiva: une todos los `nombre_1`/`_2` con su base.

### :mouse_three_button: Botones del Panel
- **➕ Añadir Relación / ➖ Eliminar Relación**: declarar/desdeclarar alianzas manuales (no decaen).
- **✏️ Renombrar Tribu**: asigna un alias persistente a una tribu detectada (ej. "Cluster A" → "Los Alfas").
- **Selector de Jugador**: clic en un jugador → expediente completo (perfil unificado con KDA + horas + mapas) en privado.""",
    "ranking": """# :skull_crossbones: EL SALÓN DE LA INFAMIA (Rancómetro)

El bot usa un **Log Processor** que escucha 24/7 el canal de Logs del servidor y parsea cada muerte.

### :chart_with_downwards_trend: Funcionamiento
- **Detección automática:** cada `fue 🔪` o `was :knife:` en los logs incrementa el contador de muertes del personaje. Las kills se ignoran a propósito (solo contamos muertes).
- **Anti-fuego-amigo:** si el asesino también es miembro registrado de tu tribu (vía `/tribu miembro crear`), la muerte NO suma — solo se queda en el log con un aviso de "fuego amigo".
- **Sarcasmos:** el bot responde a cada muerte con una frase aleatoria + emoji aleatorio (💀🤡🪦🥚🍗🧻🗑️).
- **Hitos especiales:** las muertes números **1, 10, 50, 69, 100, 300, 420, 666, 777, 1000** y todos los múltiplos de 100 disparan mensajes con GIF dedicado. Vete acumulando.

### :busts_in_silhouette: Configuración Obligatoria
Para que el sistema pueda atribuir muertes:
- **/tribu miembro crear usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registra a un miembro.
- **/ranking** — Dashboard del Death Counter ordenado por bajas.

### :sunrise: Recordatorios de Votos
El módulo de **Puntos Diarios** (`/info modulo:🌅 Puntos Diarios`) es opcional y complementario — te avisa por DM cada día para que canjees los votos del cluster.""",
    "alarmas": """# :bell: Alarmas de Intrusos por Mapa

Sistema de defensa pasiva: el bot vigila los mapas que elijas y te avisa por **mensaje privado (DM)** cuando entra un jugador que NO esté en tu tribu propia, en una tribu aliada, ni registrado como personaje conocido.

### :gear: Comandos
- **/alarma activar mapa:Fjordur estado:on** — Activa la vigilancia de un mapa.
- **/alarma activar mapa:Fjordur estado:off** — La desactiva.
- **/alarma panel** — Abre el **panel interactivo** con todas las alarmas configurables del cluster (más cómodo que el comando suelto).
- **/tribu aliada crear / modificar / borrar / lista** *(admin)* — Registra tribus aliadas para que sus jugadores no disparen alarmas.

### :brain: Cómo decide si alguien es intruso
Cada minuto el bot lee el caché de Status (no genera tráfico extra) y compara contra el último snapshot del mapa. Para cada jugador NUEVO:
1. Si está en tu tribu propia (`/tribu propia`) → ignora.
2. Si está en una tribu aliada (`/tribu aliada`) → ignora.
3. Si está registrado como personaje conocido (`/tribu miembro crear`) → ignora.
4. Si no → :rotating_light: **alarma**: el bot te envía un **DM** con la lista de intrusos y la hora de entrada de cada uno.

### :pushpin: Detalle
- Las alarmas son **por usuario** y por mapa: cada miembro puede tener su propia lista.
- Multi-mapa: puedes vigilar varios mapas a la vez sin coste extra.
- **Anti-spam:** si entran más intrusos mientras tu alerta sigue reciente (1h), el bot **edita el mismo mensaje** añadiéndolos a la lista en vez de enviarte uno nuevo. Pasada la ventana, borra el viejo y envía uno fresco (para que te llegue la notificación).
- El mensaje de alarma incluye un botón **✅ Silenciar** para descartarlo.
- Si tienes los DMs cerrados para este servidor, el bot no podrá avisarte (queda anotado en el log).""",
    "puntos_diarios": """# :sunrise: Puntos Diarios de Voto

Recordatorio personal por DM para que canjees los puntos diarios votando tu cluster en los rankings públicos.

### :gear: Comandos de Usuario
- **/puntos mi estado:on hora:8 zona:España** — Activa el recordatorio diario a la hora indicada.
  - Zonas soportadas: **España (es)** y **México (mx)**.
  - Hora válida: **0-23** (defecto 8).
- **/puntos mi estado:off** — Cancela los recordatorios.

### :man_office_worker: Comandos de Admin
- **/puntos config estado:on|off vote_links:"Mapa1|URL1,Mapa2|URL2"** — Activa/desactiva el sistema para todo el servidor y personaliza los URLs de voto.
- **/puntos config** (sin args) — Muestra el estado actual y los URLs configurados.

### :white_check_mark: Cómo Funciona
1. A la hora elegida el bot te manda un DM con los enlaces de voto del cluster.
2. El DM incluye un botón **✅ Completado** que marca el día como hecho (visual, no toca tu cuenta de ARK).
3. Al día siguiente vuelve a avisarte automáticamente.

> :bulb: Si el admin desactiva el sistema para todo el servidor con `/puntos config estado:off`, deja de mandar avisos aunque tengas la suscripción activa.""",
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
- **/admin config** — Mismo formulario que `/inicio_ark` pero para **editar** la configuración existente sin recrear los dashboards. Sin argumentos, muestra el estado actual.
- **/admin idioma** — Cambia el idioma del bot en este servidor: Español, Inglés (solo dashboards) o Inglés (todo).
- **/admin bind message_id:... channel_id:...** — Asocia un mensaje existente al dashboard de K4Ultra (útil tras reinstalar el bot).

### :recycle: Mantenimiento
- **/admin clear** — Borra solo los registros de mensajes/dashboards (no toca datos). Útil cuando los dashboards se han desincronizado.
- **/admin wipe** — :radioactive: Borra **TODOS** los datos del servidor (scouts, blacklist, todo-list, líneas, etc.). Acción destructiva — pide confirmación. Solo el propietario.

### :memo: Diagnóstico
- **/admin log** — Muestra los últimos comandos ejecutados en la sesión actual del bot.
- **/help** — Guía completa textual del bot (resumen de todos los módulos).
- **/info modulo:...** — Esta misma ayuda contextual por módulo.""",
    "backup": """# :floppy_disk: Backups de la Base de Datos

El bot guarda automáticamente una copia diaria de `tribe_data.db` para recuperar el estado tras incidentes.

### :alarm_clock: Backup Automático
- Se ejecuta **todos los días a las 04:00 UTC**.
- Los archivos se guardan en `backups/tribe_data_YYYY-MM-DD.db`.
- **Retención: 7 días**: los backups con más de una semana se borran automáticamente.

### :gear: Backup Manual
- **/admin backup** — Genera un backup **al instante**. Útil antes de cambios destructivos (`/admin wipe`, migración de versión, etc.).
  - Devuelve el nombre del archivo y el tamaño en KB.
  - Aplica también la retención de 7 días.

### :information_source: Recuperación
Si necesitas restaurar un backup, copia el `.db` deseado encima de `tribe_data.db` con el bot **detenido** (`systemctl stop arkbot`). Al arrancar, el esquema se valida y migra automáticamente vía `db/schema.py`.

> :warning: Los backups son **locales al servidor del bot**. Si pierdes el servidor entero, pierdes la DB. Considera mantener una copia externa cada cierto tiempo.""",
}
