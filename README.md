# Ark Tribe Bot v2.0 - "Tribe Master"

[![ARK Tribe Bot](https://img.shields.io/badge/ARK-Tribe%20Bot-358750?style=for-the-badge&logo=discord)](https://github.com/jms1008/ArkTribeBot)
[![Version](https://img.shields.io/badge/version-2.0.0-blue?style=for-the-badge)](https://github.com/jms1008/ArkTribeBot/releases)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-red.svg?style=for-the-badge)](https://www.gnu.org/licenses/agpl-3.0)

**ArkTribeBot** es un sistema de gestión integral para **ARK: Survival Evolved**. Actúa como un centro de mando asíncrono que coordina las operaciones de guerra, crianza, espionaje y administración tribal a través de una interfaz interactiva en Discord.

---

## 📖 Índice

1. [🚀 Configuración Inicial](#-configuración-inicial) - Instrucciones de despliegue y puesta a punto.
2. [⚔️ Gestión de Guerra (Warfare)](#️-gestión-de-guerra-warfare) - Alertas SOS, radar y seguimiento de bajas.
3. [🕵️ Sistema de Inteligencia](#️-sistema-de-inteligencia) - Consultas de perfiles con K4Ultra y Scouting de bases.
4. [🦕 Gestión de Crianza](#-gestión-de-crianza) - Registro de líneas de sangre y control de mutaciones.
5. [📈 Logística Tribal](#-logística-tribal) - Organización de tareas y planificación de eventos.
6. [🛠️ Guía Técnica](#️-guía-técnica) - Requisitos e instrucciones de instalación.
7. [🛡️ Seguridad y Administración](#️-seguridad-y-administración) - Control de acceso y gestión de datos del servidor.

---

## 🚀 Configuración Inicial

El proceso de configuración está diseñado para ser directo y funcional.

* **Sincronización de Comandos (`!sync guild`):** Registra los comandos slash en el servidor de Discord. Es el primer paso necesario tras invitar al bot.
* **Asistente `/inicio_ark`:** Guía al administrador en la vinculación de canales clave (SOS, Logs, Scouting, etc.) y la creación automática de hilos de trabajo.
* **Panel `/config`:** Permite visualizar la configuración actual y editar canales o roles administrativos de forma interactiva.

---

## ⚔️ Gestión de Guerra (Warfare)

Proporciona herramientas para la monitorización de eventos en el servidor de juego.

* **Alertas SOS Automáticas:** El sistema analiza los logs del servidor y genera alertas con información detallada del mapa, tipo de ataque y agresores.
* **Detector @policia:** Al etiquetar animales clave con el nombre `@policia`, el bot generará una alerta automática inmediata tras su muerte, facilitando la detección de incursiones silenciosas.
* **Tracking de Bajas (KDA):** Registra las muertes de los miembros de la tribu, proporcionando estadísticas acumuladas y respuestas aleatorias automatizadas en cada evento.

---

## 🕵️ Sistema de Inteligencia

Herramientas para la recopilación de datos sobre otros jugadores y ubicaciones.

* **K4Ultra Intelligence Dashboard:** Motor de inteligencia avanzada y continuo.
  * **Modo Radar:** Ranking paginado dinámicamente (`/k4ultra modo:radar`) con jugadores conectados, tiempo de juego verificado y seguimiento anti-nombres genéricos (ej. `123`) mediante cálculo de tolerancia `duration_score` del protocolo A2S.
  * **Modo Tribus:** Mapa de alianzas predictivo (`/k4ultra modo:tribus`). Agrupa jugadores por coincidencias de tiempo y sesiones. Permite establecer tu propia tribu principal (`/tribu_propia`) para destacarla visualmente, soporta la reasignación de nombres (Aliases globales) y aplica un decaimiento inactivo del 5% diario a las predicciones.
* **Scouting Geográfico (`/scout_list`):** Directorio de bases enemigas organizado por mapas. Permite adjuntar imágenes mediante `/scout_add_image` para facilitar el reconocimiento previo.

---

## 🦕 Gestión de Crianza

Módulos dedicados a la optimización de las líneas de sangre.

* **Dashboard `/lineas`:** Panel interactivo para monitorizar las mejores estadísticas (Top Stats) de cada especie. Permite actualizaciones directas de datos sin comandos adicionales.
* **Selector de Especies:** Menú desplegable para filtrar y consultar rápidamente la información de un dinosaurio específico dentro de las líneas registradas.
* **Registro de Mutaciones:** Monitorización de logs de nacimiento con botones interactivos para registrar mutaciones nuevas y documentar quién realizó la reclamación.

---

## 📈 Logística Tribal

Herramientas para la coordinación diaria de los miembros.

* **Lista de Tareas (To-Do):** Panel para asignar y reclamar objetivos (farma, mantenimiento, etc.), permitiendo un seguimiento visual del progreso.
* **Gestor de Eventos (`/evento`):** Sistema de votación para planificar actividades grupales como jefes (bosses) o ascensiones.
* **Puntos de Ark Shop:** Recordatorios configurables para el canje de puntos de votación diarios del cluster.

---

## 🛠️ Guía Técnica

Información necesaria para el autohospedaje y mantenimiento.

* **Requisitos:** Python 3.12+ y motor de base de datos `aiosqlite`.
* **Instalación:**

```bash
git clone https://github.com/jms1008/ArkTribeBot
cd ArkTribeBot
python -m venv venv
# En Windows: .\venv\Scripts\activate
# En Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

* **Permisos Requeridos:** Se recomienda invitar al bot con el permiso integral `519168` para asegurar el correcto funcionamiento de los componentes interactivos.

---

## 🛡️ Seguridad y Administración

Protocolos para garantizar la integridad y privacidad del servicio.

* **Aislamiento de Datos:** Arquitectura diseñada para separar estrictamente la información por `guild_id`, evitando cualquier fuga de datos entre servidores.
* **Roles Administrativos:** Acceso restringido a comandos críticos (`/config`, `/wipe_db`) limitado al propietario o usuarios con el rol designado.
* **Gestión de Datos:** Herramientas para la limpieza selectiva de tablas (`/wipe_db`) durante cambios de temporada o mantenimiento. Purga selectiva de analíticas predictivas de IA mediante `/reset_k4_dynamic`.

---
> *ArkTribeBot v2.0 • Sistema integral de gestión para el Cluster.*
