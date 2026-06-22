"""Tests del cog Management: ciclo completo de To-Do (añadir, reclamar, eliminar)."""

import pytest

from cogs.management import (
    AddTaskModal,
    ClaimTaskModal,
    DeleteTaskModal,
    Management,
    build_todo_embed_view,
)


@pytest.fixture
async def mgmt_cog(mock_bot):
    return Management(mock_bot)


@pytest.fixture
def _no_dashboard_refresh(mocker):
    """Silencia update_all_dashboards (requeriría canales Discord reales)."""
    mocker.patch("cogs.management.update_all_dashboards", new=mocker.AsyncMock())


@pytest.fixture(autouse=True)
def _skip_auto_delete_sleeps(mocker):
    """Los modales del cog hacen ``await asyncio.sleep(5)`` para auto-borrar el
    mensaje de feedback. En tests lo saltamos para no tardar segundos por modal.
    """
    real_sleep = __import__("asyncio").sleep

    async def fast_sleep(delay, *args, **kwargs):
        return await real_sleep(0)

    mocker.patch("cogs.management.asyncio.sleep", new=fast_sleep)


@pytest.mark.asyncio
async def test_add_task_inserts_pending_row(mgmt_cog, mock_interaction, mock_bot, _no_dashboard_refresh):
    await mock_bot.init_mock_db()

    modal = AddTaskModal(mock_bot)
    modal.tarea_content._value = "Recoger metal en Aberration"

    await modal.on_submit(mock_interaction)

    row = await mock_bot.db.fetchone(
        "SELECT tarea, estado FROM todos WHERE guild_id = ?",
        (mock_interaction.guild_id,),
    )
    assert row is not None
    assert row["tarea"] == "Recoger metal en Aberration"
    # Nueva tarea entra en estado por defecto.
    assert row["estado"] == "Pendiente"


@pytest.mark.asyncio
async def test_claim_task_assigns_user_and_moves_to_in_progress(
    mgmt_cog, mock_interaction, mock_bot, _no_dashboard_refresh
):
    await mock_bot.init_mock_db()
    # Tarea preexistente sin asignar.
    cursor = await mock_bot.db.execute(
        "INSERT INTO todos (guild_id, task_number, tarea) VALUES (?, ?, ?)",
        (mock_interaction.guild_id, 1, "Construir torreta"),
    )
    await mock_bot.db.commit()

    modal = ClaimTaskModal(mock_bot)
    modal.task_id._value = "1"  # task_number, not global id
    await modal.on_submit(mock_interaction)

    row = await mock_bot.db.fetchone(
        "SELECT asignado_a, estado FROM todos WHERE task_number = ? AND guild_id = ?",
        (1, mock_interaction.guild_id),
    )
    assert row is not None
    assert row["estado"] == "En Progreso"
    assert f"<@{mock_interaction.user.id}>" in row["asignado_a"]


@pytest.mark.asyncio
async def test_claim_task_toggles_off_when_already_assigned(
    mgmt_cog, mock_interaction, mock_bot, _no_dashboard_refresh
):
    """Pulsar 'Reclamar' dos veces como mismo usuario debe quitarlo de la lista."""
    await mock_bot.init_mock_db()
    cursor = await mock_bot.db.execute(
        "INSERT INTO todos (guild_id, task_number, tarea) VALUES (?, ?, ?)",
        (mock_interaction.guild_id, 1, "Tarea A"),
    )
    await mock_bot.db.commit()

    modal = ClaimTaskModal(mock_bot)
    modal.task_id._value = "1"
    await modal.on_submit(mock_interaction)
    # Segundo claim del mismo usuario.
    await modal.on_submit(mock_interaction)

    row = await mock_bot.db.fetchone(
        "SELECT asignado_a FROM todos WHERE task_number = ? AND guild_id = ?",
        (1, mock_interaction.guild_id),
    )
    # Ya no debe contener su mention.
    assert f"<@{mock_interaction.user.id}>" not in (row["asignado_a"] or "")


@pytest.mark.asyncio
async def test_claim_task_rejects_invalid_id(mgmt_cog, mock_interaction, mock_bot):
    await mock_bot.init_mock_db()

    modal = ClaimTaskModal(mock_bot)
    modal.task_id._value = "no_es_numero"
    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    args, _ = mock_interaction.response.send_message.call_args
    assert "número" in args[0] or "numero" in args[0].lower()


@pytest.mark.asyncio
async def test_claim_task_rejects_unknown_id(mgmt_cog, mock_interaction, mock_bot):
    await mock_bot.init_mock_db()

    modal = ClaimTaskModal(mock_bot)
    modal.task_id._value = "99999"
    await modal.on_submit(mock_interaction)

    mock_interaction.response.send_message.assert_called_once()
    args, _ = mock_interaction.response.send_message.call_args
    assert "no existe" in args[0].lower()


@pytest.mark.asyncio
async def test_delete_task_removes_row(mgmt_cog, mock_interaction, mock_bot, _no_dashboard_refresh):
    await mock_bot.init_mock_db()
    cursor = await mock_bot.db.execute(
        "INSERT INTO todos (guild_id, task_number, tarea) VALUES (?, ?, ?)",
        (mock_interaction.guild_id, 1, "Tarea a borrar"),
    )
    await mock_bot.db.commit()

    modal = DeleteTaskModal(mock_bot)
    modal.task_id._value = "1"
    await modal.on_submit(mock_interaction)

    row = await mock_bot.db.fetchone(
        "SELECT id FROM todos WHERE task_number = ? AND guild_id = ?",
        (1, mock_interaction.guild_id),
    )
    assert row is None


@pytest.mark.asyncio
async def test_delete_task_isolates_by_guild(mgmt_cog, mock_interaction, mock_bot, _no_dashboard_refresh):
    """Un usuario no puede borrar tareas de OTRO guild aunque conozca el ID."""
    await mock_bot.init_mock_db()
    cursor = await mock_bot.db.execute(
        "INSERT INTO todos (guild_id, task_number, tarea) VALUES (?, ?, ?)",
        (mock_interaction.guild_id + 1, 1, "De otro guild"),
    )
    await mock_bot.db.commit()

    modal = DeleteTaskModal(mock_bot)
    modal.task_id._value = "1"  # task_number 1 exists but in another guild
    await modal.on_submit(mock_interaction)

    # La tarea debe seguir existiendo.
    row = await mock_bot.db.fetchone(
        "SELECT id FROM todos WHERE task_number = ? AND guild_id = ?",
        (1, mock_interaction.guild_id + 1),
    )
    assert row is not None


class TestBuildTodoEmbedView:
    """build_todo_embed_view es relativamente pura (mock bot solo para View)."""

    def test_empty_list_shows_celebration(self, mock_bot):
        embed, page, view = build_todo_embed_view(mock_bot, rows=[], page=0)
        assert "Sin tareas" in embed.description or "al día" in embed.description
        assert page == 0

    def test_pagination_clamps_high_page(self, mock_bot):
        # Sólo 1 tarea → siempre página 0.
        rows = [{"id": 1, "task_number": 1, "tarea": "X", "asignado_a": None, "estado": "Pendiente"}]
        embed, page, _ = build_todo_embed_view(mock_bot, rows=rows, page=5)
        assert page == 0
