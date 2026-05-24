"""Smoke tests: verifican que el bot arranca y todos los cogs esperados se cargan.

Estos tests son la red de seguridad para evitar el tipo de regresión que rompió
K4Ultra silenciosamente cuando se convirtió en paquete (commit ``ddba5fd``):
la suite Python pasaba pero el cog no se cargaba en producción, y el bug solo
se notó cuando los usuarios pulsaron un botón.

Si añades un nuevo cog, añade su nombre de clase a ``EXPECTED_COGS``.
"""

from __future__ import annotations

import pytest

# Conjunto canónico de cogs que el bot debe cargar para considerarse sano.
EXPECTED_COGS: frozenset[str] = frozenset(
    {
        "Admin",
        "Alarma",
        "Backup",
        "Breeding",
        "DailyPoints",
        "Events",
        "K4Ultra",
        "LogProcessor",
        "Management",
        "Scouting",
        "ServerStatus",
        "Warfare",
    }
)


@pytest.fixture
def _bot_env(monkeypatch, tmp_path):
    """Aísla el bot: token y DB temporales para que el arranque no toque producción."""
    monkeypatch.setenv("DISCORD_TOKEN", "fake_token_for_smoke_test")
    monkeypatch.setenv("APPLICATION_ID", "0")
    return tmp_path


@pytest.mark.asyncio
async def test_all_expected_cogs_load(_bot_env):
    """El bot debe arrancar e instanciar TODOS los cogs esperados."""
    # Import diferido para que monkeypatch del env esté aplicado al cargar main.
    from main import ArkTribeBot

    bot = ArkTribeBot()
    bot.db_name = str(_bot_env / "smoke.db")
    try:
        await bot.init_db()
        await bot.load_extensions()

        loaded = set(bot.cogs.keys())
        missing = EXPECTED_COGS - loaded

        assert not missing, f"Cogs faltantes en el bot: {sorted(missing)}. Cargados: {sorted(loaded)}."
    finally:
        # Cerrar tasks de los loops y la DB persistente para no leakar.
        for cog in list(bot.cogs.values()):
            try:
                await bot.remove_cog(cog.qualified_name)
            except Exception:
                pass
        await bot.close()


@pytest.mark.asyncio
async def test_k4ultra_is_a_loaded_cog_after_package_refactor(_bot_env):
    """Regresión específica de commit 366363b.

    Tras convertir cogs/k4ultra.py en paquete (cogs/k4ultra/), el cog se
    dejó de cargar porque el loader buscaba 'def setup(' literal y el
    __init__.py solo importaba setup. Este test bloquea ese tipo de regresión.
    """
    from main import ArkTribeBot

    bot = ArkTribeBot()
    bot.db_name = str(_bot_env / "k4u.db")
    try:
        await bot.init_db()
        await bot.load_extensions()

        cog = bot.get_cog("K4Ultra")
        assert cog is not None, "K4Ultra debe estar registrado tras load_extensions"
        # Verifica que el callback que falla en producción está disponible.
        assert hasattr(cog, "generate_k4ultra_embed")
        assert hasattr(cog, "gather_player_data")
    finally:
        await bot.close()
