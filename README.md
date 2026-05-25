# Ark Tribe Bot v3.0 — "Cluster Master"

[![ARK Tribe Bot](https://img.shields.io/badge/ARK-Tribe%20Bot-358750?style=for-the-badge&logo=discord)](https://github.com/jms1008/ArkTribeBot)
[![Version](https://img.shields.io/badge/version-3.0.0-blue?style=for-the-badge)](https://github.com/jms1008/ArkTribeBot/releases)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-red.svg?style=for-the-badge)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-124%20passing-brightgreen?style=for-the-badge)](https://github.com/jms1008/ArkTribeBot/actions)
[![Python](https://img.shields.io/badge/python-3.12+-yellow?style=for-the-badge&logo=python)](https://www.python.org/)

**ArkTribeBot** es un sistema de gestión integral para clusters de **ARK: Survival Ascended / Evolved**. Actúa como un centro de mando asíncrono que coordina las operaciones de guerra, crianza, espionaje y administración de la tribu a través de una interfaz interactiva en Discord.

---

## 📖 Índice

1. [🚀 Configuración Inicial](#-configuración-inicial) — Despliegue y puesta a punto en 2 pasos.
2. [⚔️ Gestión de Guerra](#️-gestión-de-guerra) — Alertas SOS, alarmas de intrusos, KDA y blacklist.
3. [🕵️ Sistema de Inteligencia](#️-sistema-de-inteligencia) — K4Ultra Radar y Scouting Geográfico.
4. [🦕 Gestión de Crianza](#-gestión-de-crianza) — Líneas genéticas, mutaciones y alarmas de impronta.
5. [📈 Logística Tribal](#-logística-tribal) — To-Do, eventos LFG y recordatorios de voto.
6. [🛠️ Guía Técnica](#️-guía-técnica) — Stack, instalación, arquitectura y CI.
7. [🛡️ Seguridad y Administración](#️-seguridad-y-administración) — Control de acceso, backups y mantenimiento.

---

## 🚀 Configuración Inicial

El proceso está diseñado para que un admin tenga el bot operativo en 2 pasos.

* **Pre-requisito:** crea los canales que usará el bot (ej. `#blacklist`, `#scouting`, `#crianza`, `#todo-list`, `#k4ultra`, `#status`, `#alarmas`).
* **`/inicio_ark`** — Asistente único: vincula canales, registra el cluster en `battlemetrics_urls`, configura rol admin/propietario y despliega todos los dashboards automáticamente.
* **`/config`** — Editar la configuración existente sin recrear nada.
* **`/sync guild`** *(prefix command)* — Registra los comandos slash en este servidor inmediatamente tras invitar al bot.
* **`/info modulo:...`** y **`/guia`** — Ayuda contextual e interactiva en cualquier momento.

---

## ⚔️ Gestión de Guerra

Herramientas para vigilar y reaccionar a ataques en tiempo real.

* **Alertas SOS estructuradas (`/sos`):** mapa, tipo de amenaza (raideo/FOB/soaking/...), recuento de fuerzas y notas. Botón "Solucionado" para silenciar.
* **Detector silencioso `@policia`:** marcar un dino con `@policia` hace que su muerte se reporte automáticamente en el canal de SOS. Útil para detectar infiltrados sin que el atacante lo sepa.
* **Alarmas de Intrusos (`/alarma`, `/alarmas`):** vigilancia pasiva por mapa. El bot lee el caché compartido de A2S (sin tráfico extra) y avisa a quien la activó cuando entra un jugador NO registrado como tribu propia ni personaje conocido.
* **Tracking KDA (`/ranking`):** lee los logs del juego, parsea muertes y mantiene un leaderboard de mortalidad con barras de progreso, picos por hora y rangos sarcásticos. Anti-fuego-amigo: si el asesino también es miembro de la tribu, NO suma.
* **Blacklist (`/blacklist`, `/bl_editar`):** dashboard con enemigos (KOS) y neutrales auto-detectados por K4Ultra. Enriquecimiento automático con horas totales, último mapa y last_seen.

---

## 🕵️ Sistema de Inteligencia

Recopilación y análisis pasivo de datos del cluster.

* **K4Ultra Radar (`/k4ultra modo:radar`):** ranking paginado con jugadores online en tiempo real y top global de horas. Heurística `duration_score` del protocolo A2S para distinguir jugadores reales de nombres genéricos (`123`, `bob`, etc.).
* **K4Ultra Tribus (`/k4ultra modo:tribus`):** grafo de alianzas predictivo. Acumula puntos por minutos compartidos, login/logout sincronizados y transferencias simultáneas. **Decaimiento del 5%/día** en relaciones inactivas. Soporta tribus fijadas manualmente, aliases globales y fusión/separación de identidades.
* **Gestión de identidades:** `/perfil_tribu`, `/fusionar_perfiles`, `/k4ultra_merge`, `/k4ultra_split`, `/k4ultra_cleanup`, `/fijar_tribu`, `/unfijar_tribu`, `/tribu_propia crear|modificar|borrar`.
* **Scouting Geográfico (`/scout_list`, `/scout_add`, `/scout_add_image`):** directorio de bases enemigas paginado por mapa. Acepta imágenes adjuntas (almacenadas en un canal upload propio). Niveles de amenaza 1-5 con barras visuales.

---

## 🦕 Gestión de Crianza

Módulos dedicados a la optimización de las líneas de sangre.

* **Dashboard `/lineas`:** las 7 stats por especie (HP / Melee / Stam / Peso / Oxy / Comida / Speed) con `—` para las no registradas, paginado automático.
* **Comandos `/linea_add`, `/linea_mod`, `/linea_ver`:** añadir, modificar y consultar stats con validación de columna (whitelist anti-inyección).
* **Botones del dashboard:** Nueva muta (+2 con log automático), Alarmas (1.5h / 2.5h / 4h / 10h para impronta o crecimiento), Ver Logs Muta.
* **`/log_mutas`:** las últimas 20 mutaciones registradas con timestamp.
* **Selector inferior:** consulta privada con todas las stats de un dino concreto.

---

## 📈 Logística Tribal

Coordinación diaria de los miembros.

* **To-Do List (`/todo_list`, `/todo_add`):** panel agrupado por estado (🔨 En Progreso / ⏳ Pendientes), multi-asignación con toggle de reclamar y refresh automático tras cada cambio.
* **Gestor de Eventos LFG (`/evento`):** encuestas con 2-4 opciones, votación por botones, botón "No puedo asistir", actualización en vivo del recuento con barras de progreso. Persistencia tras reinicios del bot.
* **Puntos Diarios (`/puntos_diarios`):** recordatorio por DM a la hora elegida (zonas `es` y `mx`) con los URLs de voto del cluster. El admin configura los URLs por servidor con `/config_puntos`.

---

## 🛠️ Guía Técnica

Información necesaria para autohospedar y mantener el bot.

### Stack

* **Python 3.12** + **discord.py ≥ 2.7** (slash commands, Views persistentes, Modals).
* **aiosqlite** con WAL — conexión persistente compartida (`bot.db`).
* **python-a2s** — Steam Query Protocol con caché compartido de 90 s.
* **pytest + pytest-asyncio** — **124 tests** en CI (`asyncio_mode = auto`).
* **ruff** + **pre-commit** — lint y formato automáticos.

### Arquitectura (resumen)

```
main.py                  → Entrypoint, setup_hook, persistent Views, on_ready
db/
  schema.py              → CREATE TABLE + ALTER + CREATE INDEX unificados
  database.py            → Database: conexión persistente (bot.db) + helpers
utils/
  parsing.py             → Funciones puras (parse_battlemetrics, whitelists SQL)
  bus.py                 → Constantes de eventos del bus (BLACKLIST_UPDATED, etc.)
cogs/
  admin / alarma / backup / breeding / daily_points / events
  k4ultra/  (paquete: cog · embeds · sessions · relationships · ui)
  log_processor / management / scouting / server_status / warfare
tests/                   → 124 tests
.github/
  workflows/tests.yml    → pytest en cada push/PR
  workflows/deploy.yml   → SSH deploy a producción al hacer push a main
  dependabot.yml         → Updates semanales de pip + mensuales de actions
```

Detalles clave:

* **Esquema centralizado** en `db/schema.py` — los cogs NUNCA crean tablas.
* **Bus de eventos interno** (`utils/bus.py`) — los cogs dueños de dashboards escuchan eventos en vez de importar funciones de otros cogs.
* **Conexión SQLite persistente** — un único `bot.db` compartido en hot paths (task loops cada minuto). Resto de comandos usan conexión efímera.
* **Backups automáticos diarios** a las 04:00 UTC en `backups/` con retención de 7 días (cog `backup`).
* **Rotación de logs** con `TimedRotatingFileHandler` (14 días).

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

Invita al bot con permiso integral `519168` para asegurar el funcionamiento de Views y Modals.

### Tests y CI

```bash
python -m pytest tests/ -v       # 124 tests, ~10 s
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
* **Autorización admin:** `/config`, `/wipe_db`, `/bind_k4ultra`, `/db_backup` y similares requieren permiso de administrador del servidor, rol designado en `guild_config.admin_role_id`, o el `BOT_OWNER_ID` global del `.env`.
* **Mantenimiento:**
    * `/wipe_db` — ☢️ Borra **TODOS** los datos del servidor (acción destructiva, pide confirmación).
    * `/clear_updates` — Borra solo los registros de mensajes/dashboards (no toca datos).
    * `/db_backup` — Backup manual instantáneo.
    * `/log` — Últimos comandos ejecutados en la sesión actual.

---

> *ArkTribeBot v3.0 — Sistema integral de gestión para el Cluster.*
