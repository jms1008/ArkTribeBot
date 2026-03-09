# Ark Tribe Bot 🦖

Un bot de Discord diseñado a medida y altamente interactivo para gestionar, automatizar y administrar todas las operaciones de una tribu en **ARK: Survival Evolved**. Mantenido y actualizado garantizando rendimiento 100% asíncrono.

## 🚀 Funcionalidades Principales

### 🎯 Organización y Eventos

* **Gestor de Eventos LFG (`/evento`):** Sistema interactivo basado en botones para organizar Bosses y actividades, permitiendo votar horarios y registrar asistencia automáticamente en paneles auto actualizables.
* **Gestor de Tareas (`/todo_list`, `/todo_add`):** Panel dinámico integrado en Discord para gestionar tareas pendientes, asignarlas (en curso) y darles cierre (terminado).
* **Alertas de Reclamación Diaria (`/puntos_diarios`):** Sistema de suscripciones y temporizadores precisos por zona horaria para no olvidar los canjes de moneda/Puntos de Tienda (Ark Shop).

### 🦕 Crianza y Genética

* **Gestor de Líneas de Crianza (`/lineas`):** Tablones visuales por especie para registrar, centralizar y actualizar estadísticas base (HP, Stamina, Melee, Peso, Oxígeno, Comida, Velocidad).
* **Tracker Inmersivo de Mutaciones:** Extracción de logs y seguimientos para rastrear en qué ramas ocurre una mutación individual o, para los afortunados, dobles mutaciones genéticas.

### 🕵️ Inteligencia y Monitorización (Radar)

* **K4Ultra Intelligence:** Escáner pasivo (vía A2S) que vigila la inmensidad de los mapas. Analiza tiempos de conexión, mapeo habitual de los rivales y elabora algoritmos de co-ocurrencia para predecir alianzas y relaciones de tribus enemigas.
* **Status y Población de Servidores (`/status`):** Visualización en vivo y permanente del ping y número de jugadores online a lo largo de todo el cluster, ignorando slots ocultos o falsos.
* **Scouting de Bases (`/scout_list`):** Inteligencia militar. Base de datos con coordenadas, niveles de amenaza (1-5), notas e imágenes adjuntas protegidas de los "dead links". Admite filtrado global o privado.

### ⚔️ Guerra y Moderación (Warfare)

* **Blacklist (`/blacklist`):** Registro de jugadores "non gratos" y tribus problemáticas. Integrado codo a codo con K4Ultra para el auto-blacklisting de amenazas detectadas en tiempo real.
* **Alertas SOS de Emergencia (`/sos`):** Emisión instantánea de reportes estructurados marcables mediante *pings* al instante (Soaking, Raideo Inminente, FOB Enemigo) alertando sobre atacantes/defensores presenciales.

### ⚙️ Administración

* Comandos restringidos para establecer configuraciones principales, consultar logs crudos (`/log`) y realizar limpiezas base de datos para inicio a temporadas (Wipes) (`/wipe_db`).

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
