# Ark Tribe Bot 🦖

Bot privado de Discord diseñado a medida para gestionar y administrar todas las operaciones de una tribu jugando a **ARK: Survival Ascended** en servidores modificados (x10).

## 🚀 Funcionalidades Principales

*   **⚔️ Dashboard de Guerra (Warfare)**
    *   **K/D/A Tracker:** Ranking automatizado ("El Más Manco") que lee los logs in-game para puntuar asesinos y víctimas excluyendo el Fuego Amigo.
    *   **Blacklist:** Base de datos auto-actualizable in-game para trackear a jugadores non gratos, su tribu y sus bases.
    *   **Alertas SOS:** Sistema de pings estructurados para avisos de Raideo, Soaking, FOB o Scouting enemigo.
*   **🧬 Crianza y Mutaciones**
    *   **Gestión de Líneas:** Tablón visual para compartir y registrar por especie los puntos en Vida, Melee, Peso, etc.
    *   **Temporizadores:** Sistema de alarmas de maduración/impronta con avisos al usuario y auto-eliminación de notificaciones.
*   **🕵️ Inteligencia (K4Ultra & Scouting)**
    *   Analizador de actividad de jugadores rivales y mapas para predecir alianzas ("Relationships") mediante algoritmos de co-ocurrencia.
*   **🎁 Tareas y Mantenimiento**
    *   Recordatorios diarios (Configurables por Zona Horaria) para canjear Puntos de Tienda (Ark Shop/Vote Rewards).
    *   Gestor de Tareas `/todo` integrado en Discord (Pendiente, En Curso, Terminado).

## 🛠️ Tecnologías Utilizadas

*   **Python 3.10+** (Asíncrono total)
*   **Discord.py** (App Commands, Modals, Views, Selects)
*   **aiosqlite** (Base de datos local ultrarrápida incrustada)
*   Integraciones con Webhooks nativos del servidor (Lectura de kills de Super Structures o mods similares).

> *Este código es de uso exclusivamente privado.*
