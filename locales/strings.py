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
        # --- /idioma ---
        "idioma.set.en_total": (
            "🌐 Language set: **English (everything)**.\n"
            "The entire bot — dashboards, command replies and messages — will now "
            "be shown in English."
        ),
    },
}
