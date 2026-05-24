"""Tests de is_authorized_admin (función crítica de seguridad)."""
import importlib

import aiosqlite
import pytest


@pytest.fixture
def _patch_owner_id(monkeypatch):
    """Permite controlar BOT_OWNER_ID en cada test."""

    def _set(value: str | None):
        if value is None:
            monkeypatch.delenv("BOT_OWNER_ID", raising=False)
        else:
            monkeypatch.setenv("BOT_OWNER_ID", value)

    return _set


@pytest.mark.asyncio
async def test_guild_administrator_is_authorized(mocker, _patch_owner_id):
    _patch_owner_id(None)
    main = importlib.import_module("main")

    bot = main.ArkTribeBot.__new__(main.ArkTribeBot)
    bot.db_name = ":memory:"

    interaction = mocker.MagicMock()
    interaction.user.guild_permissions.administrator = True
    interaction.user.id = 99
    interaction.guild_id = None

    assert await bot.is_authorized_admin(interaction) is True


@pytest.mark.asyncio
async def test_env_owner_is_authorized_even_without_admin(mocker, _patch_owner_id):
    _patch_owner_id("777")
    main = importlib.import_module("main")

    bot = main.ArkTribeBot.__new__(main.ArkTribeBot)
    bot.db_name = ":memory:"

    interaction = mocker.MagicMock()
    interaction.user.guild_permissions.administrator = False
    interaction.user.id = 777
    interaction.guild_id = None

    assert await bot.is_authorized_admin(interaction) is True


@pytest.mark.asyncio
async def test_random_user_without_admin_is_rejected(mocker, _patch_owner_id):
    _patch_owner_id("777")
    main = importlib.import_module("main")

    bot = main.ArkTribeBot.__new__(main.ArkTribeBot)
    bot.db_name = ":memory:"

    interaction = mocker.MagicMock()
    interaction.user.guild_permissions.administrator = False
    interaction.user.id = 12345  # No es owner ni admin del guild.
    interaction.guild_id = None  # Sin guild → no se consulta guild_config.

    assert await bot.is_authorized_admin(interaction) is False


@pytest.mark.asyncio
async def test_invalid_env_owner_id_is_treated_as_zero(mocker, _patch_owner_id, tmp_path):
    """Si BOT_OWNER_ID no es numérico no debe romper ni autorizar a id=0."""
    _patch_owner_id("not-a-number")
    main = importlib.import_module("main")

    db_path = str(tmp_path / "auth.db")
    # Tabla mínima necesaria — el bot la consulta cuando hay guild_id.
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE guild_config (guild_id INTEGER PRIMARY KEY, admin_role_id INTEGER, bot_owner_id INTEGER)"
        )
        await db.commit()

    bot = main.ArkTribeBot.__new__(main.ArkTribeBot)
    bot.db_name = db_path

    interaction = mocker.MagicMock()
    interaction.user.guild_permissions.administrator = False
    interaction.user.id = 0  # Coincidiría con un fallback mal configurado.
    interaction.guild_id = 1

    assert await bot.is_authorized_admin(interaction) is False
