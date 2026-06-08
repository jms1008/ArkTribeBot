"""Sistema de internacionalización (i18n) por servidor.

Dos idiomas: español (``es``, por defecto) e inglés (``en``).

El idioma se configura **por guild** en ``guild_config.language`` con uno de:
- ``'es'``         → todo en español.
- ``'en_periodic'`` → dashboards periódicos en inglés; comandos y chistes en español.
- ``'en_total'``    → absolutamente todo en inglés.

La resolución depende del *scope* desde el que se llama:
- ``scope="periodic"`` (dashboards auto-actualizables) → inglés si el modo es
  ``en_periodic`` o ``en_total``.
- ``scope="command"`` (respuestas de comandos, frases sarcásticas) → inglés solo si
  el modo es ``en_total``.

Uso típico:

    from utils.i18n import resolve_lang, t

    lang = await resolve_lang(bot, guild_id, "periodic")
    embed.title = t("todo.title", lang)
    embed.set_footer(text=t("todo.footer", lang, total=total))
"""

from __future__ import annotations

import logging

from locales.strings import STRINGS

logger = logging.getLogger("ArkTribeBot")

DEFAULT_LANG = "es"
SUPPORTED = ("es", "en")

# Valores válidos de guild_config.language.
MODE_ES = "es"
MODE_EN_PERIODIC = "en_periodic"
MODE_EN_TOTAL = "en_total"
VALID_MODES = (MODE_ES, MODE_EN_PERIODIC, MODE_EN_TOTAL)

# Caché en memoria del modo por guild: {guild_id: mode}. Se invalida al cambiar
# /idioma para que los dashboards reflejen el cambio sin esperar al loop.
_mode_cache: dict[int, str] = {}


def invalidate_lang_cache(guild_id: int | None = None) -> None:
    """Invalida la caché del modo de idioma de un guild (o de todos si es None)."""
    if guild_id is None:
        _mode_cache.clear()
    else:
        _mode_cache.pop(guild_id, None)


async def get_guild_mode(bot, guild_id: int | None) -> str:
    """Devuelve el modo bruto del guild (``es`` / ``en_periodic`` / ``en_total``).

    Cae a ``MODE_ES`` si no hay guild, no hay config o la columna no existe.
    """
    if guild_id is None:
        return MODE_ES
    if guild_id in _mode_cache:
        return _mode_cache[guild_id]

    mode = MODE_ES
    try:
        db = getattr(bot, "db", None)
        if db is not None:
            row = await db.fetchone(
                "SELECT language FROM guild_config WHERE guild_id = ?", (guild_id,)
            )
            if row is not None and row["language"] in VALID_MODES:
                mode = row["language"]
    except Exception as e:  # columna ausente, DB no lista, etc.
        logger.debug(f"[i18n] No se pudo leer language de guild {guild_id}: {e}")

    _mode_cache[guild_id] = mode
    return mode


async def get_user_lang(bot, guild_id: int | None, user_id: int | None) -> str | None:
    """Preferencia de idioma personal de un usuario en un guild, o ``None``.

    Configurable vía /tribu miembro. Sobrescribe el idioma de servidor SOLO para
    las respuestas de comandos dirigidas a ese usuario (scope ``command``).
    """
    if guild_id is None or user_id is None:
        return None
    try:
        db = getattr(bot, "db", None)
        if db is None:
            return None
        row = await db.fetchone(
            "SELECT lang FROM user_language WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        if row is not None and row["lang"] in SUPPORTED:
            return row["lang"]
    except Exception as e:  # tabla ausente, DB no lista, etc.
        logger.debug(f"[i18n] No se pudo leer user_language ({guild_id}/{user_id}): {e}")
    return None


async def resolve_lang(bot, guild_id: int | None, scope: str, user_id: int | None = None) -> str:
    """Resuelve el idioma efectivo (``"es"`` / ``"en"``) para un *scope*.

    - ``scope="periodic"`` (dashboards compartidos) → ``"en"`` si modo ∈
      {en_periodic, en_total}. La preferencia por usuario NO aplica aquí porque
      los paneles los ve toda la tribu.
    - ``scope="command"`` (respuestas dirigidas a un usuario) → si ese usuario
      tiene preferencia personal, manda; si no, ``"en"`` solo si modo == en_total.
    """
    mode = await get_guild_mode(bot, guild_id)
    if scope == "periodic":
        return "en" if mode in (MODE_EN_PERIODIC, MODE_EN_TOTAL) else "es"

    # scope == "command": preferencia personal del usuario tiene prioridad.
    if user_id is not None:
        pref = await get_user_lang(bot, guild_id, user_id)
        if pref is not None:
            return pref
    return "en" if mode == MODE_EN_TOTAL else "es"


def t(key: str, lang: str = "es", /, **fmt) -> str:
    """Traduce ``key`` al idioma ``lang``.

    Estrategia de fallback (nunca lanza):
    1. ``STRINGS[lang][key]`` si existe.
    2. ``STRINGS['es'][key]`` como respaldo.
    3. la propia ``key`` si no está en ningún catálogo.

    Si se pasan kwargs, se aplican con ``str.format(**fmt)``. Si el formato falla
    (placeholder ausente), se devuelve la plantilla sin formatear.
    """
    table = STRINGS.get(lang) or STRINGS.get(DEFAULT_LANG, {})
    template = table.get(key)
    if template is None:
        template = STRINGS.get(DEFAULT_LANG, {}).get(key, key)
    if not fmt:
        return template
    try:
        return template.format(**fmt)
    except (KeyError, IndexError, ValueError) as e:
        logger.debug(f"[i18n] Formato falló para key='{key}' lang='{lang}': {e}")
        return template
