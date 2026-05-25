"""Utilidades visuales para embeds.

Discord no tiene un parámetro de "ancho mínimo" para los embeds: se ajustan al
contenido más ancho de su description o fields. Cuando dos embeds del bot
tienen contenido de longitud muy distinta, se ven con anchos visibles distintos
y queda inconsistente.

``apply_uniform_width`` añade una línea invisible al final del ``description``
(BRAILLE PATTERN BLANK ``U+2800`` dentro de backticks para forzar monospace y
ancho consistente). Visualmente la línea no se ve, pero Discord usa su longitud
para calcular el ancho del embed → todos los embeds del bot quedan al mismo
ancho mínimo.

Uso:

.. code-block:: python

    from utils.embeds import apply_uniform_width

    embed = discord.Embed(title="...", description="...")
    apply_uniform_width(embed)
    await channel.send(embed=embed)
"""

from __future__ import annotations

import discord

# Carácter invisible (BRAILLE PATTERN BLANK). En fuente monospace tiene ancho
# fijo de 1 char, lo que nos permite forzar el ancho del embed.
_BLANK = "⠀"

# Ancho visual deseado en caracteres monoespaciados. Discord renderiza el embed
# al ancho del contenido más largo; 40 caracteres es un buen compromiso entre
# "embed lo bastante ancho para verse parejo" y "no demasiado en pantallas
# pequeñas / móvil".
DEFAULT_WIDTH_CHARS = 40

# Cadena exacta que se inserta al final del description. Se guarda como
# constante para poder detectar y no duplicarla si la función se llama dos
# veces sobre el mismo embed.
_WIDTH_LINE = "`" + _BLANK * DEFAULT_WIDTH_CHARS + "`"


def apply_uniform_width(embed: discord.Embed, *, width_chars: int = DEFAULT_WIDTH_CHARS) -> discord.Embed:
    """Añade una línea invisible al final del ``description`` para forzar un
    ancho mínimo uniforme entre embeds del bot.

    La función es idempotente: aplicada dos veces no duplica la línea.

    Args:
        embed: El embed a modificar (in-place).
        width_chars: Ancho deseado en chars monoespaciados (default: 40).

    Returns:
        El mismo embed, para permitir encadenado.
    """
    line = "`" + _BLANK * width_chars + "`"

    current = embed.description or ""
    # Idempotencia: si ya tiene una línea de relleno (incluso de otro ancho),
    # se reemplaza por la nueva.
    if _BLANK in current:
        lines_in = current.split("\n")
        lines_in = [line_ for line_ in lines_in if _BLANK not in line_]
        current = "\n".join(lines_in)

    if current:
        embed.description = current + "\n" + line
    else:
        embed.description = line
    return embed
