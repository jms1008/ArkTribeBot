# Ark Tribe Bot v3.1 — "Babel"

[![ARK Tribe Bot](https://img.shields.io/badge/ARK-Tribe%20Bot-358750?style=for-the-badge&logo=discord)](https://github.com/jms1008/ArkTribeBot)
[![Version](https://img.shields.io/badge/version-3.1.0-blue?style=for-the-badge)](https://github.com/jms1008/ArkTribeBot/releases)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-red.svg?style=for-the-badge)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-204%20passing-brightgreen?style=for-the-badge)](https://github.com/jms1008/ArkTribeBot/actions)
[![Python](https://img.shields.io/badge/python-3.12+-yellow?style=for-the-badge&logo=python)](https://www.python.org/)

**ArkTribeBot** es un sistema de gestión integral para clusters de **ARK: Survival Ascended / Evolved**. Actúa como un centro de mando asíncrono que coordina las operaciones de guerra, crianza, espionaje y administración de la tribu a través de una interfaz interactiva en Discord. **Bilingüe (Español/Inglés)** por servidor y por usuario.

---

## 📖 Índice

1. [🚀 Configuración Inicial](#-configuración-inicial) — Despliegue y puesta a punto en 2 pasos.
2. [🌐 Idiomas](#-idiomas) — Español e inglés, por servidor o por usuario.
3. [⚔️ Gestión de Guerra](#️-gestión-de-guerra) — Alertas SOS, trampas, alarmas de intrusos, KDA y blacklist.
4. [🕵️ Sistema de Inteligencia](#️-sistema-de-inteligencia) — K4Ultra Radar, gestión de tribus y Scouting.
5. [🦕 Gestión de Crianza](#-gestión-de-crianza) — Líneas genéticas, mutaciones y alarmas de impronta.
6. [📈 Logística Tribal](#-logística-tribal) — To-Do, eventos LFG y recordatorios de voto.
7. [🛠️ Guía Técnica](#️-guía-técnica) — Stack, instalación, arquitectura y CI.
8. [🛡️ Seguridad y Administración](#️-seguridad-y-administración) — Control de acceso, backups y mantenimiento.

---

## 🚀 Configuración Inicial

El proceso está diseñado para que un admin tenga el bot operativo en 2 pasos.

* **Pre-requisito:** crea los canales que usará el bot (ej. `#blacklist`, `#scouting`, `#crianza`, `#todo-list`, `#k4ultra`, `#status`, `#alarmas`).
* **`/inicio_ark`** — Asistente único: vincula canales, registra el cluster en `battlemetrics_urls`, configura rol admin/propietario y despliega todos los dashboards automáticamente.
* **`/admin config`** — Editar la configuración existente sin recrear nada.
* **`/sync guild`** *(prefix command)* — Registra los comandos slash en este servidor inmediatamente tras invitar al bot.
* **`/help`** y **`/info modulo:...`** — Manual interactivo y ayuda contextual, ambos con selector de idioma.

### Comandos agrupados por temática

Toda la superficie de comandos está organizada en **9 grupos** + 7 comandos sueltos:

| Grupo | Subcomandos |
|---|---|
| `/tribu` | `propia crear/modificar/borrar` · `aliada crear/modificar/borrar/lista` · `miembro crear/borrar` · `fijar` · `desfijar` · `fusionar` · `separar` · `limpiar` · `lista` |
| `/scout` | `add` · `imagen` · `borrar` · `lista` · `panel` |
| `/linea` | `add` · `mod` · `ver` · `panel` · `log` |
| `/status` | `mapa` · `cluster` · `fijar` |
| `/alarma` | `activar` · `panel` |
| `/blacklist` | `panel` · `editar` |
| `/todo` | `add` · `panel` |
| `/puntos` | `mi` · `config` |
| `/admin` | `config` · `idioma` · `bind` · `clear` · `wipe` · `log` · `backup` |
| *Sueltos* | `/sos` · `/ranking` · `/evento crear/cerrar` · `/k4ultra` · `/inicio_ark` · `/info` · `/help` |

---

## 🌐 Idiomas

Soporte bilingüe **Español / Inglés** en tres niveles:

* **Por servidor:** `/admin idioma` con 3 modos — `Español` (todo en español), `English (solo dashboards)` (los paneles automáticos en inglés) o `English (todo)` (absolutamente todo: paneles, respuestas de comandos y hasta los sarcasmos del ranking).
* **Por usuario:** el campo `idioma` de `/tribu miembro crear` fija el idioma personal de un miembro — sus respuestas de comandos y alertas DM llegarán en su idioma, independientemente del servidor.
* **Por consulta:** `/help` y `/info` aceptan el parámetro `idioma` para ver cualquier guía en ES o EN al momento.

Las **horas** de alertas y SOS se muestran como timestamps nativos de Discord: cada miembro las ve en **su zona horaria local** automáticamente.

---

## ⚔️ Gestión de Guerra

Herramientas para vigilar y reaccionar a ataques en tiempo real.

* **Alertas SOS estructuradas (`/sos`):** mapa, tipo de amenaza (raideo/FOB/soaking/...), recuento de fuerzas, hora local y notas. Botón "Solucionado" para silenciar.
* **Trampas silenciosas:**
  * **Dinos `@policia` / `@log`:** marcar un dino con cualquiera de estos tags hace que su muerte se reporte automáticamente en el canal de SOS. Útil para detectar infiltrados sin que el atacante lo sepa.
  * **Cajas-trampa (`SS Storage Box`):** si destruyen una caja SS Storage Box con nombre, salta una alerta de *intruso en [nombre]* con el mapa resuelto desde el tag del log (`(Abr)` → Aberration, `(Isl)` → The Island...). Anti-spam: 1 alerta/10 min por caja.
* **Alarmas de Intrusos (`/alarma activar`, `/alarma panel`):** vigilancia pasiva por mapa. El bot lee el caché compartido de A2S (sin tráfico extra) y avisa por **DM** cuando entra un jugador NO registrado como tribu propia, tribu aliada ni personaje conocido.
  * **Anti-spam:** un único mensaje-resumen por mapa que se va actualizando con la lista de intrusos y su hora de entrada (en tu hora local). Botón *Silenciar* para descartar.
  * Detecta incluso a jugadores con Steam name duplicado ("123", "bob") gracias al conteo por multiconjunto.
* **Tracking KDA (`/ranking`):** lee los logs del juego, parsea muertes y mantiene un leaderboard de mortalidad con barras de progreso, picos por hora y rangos sarcásticos (bilingües). Anti-fuego-amigo: si el asesino también es miembro de la tribu, NO suma.
* **Blacklist (`/blacklist panel`, `/blacklist editar`):** dashboard con enemigos (KOS) y neutrales auto-detectados por K4Ultra. Enriquecimiento automático con horas totales, último mapa y last_seen. Botones Añadir/Modificar/Eliminar con modal.

---

## 🕵️ Sistema de Inteligencia

Recopilación y análisis pasivo de datos del cluster.

* **K4Ultra Radar (`/k4ultra modo:radar`):** ranking paginado con jugadores online en tiempo real y top global de horas. Heurística `duration_score` del protocolo A2S para distinguir jugadores reales de nombres genéricos (`123`, `bob`, etc.).
* **K4Ultra Tribus (`/k4ultra modo:tribus`):** grafo de alianzas predictivo. Acumula puntos por minutos compartidos, login/logout sincronizados y transferencias simultáneas. **Decaimiento del 5%/día** en relaciones inactivas.
* **Gestión de tribus e identidades — grupo `/tribu`:**
  * `propia crear/modificar/borrar` — tu tribu (excluida del radar y de las alarmas).
  * `aliada crear/modificar/borrar/lista` — tribus aliadas (no disparan alarmas de intrusos).
  * `fijar` / `desfijar` — etiquetar otras tribus conocidas en el modo Tribus.
  * `miembro crear/borrar` — ficha completa de cada miembro (Discord + personaje + Steam + apodo + idioma personal). El borrado limpia perfil, alias, idioma y lo saca de la tribu propia.
  * `fusionar` / `separar` / `limpiar` — mantenimiento de identidades duplicadas del radar.
  * `lista` — vista única de TODAS las tribus registradas (⭐ propia, 🤝 aliadas, 📌 fijadas).
* **Scouting Geográfico — grupo `/scout`:** directorio de bases enemigas. `add` (con imagen), `imagen` (adjuntar a posteriori), `borrar`, `lista` (consulta privada global o por mapa) y `panel` (dashboard público). Niveles de amenaza 1-5 con barras visuales.

---

## 🦕 Gestión de Crianza

Módulos dedicados a la optimización de las líneas de sangre — grupo `/linea`.

* **Dashboard `/linea panel`:** las 7 stats por especie (HP / Melee / Stam / Peso / Oxy / Comida / Speed) con `—` para las no registradas, paginado automático.
* **`/linea add`, `/linea mod`, `/linea ver`:** añadir, modificar y consultar stats con validación de columna (whitelist anti-inyección).
* **Botones del dashboard:** Nueva muta (+2 con log automático), Alarmas (1.5h / 2.5h / 4h / 10h para impronta o crecimiento), Ver Logs Muta.
* **`/linea log`:** las últimas 20 mutaciones registradas con timestamp.
* **Selector inferior:** consulta privada con todas las stats de un dino concreto.

---

## 📈 Logística Tribal

Coordinación diaria de los miembros.

* **To-Do List (`/todo panel`, `/todo add`):** panel agrupado por estado (🔨 En Progreso / ⏳ Pendientes), multi-asignación con toggle de reclamar y refresh automático tras cada cambio.
* **Gestor de Eventos LFG (`/evento crear`, `/evento cerrar`):** encuestas con 2-4 opciones, votación por botones, botón "No puedo asistir", actualización en vivo del recuento con barras de progreso. Persistencia tras reinicios y cierre con archivado (botones desactivados).
* **Puntos Diarios (`/puntos mi`):** recordatorio por DM a la hora elegida (zonas `es` y `mx`) con los URLs de voto del cluster. El admin configura los URLs por servidor con `/puntos config`.

---

## 🛠️ Guía Técnica

Información necesaria para autohospedar y mantener el bot.

### Stack

* **Python 3.12** + **discord.py ≥ 2.7** (slash commands con grupos anidados, Views persistentes, Modals).
* **aiosqlite** con WAL — conexión persistente compartida (`bot.db`).
* **python-a2s** — Steam Query Protocol con caché compartido de 90 s.
* **pytest + pytest-asyncio** — **204 tests** en CI (`asyncio_mode = auto`).
* **ruff** + **pre-commit** — lint y formato automáticos.

### Arquitectura (resumen)

```
main.py                  → Entrypoint, setup_hook, persistent Views, bloqueo de DMs
db/
  schema.py              → CREATE TABLE + ALTER + CREATE INDEX unificados
  database.py            → Database: conexión persistente (bot.db) + helpers
locales/
  strings.py             → Catálogo i18n de cadenas cortas (ES/EN)
  guides_es.py / _en.py  → Guías largas de /help e /info en ambos idiomas
utils/
  parsing.py             → Funciones puras (battlemetrics, destrucciones, tags de mapa, whitelists SQL)
  i18n.py                → resolve_lang (servidor/usuario/scope) + t() con fallback
  bus.py                 → Constantes de eventos del bus (BLACKLIST_UPDATED, etc.)
cogs/
  admin / alarma / backup / breeding / daily_points / events
  k4ultra/  (paquete: cog · embeds · sessions · relationships · ui)
  log_processor / management / scouting / server_status / warfare
tests/                   → 204 tests
.github/
  workflows/tests.yml    → pytest en cada push/PR
  workflows/deploy.yml   → SSH deploy a producción al hacer push a main
  dependabot.yml         → Updates semanales de pip + mensuales de actions
```

Detalles clave:

* **Esquema centralizado** en `db/schema.py` — los cogs NUNCA crean tablas.
* **i18n por scope**: `periodic` (dashboards compartidos → idioma del servidor) vs `command` (respuestas → idioma personal del usuario si lo tiene; si no, el del servidor en modo total).
* **Bus de eventos interno** (`utils/bus.py`) — refresco de dashboards e invalidación de snapshots de alarmas (`TRUSTED_MEMBERS_CHANGED`) sin imports cruzados.
* **Conexión SQLite persistente** — un único `bot.db` compartido en hot paths (task loops cada minuto).
* **Backups automáticos diarios** a las 04:00 UTC en `backups/` con retención de 7 días (+ `/admin backup` manual).
* **Rotación de logs** con `TimedRotatingFileHandler` (14 días).
* **DMs entrantes bloqueados**: los usuarios no pueden usar comandos por DM; las alertas salientes por DM siguen funcionando.

### Instalación

```bash
git clone https://github.com/jms1008/ArkTribeBot
cd ArkTribeBot
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # rellenar DISCORD_TOKEN, APPLICATION_ID, BOT_OWNER_ID
python main.py
```

### Permisos requeridos

Invita al bot con permiso integral `519168` para asegurar el funcionamiento de Views y Modals. Los miembros deben tener los **DMs abiertos** para recibir alarmas de intrusos.

### Tests y CI

```bash
python -m pytest tests/ -v       # 204 tests, ~17 s
python -m ruff check . --fix     # lint + autofix
python -m ruff format .          # format
pre-commit install               # hook local opcional
```

Cada push a `main` ejecuta los tests automáticamente vía GitHub Actions (`.github/workflows/tests.yml`) y, en paralelo, dispara el deploy SSH a producción.

---

## 🛡️ Seguridad y Administración

Protocolos para garantizar la integridad y privacidad del servicio.

* **Aislamiento por servidor (`guild_id`):** todas las consultas filtran por servidor. No hay fugas entre guilds.
* **Whitelist anti-inyección SQL:** `utils.parsing.ALLOWED_BLACKLIST_FIELDS` y `ALLOWED_DINO_STATS` validan cualquier columna interpolada en `UPDATE`/`INSERT` dinámicos.
* **Autorización admin:** los subcomandos de `/admin`, la gestión de `/tribu` y similares requieren permiso de administrador del servidor, rol designado en `guild_config.admin_role_id`, o el `BOT_OWNER_ID` global del `.env`.
* **Mantenimiento (grupo `/admin`):**
    * `/admin wipe` — ☢️ Borra **TODOS** los datos del servidor (33 tablas; `guild_config` sobrevive para que el bot siga configurado).
    * `/admin clear` — Borra solo los registros de mensajes/dashboards (no toca datos).
    * `/admin backup` — Backup manual instantáneo.
    * `/admin log` — Últimos comandos ejecutados en la sesión actual.
    * `/admin idioma` — Idioma del servidor (ES / EN parcial / EN total).

---

> *ArkTribeBot v3.1 — Sistema integral de gestión para el Cluster, ahora bilingüe.*
