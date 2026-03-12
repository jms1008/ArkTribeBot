# 🦖 Ark Tribe Bot v2.0 - "Tribe Master"

![ArkTribeBot Banner](https://img.shields.io/badge/ARK-Tribe%20Bot-green?style=for-the-badge&logo=discord)
![Version](https://img.shields.io/badge/version-2.0.0-blue?style=for-the-badge)
![License](https://img.shields.io/badge/license-Private-red?style=for-the-badge)

**ArkTribeBot** es una IA táctica integral diseñada para la dominación absoluta en **ARK: Survival Evolved**. No es solo un bot de registro; es un centro de mando asíncrono que coordina guerra, crianza, espionaje y administración tribal en una interfaz premium y paginada.

---

## 📖 Índice de Guía Maestra

1. [Primeros Pasos](#primeros-pasos)
2. [Warfare y Combate](#warfare-y-combate)
3. [K4Ultra Intelligence](#k4ultra-intelligence)
4. [Crianza y Genética](#crianza-y-genética)
5. [Logística Tribal](#logística-tribal)
6. [Guía Técnica e Instalación](#guía-técnica-e-instalación)
7. [Administración](#administración)

---

## Primeros Pasos

Si eres un administrador nuevo, sigue este flujo para activar el bot:

1. **Activación de Comandos:** Escribe `!sync guild` en cualquier canal para que Discord reconozca los nuevos comandos slash (`/`).
2. **Despliegue Maestro:** Ejecuta **`/inicio_ark`**. Este asistente te pedirá los canales clave:
    * **SOS:** Donde llegarán las alertas de raid.
    * **Logs:** El canal "puente" donde tu servidor de Ark vuelca los logs (Tribemember Killed, etc).
    * **Opcionales:** Puedes crear hilos o canales para Breeding, Scouting o Blacklist y el bot los configurará automáticamente.
3. **Ajuste Fino:** Usa **`/config`** para editar parámetros en cualquier momento sin tener que volver a empezar.

---

## Warfare y Combate

### Alertas SOS y @policia

El bot monitoriza el canal de logs 24/7.

* **SOS Manual (/sos):** Envía un informe instantáneo con mapa, tipo de ataque y atacantes. Pinguea al rol configurado.
* **Rastreador @policia:** Si nombras a tus animales centinela con la palabra clave "@policia", el bot emitirá una alerta SOS automática y silenciosa nada más mueran, destapando infiltraciones.

### Tracking de KDA y Sarcasmos

* **Auto-Registro:** Cada vez que el log muestra una muerte, el bot identifica si es un miembro de la tribu.
* **Humor Tribal:** El bot responderá con sarcasmos aleatorios y llevará la cuenta de muertes totales del jugador.
* **Registro de Miembros:** Para que esto funcione, los miembros deben registrar sus personajes con `/ranking_char_add`.

### Blacklist Paginada (/blacklist)

Gestiona la lista de enemigos de forma interactiva.

* **Enemigos (Rojo):** Jugadores marcados manualmente como KOS.
* **Neutrales (Blanco):** Registros automáticos del radar K4Ultra que aún no han sido clasificados.

---

## K4Ultra Intelligence

El motor de espionaje más potente para ARK.

* **Perfil Global (/k4ultra):** Busca a cualquier jugador por nombre para ver:
  * Estado Online/Offline.
  * Frecuencia de horas de juego (¿Cuándo suelen estar desconectados?).
  * Alts y personajes compartidos.
  * KDA PvP real basado en registros de combate.
* **Scouting Satelital (/scout_list):** Catálogo de bases enemigas organizado por mapa. Puedes adjuntar fotos con `/scout_add_image`.

---

## Crianza y Genética

### Dashboard de Líneas (/lineas)

Olvida los excels. Usa el panel paginado para:

* Ver las Top Stats actuales de cada especie.
* Editar mutaciones y estadísticas mediante botones y selectores.
* **Selector Rápido:** Usa el menú desplegable en el panel para consultar un dino específico sin navegar por páginas.

### Log de Mutaciones

El bot lee los logs de crianza. Cuando nace una mutación, aparece un botón en el log. Al pulsarlo:

1. Se registra quién la reclamó.
2. Se actualiza el contador de mutaciones de la línea automáticamente.

---

## Logística Tribal

* **To-Do List (/todo_list):** Añade tareas como "Llenar torretas" o "Farmear metal". Los miembros pueden "reclamarlas". Paginado y con botones de borrado.
* **Eventos LFG (/evento):** Propón fechas para Bosses. Los miembros votan mediante botones y el bot muestra el conteo en tiempo real.
* **Puntos de Ark:** Configura recordatorios para que nadie olvide canjear sus puntos de votación del cluster.

---

## Guía Técnica e Instalación

### 1. Clonación y Requisitos

Asegúrate de tener instalado **Python 3.10** o superior (recomendado **3.12**).

```bash
git clone <url-del-repositorio>
cd ArkTribeBot
```

### 2. Entorno Virtual e Instalación

Es altamente recomendable usar un entorno virtual:

```bash
python -m venv venv
# En Windows: .\venv\Scripts\activate
# En Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuración de Variables (.env)

Crea un archivo local llamado `.env` en la raíz del proyecto para definir tus claves privadas:

```env
DISCORD_TOKEN=tu_token_del_bot_aqui
APPLICATION_ID=id_de_tu_aplicacion_aqui
```

### 4. Permisos de Discord

Al invitar el bot, asegúrate de marcar los siguientes permisos. El valor de permisos recomendado es `519168`.

| Permiso | Uso Específico |
| --- | --- |
| **Ver Canales** | Leer logs de Ark y canales de comandos. |
| **Enviar Mensajes** | Alertas, dashboards y respuestas interactivas. |
| **Gestionar Mensajes** | Limpieza de mensajes residuales en la UI. |
| **Insertar Enlaces** | Renderizado de embeds y dashboards premium. |
| **Adjuntar Archivos** | Subida de imágenes de scouting y evidencias. |
| **Mencionar @everyone** | Alertas SOS críticas en canales de emergencia. |
| **Leer Historial** | Edición y actualización de dashboards persistentes. |
| **Emojis Externos** | Uso de iconos personalizados en botones y embeds. |

---

## Administración

### Comandos de Seguridad

* **`/config`:** El "corazón" del bot. Solo accesible por el Dueño o usuarios con el Rol Admin configurado.
* **`!sync`:** Comando de texto de emergencia para sincronizar la API de Discord.
* **`/wipe_db`:** Borrado selectivo de tablas en caso de cambio de temporada o servidor.

### Ejecución y Tests

Para arrancar el bot:

```bash
python main.py
```

Para verificar la integridad del sistema (Suite de Pruebas):

```bash
pytest tests/ -v
```

---
> ArkTribeBot v2.0 • Domina el mapa, lidera tu tribu.
