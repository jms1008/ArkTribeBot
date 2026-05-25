"""Tests del módulo utils.bus (constantes y conexión productor/consumidor)."""

import asyncio

import discord
import pytest
from discord.ext import commands

from utils import bus


class TestEventConstants:
    def test_no_event_has_on_prefix(self):
        """discord.py añade 'on_' automáticamente — los nombres no deben llevarlo."""
        for event in bus.ALL_EVENTS:
            assert not event.startswith("on_"), (
                f"{event} no debe llevar prefijo 'on_'; discord.py lo añade al buscar listeners"
            )

    def test_all_events_listed(self):
        """ALL_EVENTS debe contener todas las constantes exportadas."""
        expected = {
            bus.BLACKLIST_UPDATED,
            bus.KDA_UPDATED,
            bus.SCOUTING_UPDATED,
            bus.TODO_UPDATED,
            bus.BREEDING_UPDATED,
            bus.TRUSTED_MEMBERS_CHANGED,
        }
        assert set(bus.ALL_EVENTS) == expected

    def test_events_are_unique(self):
        assert len(set(bus.ALL_EVENTS)) == len(bus.ALL_EVENTS)


async def _make_bot() -> commands.Bot:
    """Crea un bot con su loop sentinel inicializado para tests."""
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    # discord.py 2.x bloquea bot.loop hasta que se llame al setup async hook.
    await bot._async_setup_hook()
    return bot


@pytest.mark.asyncio
async def test_dispatch_invokes_listener():
    """Verifica que bot.dispatch('blacklist_updated', x) llama a on_blacklist_updated."""
    bot = await _make_bot()
    try:
        received: list[int] = []

        class _TestCog(commands.Cog):
            @commands.Cog.listener()
            async def on_blacklist_updated(self, guild_id: int):
                received.append(guild_id)

        await bot.add_cog(_TestCog())
        bot.dispatch(bus.BLACKLIST_UPDATED, 12345)
        await asyncio.sleep(0.05)  # tick para que discord.py procese listeners
        assert received == [12345]
    finally:
        await bot.close()


@pytest.mark.asyncio
async def test_dispatch_with_multiple_listeners():
    """Múltiples cogs pueden escuchar el mismo evento."""
    bot = await _make_bot()
    try:
        calls: list[str] = []

        class _CogA(commands.Cog):
            @commands.Cog.listener()
            async def on_kda_updated(self, guild_id: int):
                calls.append(f"A:{guild_id}")

        class _CogB(commands.Cog):
            @commands.Cog.listener()
            async def on_kda_updated(self, guild_id: int):
                calls.append(f"B:{guild_id}")

        await bot.add_cog(_CogA())
        await bot.add_cog(_CogB())
        bot.dispatch(bus.KDA_UPDATED, 99)
        await asyncio.sleep(0.05)
        assert sorted(calls) == ["A:99", "B:99"]
    finally:
        await bot.close()
