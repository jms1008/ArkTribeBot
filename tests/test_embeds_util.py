"""Tests del helper utils.embeds."""

import discord
import pytest

from utils.embeds import _BLANK, DEFAULT_WIDTH_CHARS, apply_uniform_width


def test_adds_width_line_to_empty_description():
    embed = discord.Embed(title="X")
    apply_uniform_width(embed)
    assert embed.description is not None
    assert _BLANK in embed.description


def test_adds_width_line_after_existing_description():
    embed = discord.Embed(title="X", description="Contenido visible")
    apply_uniform_width(embed)
    assert embed.description.startswith("Contenido visible")
    assert _BLANK in embed.description
    # La línea con blank queda al final.
    lines = embed.description.split("\n")
    assert _BLANK in lines[-1]
    assert "Contenido visible" in lines[0]


def test_is_idempotent():
    """Llamar dos veces no debe duplicar la línea de relleno."""
    embed = discord.Embed(title="X", description="Texto")
    apply_uniform_width(embed)
    desc_once = embed.description
    apply_uniform_width(embed)
    desc_twice = embed.description
    assert desc_once == desc_twice


def test_width_chars_param_changes_line_length():
    embed = discord.Embed(title="X")
    apply_uniform_width(embed, width_chars=20)
    line_20 = embed.description

    embed2 = discord.Embed(title="X")
    apply_uniform_width(embed2, width_chars=80)
    line_80 = embed2.description

    # La línea con 80 chars debe ser más larga que la de 20.
    assert len(line_80) > len(line_20)


def test_default_width_is_constant():
    """El valor por defecto debe coincidir con la constante exportada."""
    embed = discord.Embed(title="X")
    apply_uniform_width(embed)
    # La línea contiene exactamente DEFAULT_WIDTH_CHARS caracteres BLANK.
    assert embed.description.count(_BLANK) == DEFAULT_WIDTH_CHARS


def test_returns_same_embed_for_chaining():
    embed = discord.Embed(title="X")
    result = apply_uniform_width(embed)
    assert result is embed


def test_replaces_old_width_line_with_new_width():
    """Cambiar el width sustituye la línea anterior, no acumula."""
    embed = discord.Embed(title="X", description="Texto")
    apply_uniform_width(embed, width_chars=20)
    apply_uniform_width(embed, width_chars=60)

    # Solo debe haber UNA línea con BLANK.
    lines_with_blank = [line for line in embed.description.split("\n") if _BLANK in line]
    assert len(lines_with_blank) == 1
    # Y debe tener exactamente 60 BLANK chars (no 80 = 20+60).
    assert embed.description.count(_BLANK) == 60
