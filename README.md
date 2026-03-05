# Ark Tribe Bot 🦖

Bot de Discord diseñado a medida para gestionar y administrar todas las operaciones de una tribu jugando a **ARK: Survival Evolved**.

## 🚀 Funcionalidades Principales

* **⚔️ Dashboard de Guerra (Warfare)**
  * **K/D/A Tracker:** Ranking automatizado ("El Más Manco") que lee los logs in-game para puntuar asesinos y víctimas excluyendo el Fuego Amigo.
  * **Blacklist:** Base de datos auto-actualizable in-game para trackear a jugadores non gratos, su tribu y sus bases.
  * **Alertas SOS:** Sistema de pings estructurados para avisos de Raideo, Soaking, FOB o Scouting enemigo.
* **🧬 Crianza y Mutaciones**
  * **Gestión de Líneas:** Tablón visual para compartir y registrar por especie los puntos en Vida, Melee, Peso, etc.
  * **Temporizadores:** Sistema de alarmas de maduración/impronta con avisos al usuario y auto-eliminación de notificaciones.
* **🕵️ Inteligencia (K4Ultra & Scouting)**
  * Analizador de actividad de jugadores rivales y mapas para predecir alianzas ("Relationships") mediante algoritmos de co-ocurrencia.
* **🎁 Tareas y Mantenimiento**
  * Recordatorios diarios (Configurables por Zona Horaria) para canjear Puntos de Tienda (Ark Shop/Vote Rewards).
  * Gestor de Tareas `/todo` integrado en Discord (Pendiente, En Curso, Terminado).

## 🛠️ Tecnologías Utilizadas

* **Python 3.10+** (Asíncrono total)
* **Discord.py** (App Commands, Modals, Views, Selects)
* **aiosqlite** (Base de datos local ultrarrápida incrustada)
* Integraciones con Webhooks nativos del servidor (Lectura de kills de Super Structures o mods similares).

## ⚙️ Instalación y Puesta a Punto

1. **Clonar el repositorio:**

   ```bash
   git clone <url-del-repositorio>
   cd ArkTribeBot
   ```

2. **Requisitos Previos:**
   Asegúrate de tener instalado **Python 3.10** o superior.

3. **Crear y activar un entorno virtual (Recomendado):**

   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/Mac:
   source venv/bin/activate
   ```

4. **Instalar dependencias:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configuración de Variables de Entorno:**
   Crea un archivo local llamado `.env` en la raíz del proyecto para definir tus claves privadas y configuración. Debe tener la siguiente estructura:

   ```env
   DISCORD_TOKEN=tu_token_del_bot_aqui
   APPLICATION_ID=id_de_tu_aplicacion_aqui
   SOS_ROLE_ID=id_del_rol_para_alertas_sos
   ```

6. **Ejecutar el bot:**

   ```bash
   python main.py
   ```

> *Este código es de uso exclusivamente privado.*
