# Ark Tribe Bot 🦖

Un bot de Discord diseñado a medida y altamente interactivo para gestionar, automatizar y administrar todas las operaciones de una tribu en **ARK: Survival Evolved**. Mantenido y actualizado garantizando rendimiento 100% asíncrono.

## 🚀 Funcionalidades Principales

### 🚨 Sistemas de Alerta y Respuesta (Warfare)

* **Alerta SOS y Reconocimiento Táctico (`/sos`):** Emisión instantánea de reportes estructurados de raid (con tipo, mapa y atacantes) enviando ping al rol de emergencia.
* **Sistema de Chivatazo Silencioso (@policia):** Detector pasivo en los logs del juego que destapa al instante infiltraciones silenciosas cuando el enemigo mata a animales faro con nombres clave.
* **Blacklist Inteligente (`/blacklist`):** Dashboard interactivo por botones que unifica Jugadores y Tribus enemigas (KOS, marcados en 🔴) junto a los registros neutrales automáticos detectados por el radar (⚪).

### 🕵️ Inteligencia, Espionaje y Radar

* **K4Ultra Intelligence (`/k4ultra`):** Motor de espionaje que monitoriza pasivamente el clúster entero, mostrando horas de juego globales y perfiles individuales con estado online, alts compartidos, primeros avistamientos y kda pvp real.
* **Scouting Satelital (`/scout_list`):** Base de datos de bases enemigas paginada. Admite filtrado secreto por mapas e imágenes adjuntas protegidas para evitar *dead links*.
* **Status y Población (`/status`, `/status_permanente`):** Visualización en vivo y permanente de todos tus servidores, cambiando de color si un servidor se cae o se queda vacío.

### 🦕 Genética y Crianza

* **Dashboard de Líneas (Paginado) (`/lineas`):** Tablón interactivo infinito por páginas para registrar las Top Stats (HP, Melee, Stam, etc). Modificable al vuelo desde el propio panel sin recordar comandos.
* **Detector y Logs de Mutaciones:** Sistema de botones embebidos para sumar mutaciones directas (+2 o dobles) y consultar un historial interactivo extraído directo de los logs de Ark para saber quién y cuándo mutó qué dino.
* **Temporizadores de Impronta:** Alarmas clickeables que avisan por el canal en tiempo real enviando un ping personal.

### 🎯 Tareas y Coordinación Tribal

* **To-Do List Interactiva (`/todo_list`):** Panel dinámico paginado donde los miembros pueden reclamar tareas activas y borrarlas cuando logren el objetivo (Farmear, Tamear, etc).
* **Gestor de Eventos LFG (`/evento`):** Sistema por botones para proponer y votar fechas de Bosses y Ascensiones registradas en un contador en vivo.
* **Puntos de Ark (`/config_puntos`):** Suscripciones individuales para recordar cuándo canjear los puntos de votación diarios en el Ark Shop.

### ⚙️ Administración y Base de Datos

* **Motor Integrado (`aiosqlite`) y Refugios (`/wipe_db`):** Toda la inteligencia y configuraciones están apoyadas en una pequeña BD de alto rendimiento asíncrono. Los logs originales pueden consultarse localmente sin salir a la terminal.

---

## 🛠️ Tecnologías y Prácticas

* **Python 3.12+** (Operatividad nativamente asíncrona mediante `asyncio`)
* **discord.py** (App Commands y componentes interactivos UI como Buttons, Views, Modals y Select Menus)
* **aiosqlite** (Motor de base de datos incrustada SQLite garantizando velocidad y no bloqueo)
* **python-a2s** (Comunicación de red Source Engine Query para status directo en los puertos del juego)
* **pytest** (Framework de Testing sólido con `pytest-asyncio` con un 100% de pase)
* Código sometido a estrictos *linters* (Ruff) con un índice de 0 incidencias y advertencias técnicas depuradas.

---

## ⚙️ Instalación y Puesta a Punto

1. **Clonar el repositorio:**

   ```bash
   git clone <url-del-repositorio>
   cd ArkTribeBot
   ```

2. **Requisitos Previos:**
   Asegúrate de tener instalado **Python 3.10** o superior (recomendado **3.12**).

3. **Crear y activar un entorno virtual (Recomendado):**

   ```bash
   python -m venv venv
   # En Windows Powershell:
   .\venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

4. **Instalar dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configuración de Variables de Entorno:**
   Crea un archivo local llamado `.env` en la raíz del proyecto para definir tus claves privadas. Reemplaza los valores ficticios por los reales:

   ```env
   DISCORD_TOKEN=tu_token_del_bot_aqui
   APPLICATION_ID=id_de_tu_aplicacion_aqui
   SOS_ROLE_ID=id_del_rol_para_alertas_sos
   ```

6. **Invitar el Bot al Servidor con los Permisos Correctos:**

   Al añadir el bot a un servidor de Discord, asegúrate de que tiene exactamente los siguientes permisos (y no más). Puedes usar el enlace de OAuth2 de tu aplicación en el [Portal de Desarrolladores de Discord](https://discord.com/developers/applications) y marcar únicamente:

   | Permiso | Para qué lo necesita |
   | --- | --- |
   | **Ver Canales** | Leer el canal de logs del juego y los canales configurados |
   | **Enviar Mensajes** | Enviar alertas SOS, embeds de estado y respuestas a comandos |
   | **Gestionar Mensajes** | Eliminar mensajes residuales de usuarios tras ciertas interacciones |
   | **Insertar Enlace** | Renderizar correctamente los embeds enriquecidos |
   | **Adjuntar Archivos** | Subir capturas de scouts al canal de archivos |
   | **Leer el Historial de Mensajes** | Editar mensajes persistentes (dashboards) ya enviados |
   | **Mencionar a todos** | Enviar alertas `@here` en el canal SOS durante una raid |
   | **Usar Emojis Externos** | Mostrar emojis personalizados en embeds y botones |

   > **Scope requerido:** `bot` + `applications.commands`

   El valor de permisos resultante es `519168`. Sustituye `TU_CLIENT_ID` con el ID de tu aplicación:

   ```text
   https://discord.com/oauth2/authorize?client_id=TU_CLIENT_ID&permissions=519168&integration_type=0&scope=bot+applications.commands
   ```

7. **Ejecutar el bot:**

   ```bash
   python main.py
   ```

## 🧪 Testing

El bot cuenta con una extensa arquitectura de pruebas pre-configurada para asegurar que cada nueva adición funcione según lo esperado antes de impactar en producción.

Para ejecutar la batería de pruebas en local:

```bash
pytest tests/ -v
```

> *Este proyecto/código es de uso exclusivamente privado para alcanzar la dominación total del Cluster ARK.*
