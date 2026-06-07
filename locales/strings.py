"""Catálogo de cadenas de UI cortas, indexado por idioma.

Estructura: ``STRINGS[lang][key] = "plantilla"``. Las plantillas pueden contener
placeholders de ``str.format`` (ej. ``"{total} tareas"``).

Convención de claves: ``modulo.subclave`` (ej. ``todo.title``, ``blacklist.footer``).

Este catálogo se rellena de forma incremental según avanzan las fases del soporte
bilingüe. La función ``utils.i18n.t`` cae a español si falta una clave en inglés.
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "es": {},
    "en": {},
}
