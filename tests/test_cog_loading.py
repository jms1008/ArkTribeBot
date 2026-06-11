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
async def test_tribu_group_consolidates_tribe_commands(_bot_env):
    """El grupo /tribu reúne toda la gestión de tribu y los comandos sueltos
    antiguos (/tribu_propia, /fijar_tribu, /perfil_tribu, /aliados, etc.) ya no
    existen como comandos de nivel superior (consolidación, reemplazo en seco).
    """
    import discord.app_commands as ac

    from main import ArkTribeBot

    bot = ArkTribeBot()
    bot.db_name = str(_bot_env / "tribu.db")
    try:
        await bot.init_db()
        await bot.load_extensions()

        # Recolectar todos los nombres de comando (planos, con ruta de grupos).
        names: list[str] = []

        def _walk(cmd, prefix: str = ""):
            if isinstance(cmd, ac.Group):
                for sub in cmd.commands:
                    _walk(sub, f"{prefix}{cmd.name} ")
            else:
                names.append(f"{prefix}{cmd.name}".strip())

        for cmd in bot.tree.get_commands():
            _walk(cmd)

        # El grupo /tribu debe tener los 13 subcomandos esperados.
        expected_subs = {
            "tribu propia crear",
            "tribu propia modificar",
            "tribu propia borrar",
            "tribu aliada crear",
            "tribu aliada modificar",
            "tribu aliada borrar",
            "tribu aliada lista",
            "tribu fijar",
            "tribu desfijar",
            "tribu fusionar",
            "tribu separar",
            "tribu limpiar",
            "tribu lista",
            "tribu miembro crear",
            "tribu miembro borrar",
        }
        assert expected_subs <= set(names), f"Faltan subcomandos de /tribu: {expected_subs - set(names)}"

        # Los nombres planos viejos NO deben existir.
        old_names = {
            "tribu_propia",
            "fijar_tribu",
            "unfijar_tribu",
            "perfil_tribu",
            "fusionar_perfiles",
            "k4ultra_merge",
            "k4ultra_split",
            "k4ultra_cleanup",
            "aliados",
        }
        leftover = old_names & set(names)
        assert not leftover, f"Comandos viejos que deberían haberse eliminado: {leftover}"
    finally:
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
