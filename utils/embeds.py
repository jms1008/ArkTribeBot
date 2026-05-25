"""Utilidades visuales para embeds.

Discord no expone un parámetro de "ancho mínimo" para los embeds: cada uno se
ajusta al contenido más ancho de su ``description`` o ``fields``. Esto hace que
embeds con poco contenido queden notablemente más estrechos que los grandes.

``apply_uniform_width`` usa el truco del **PNG transparente** como ``set_image``:
Discord renderiza la imagen al ancho disponible del embed → la imagen es 100%
transparente y de 1 píxel de alto, así que es **invisible** pero fuerza el
ancho mínimo del embed al tamaño nativo de la imagen.

La imagen vive en ``assets/spacer.png`` (1200×1 px, RGBA todo cero) y se sirve
vía GitHub raw, que es estable y no depende de servicios externos.

Uso:

.. code-block:: python

    from utils.embeds import apply_uniform_width

    embed = discord.Embed(title="...", description="...")
    apply_uniform_width(embed)
    await channel.send(embed=embed)
"""

from __future__ import annotations

import discord

# URL del PNG transparente 1200×1 hospedado en GitHub raw.
# Si se renombra la rama o el repo, actualizar aquí.
SPACER_URL = "https://raw.githubusercontent.com/jms1008/ArkTribeBot/main/assets/spacer.png"


def apply_uniform_width(embed: discord.Embed) -> discord.Embed:
    """Fuerza un ancho mínimo uniforme en el embed via PNG transparente.

    Idempotente: aplicada varias veces no duplica nada (``set_image`` reemplaza).

    Args:
        embed: El embed a modificar (in-place).

    Returns:
        El mismo embed, para permitir encadenado.
    """
    embed.set_image(url=SPACER_URL)
    return embed
