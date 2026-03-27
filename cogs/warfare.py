import os
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
import logging
from cogs.server_status import get_guild_servers

logger = logging.getLogger("ArkTribeBot")


PAGE_SIZE = 10  # Entradas por página en el dashboard de Blacklist


def build_blacklist_embed(rows: list, page: int = 0) -> discord.Embed:
    """Construye el embed de la Blacklist en formato compacto paginado."""
    total = len(rows)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = rows[start : start + PAGE_SIZE]

    embed = discord.Embed(
        title="☠️ Blacklist de Tribu",
        color=discord.Color.dark_grey(),
    )

    if not rows:
        embed.description = "No hay jugadores en la lista negra.\n💡 Usa el botón **Añadir** para registrar uno."
    else:
        lines = []
        current_section = None

        for row in chunk:
            # Safely check if 'is_enemy' column exists in this row, default to 1 if missing in old schema
            is_enemy = row["is_enemy"] if "is_enemy" in row.keys() else 1

            # Separador de secciones
            if is_enemy == 1 and current_section != "Enemigos":
                lines.append("\n🔴 **ENEMIGOS** 🔴")
                lines.append("────────────────")
                current_section = "Enemigos"
            elif is_enemy == 0 and current_section != "Neutrales":
                lines.append("\n⚪ **REGISTROS K4ULTRA (NEUTRALES)** ⚪")
                lines.append("────────────────")
                current_section = "Neutrales"

            nota_corta = (
                (row["notes"][:30] + "...")
                if row["notes"] and len(row["notes"]) > 30
                else (row["notes"] or "")
            )

            emoji = "🔴" if is_enemy == 1 else "⚪"
            lines.append(
                f"`#{row['id']}` {emoji} **{row['player']}** | {row['tribe']} | {row['map']}\n"
                f"    📝 {nota_corta}"
            )

        embed.description = "\n".join(lines).strip()
        embed.set_footer(
            text=f"Página {page + 1}/{total_pages} • {total} entradas totales"
        )

    return embed, page, total_pages


async def update_blacklist_dashboards(bot, guild_id: int, page: int = 0):
    """Actualiza todos los mensajes de lista negra (dashboards)."""

    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM blacklist_messages WHERE guild_id = ?", (guild_id,)
        )
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Recuperación de registros de la Blacklist
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM blacklist WHERE guild_id = ? ORDER BY is_enemy DESC, id DESC",
            (guild_id,),
        )
        rows = await cursor.fetchall()

    embed, current_page, total_pages = build_blacklist_embed(rows, page)
    view = BlacklistView(bot, rows, current_page)
    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                await message.edit(embed=embed, view=view)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            logger.error(f"Error actualizando blacklist dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos o inaccesibles
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM blacklist_messages WHERE id = ?", (mid,))
            await db.commit()


async def update_kda_dashboards(bot, guild_id: int):
    """Actualiza todos los mensajes persistentes del Ranking KDA (El Más Manco)."""
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM kda_messages WHERE guild_id = ?", (guild_id,)
        )
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Generación del Leaderboard con cálculo dinámico de K/D
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        # Ordenación ascendente por K/D (Peor ratio = "El Más Manco").
        # Prevención de división por cero tratando muertes=0 como 1 lógicamente en la consulta.
        cursor = await db.execute(
            """
            SELECT player_name, kills, deaths,
                   CAST(kills AS FLOAT) / CASE WHEN deaths = 0 THEN 1 ELSE deaths END as kd_ratio
            FROM tribe_kda
            WHERE guild_id = ?
            ORDER BY kd_ratio ASC, deaths DESC
        """,
            (guild_id,),
        )
        rows = await cursor.fetchall()

    if not rows:
        embed = discord.Embed(
            title="☠️ Ranking de El Más Manco",
            description="Todavía no hay bajas registradas en la tribu.",
            color=discord.Color.dark_red(),
        )
        embed.set_footer(text="💡 Añade personajes con /ranking_char_add")
    else:
        embed = discord.Embed(
            title="☠️ Ranking de El Más Manco (K/D/A)",
            description="La tabla de la vergüenza. Ordenado de **PEOR a MEJOR** Ratio K/D.",
            color=discord.Color.red(),
        )

        medallas = ["🥇", "🥈", "🥉", "💀", "💀", "💀", "💀", "💀", "💀", "💀"]

        for idx, row in enumerate(rows):
            medalla = medallas[idx] if idx < len(medallas) else "🪦"

            kd_ratio = row["kd_ratio"]
            kills = row["kills"]
            deaths = row["deaths"]

            embed.add_field(
                name=f"{medalla} #{idx + 1} | {row['player_name']}",
                value=f"**K/D Ratio:** `{kd_ratio:.2f}`\n⚔️ **Kills:** {kills} | ☠️ **Muertes:** {deaths}",
                inline=False,
            )

        embed.set_footer(
            text="💡 El Bot se actualiza en vivo leyendo los logs del servidor."
        )

    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                await message.edit(embed=embed)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            logger.error(f"Error actualizando KDA dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM kda_messages WHERE id = ?", (mid,))
            await db.commit()


class AddBlacklistModal(discord.ui.Modal, title="Añadir a Blacklist"):
    player = discord.ui.TextInput(
        label="Nombre del Jugador", placeholder="Ej: xXDarkHunterXx"
    )
    tribe = discord.ui.TextInput(
        label="Tribu", placeholder="Ej: Los Malos", required=False
    )
    map_name = discord.ui.TextInput(
        label="Mapa", placeholder="Ej: Fjordur", required=False
    )
    notes = discord.ui.TextInput(
        label="Notas",
        placeholder="Razón del ban o información relevante",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO blacklist (guild_id, player, tribe, map, notes, is_enemy) VALUES (?, ?, ?, ?, ?, 1)",
                (
                    interaction.guild_id,
                    self.player.value,
                    self.tribe.value or "Desconocido",
                    self.map_name.value or "Desconocido",
                    self.notes.value or "",
                ),
            )
            await db.commit()
        await interaction.response.send_message(
            f"✅ **{self.player.value}** añadido a la Blacklist.", ephemeral=True
        )
        await update_blacklist_dashboards(self.bot, interaction.guild_id)


class ModifyBlacklistModal(discord.ui.Modal, title="Modificar entrada de Blacklist"):
    entry_id = discord.ui.TextInput(label="ID de la entrada", placeholder="Número ID")
    campo = discord.ui.TextInput(
        label="Campo a modificar",
        placeholder="player | tribe | map | notes | is_enemy",
    )
    nuevo_valor = discord.ui.TextInput(
        label="Nuevo valor",
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        valid_fields = {"player", "tribe", "map", "notes", "is_enemy"}
        campo = self.campo.value.strip().lower()
        if campo not in valid_fields:
            await interaction.response.send_message(
                f"❌ Campo inválido. Usa: {', '.join(valid_fields)}", ephemeral=True
            )
            return
        try:
            bid = int(self.entry_id.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        valor = self.nuevo_valor.value
        if campo == "is_enemy":
            if valor not in ("0", "1"):
                await interaction.response.send_message(
                    "❌ Para is_enemy, el valor debe ser 0 (Neutral) o 1 (Enemigo).",
                    ephemeral=True,
                )
                return
            valor = int(valor)

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT id FROM blacklist WHERE id = ? AND guild_id = ?",
                (
                    bid,
                    interaction.guild_id,
                ),
            )
            if not await cursor.fetchone():
                await interaction.response.send_message(
                    f"❌ No existe la entrada ID {bid} o no te pertenece.",
                    ephemeral=True,
                )
                return
            await db.execute(
                f"UPDATE blacklist SET {campo} = ? WHERE id = ? AND guild_id = ?",
                (valor, bid, interaction.guild_id),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ ID {bid} actualizado: **{campo}** → {valor}",
            ephemeral=True,
        )
        await update_blacklist_dashboards(self.bot, interaction.guild_id)


class DeleteBlacklistModal(discord.ui.Modal, title="Eliminar de Blacklist"):
    entry_id = discord.ui.TextInput(
        label="ID de la Entrada", placeholder="Número ID", min_length=1
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bid = int(self.entry_id.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM blacklist WHERE id = ? AND guild_id = ?",
                (
                    bid,
                    interaction.guild_id,
                ),
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Entrada ID {bid} eliminada.", ephemeral=True
        )
        await update_blacklist_dashboards(self.bot, interaction.guild_id)


async def build_player_detail_embed(
    bot, player_name: str, guild_id: int
) -> discord.Embed:
    """Construye un embed detallado para un jugador, cruzando datos de Blacklist, K4Ultra y KDA."""
    embed = discord.Embed(
        title=f"👤 Expediente: {player_name}", color=discord.Color.dark_orange()
    )

    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row

        # --- 0. Alias y Identidad ---
        cursor = await db.execute(
            "SELECT alias FROM k4ultra_aliases WHERE player_name = ? AND guild_id = ?",
            (player_name, guild_id),
        )
        alias_row = await cursor.fetchone()
        if alias_row:
            embed.title = f"👤 Expediente: {player_name} [{alias_row['alias']}]"

        # --- 1. Datos de Blacklist ---
        cursor = await db.execute(
            "SELECT tribe, map, notes, created_at, last_seen, total_hours FROM blacklist WHERE player = ? AND guild_id = ? LIMIT 1",
            (
                player_name,
                guild_id,
            ),
        )
        bl_row = await cursor.fetchone()

        status_msg = "⚪ Registro Pasivo (K4Ultra)"
        if bl_row:
            status_msg = "🔴 Marcado en Blacklist (Enemigo)"
            embed.color = discord.Color.red()

            notes_str = bl_row["notes"] if bl_row["notes"] else "Ninguna"
            embed.add_field(
                name="🏠 Tribu", value=bl_row["tribe"] or "Desconocida", inline=True
            )
            embed.add_field(
                name="🗺️ Mapa Origen", value=bl_row["map"] or "Desconocido", inline=True
            )
            embed.add_field(name="📝 Notas", value=notes_str, inline=False)
        else:
            embed.description = "Este jugador no está en la blacklist manual."

        # --- 2. Estadísticas de Juego (K4Ultra) ---
        cursor = await db.execute(
            "SELECT SUM(total_minutes) as t_mins FROM k4ultra_playtime WHERE player_name = ? AND guild_id = ?",
            (
                player_name,
                guild_id,
            ),
        )
        playtime_row = await cursor.fetchone()
        total_hours = (
            (playtime_row["t_mins"] / 60)
            if playtime_row and playtime_row["t_mins"]
            else 0.0
        )

        # --- 3. Estado Online y Map Orbit ---
        cursor = await db.execute(
            "SELECT map_name, start_time FROM k4ultra_sessions WHERE player_name = ? AND is_active = 1 AND guild_id = ? LIMIT 1",
            (
                player_name,
                guild_id,
            ),
        )
        active_session = await cursor.fetchone()

        if active_session:
            since = (
                active_session["start_time"][11:16]
                if active_session["start_time"]
                else "?"
            )
            online_str = (
                f"🟢 **En línea** (en {active_session['map_name']} desde {since})"
            )
        else:
            online_str = "🔴 **Desconectado**"

        embed.add_field(name="🔌 Estado Actual", value=online_str, inline=True)
        embed.add_field(
            name="⏱️ Tiempo Total", value=f"{total_hours:.1f} horas", inline=True
        )

        # Historial de Desplazamiento (Últimos 3 mapas)
        cursor = await db.execute(
            "SELECT DISTINCT map_name FROM k4ultra_sessions WHERE player_name = ? AND guild_id = ? ORDER BY start_time DESC LIMIT 3",
            (
                player_name,
                guild_id,
            ),
        )
        orbit_rows = await cursor.fetchall()
        if orbit_rows:
            orbit_str = " -> ".join([r["map_name"] for r in orbit_rows])
            embed.add_field(
                name="🛰️ Órbita (Últimos Mapas)", value=f"`{orbit_str}`", inline=False
            )

        # --- 4. Análisis Horario y Predicción ---
        from datetime import datetime

        now = datetime.now()
        current_hour = now.hour

        cursor = await db.execute(
            "SELECT strftime('%H', start_time) as h, COUNT(*) as c FROM k4ultra_sessions WHERE player_name = ? AND guild_id = ? GROUP BY h",
            (
                player_name,
                guild_id,
            ),
        )
        hour_data = await cursor.fetchall()

        total_sessions = sum(h["c"] for h in hour_data)
        prob = 0
        vulnerability_window = "Indeterminada"

        if total_sessions > 0:
            # Predicción para la próxima hora
            next_hour = (current_hour + 1) % 24
            next_hour_str = f"{next_hour:02d}"

            matches = [h["c"] for h in hour_data if h["h"] == next_hour_str]
            if matches:
                prob = int((matches[0] / total_sessions) * 100)

            # Ventana de Vulnerabilidad (Bloque de 4 horas con menos actividad)
            # Simplificado: buscar la hora con 0 sesiones
            inactive_hours = []
            recorded_hours = {int(h["h"]) for h in hour_data}
            for i in range(24):
                if i not in recorded_hours:
                    inactive_hours.append(i)

            if inactive_hours:
                # Buscar el bloque más largo de horas inactivas
                vulnerability_window = "Madrugada / Variable"
                if len(inactive_hours) >= 4:
                    # Ejemplo: 03:00 - 07:00
                    vulnerability_window = f"Entre {min(inactive_hours):02d}:00 y {max(inactive_hours):02d}:00"

        embed.add_field(
            name="🕒 Ventana Vulnerable", value=vulnerability_window, inline=True
        )
        embed.add_field(name="📈 Prob. Conexión (1h)", value=f"{prob}%", inline=True)

        # --- 5. PVP y Alts ---
        cursor = await db.execute(
            "SELECT kills, deaths FROM tribe_kda WHERE player_name = ? AND guild_id = ?",
            (player_name, guild_id),
        )
        kda_row = await cursor.fetchone()
        kills, deaths, kda = 0, 0, 0.0
        if kda_row:
            kills = kda_row["kills"]
            deaths = kda_row["deaths"]
            kda = round(kills / deaths, 2) if deaths > 0 else float(kills)

        cursor = await db.execute(
            "SELECT character_name FROM tribe_characters WHERE player_name = ? AND guild_id = ?",
            (player_name, guild_id),
        )
        chars = await cursor.fetchall()
        chars_str = (
            ", ".join([f"`{c['character_name']}`" for c in chars])
            if chars
            else "Ninguno"
        )

        embed.add_field(
            name="⚔️ Estadísticas PVP",
            value=f"**Kills:** {kills} | **Deaths:** {deaths} | **KDA:** {kda}",
            inline=False,
        )
        embed.add_field(name="🧑‍🤝‍🧑 Alts / Personajes", value=chars_str, inline=False)

        # --- 6. Grado de Peligro (1-5 💀) ---
        threat = 1
        if total_hours > 50:
            threat += 1
        if kda > 1.5:
            threat += 1
        if bl_row:
            threat += 1
        if kills > 10:
            threat += 1

        threat_str = "💀" * threat + "▫️" * (5 - threat)
        embed.add_field(
            name="🔥 Grado de Peligro", value=f"`{threat_str}`", inline=True
        )
        embed.add_field(name="📑 Tipo de Registro", value=status_msg, inline=True)

        # --- 7. Aliados ---
        cursor = await db.execute(
            """
            SELECT player2 as ally, probability_score FROM k4ultra_relationships WHERE player1 = ? AND guild_id = ?
            UNION
            SELECT player1 as ally, probability_score FROM k4ultra_relationships WHERE player2 = ? AND guild_id = ?
            ORDER BY probability_score DESC LIMIT 3
            """,
            (
                player_name,
                guild_id,
                player_name,
                guild_id,
            ),
        )
        allies = await cursor.fetchall()
        ally_text = (
            "\n".join(
                [f"• **{a['ally']}** ({a['probability_score']}%)" for a in allies]
            )
            if allies
            else "Sin aliados conocidos."
        )
        embed.add_field(name="🤝 Aliados Cercanos", value=ally_text, inline=False)

    return embed


class PlayerDetailSelect(discord.ui.Select):
    def __init__(self, bot, rows):
        self.bot = bot
        options = []
        if not rows:
            # Opcion dummy necesaria para poder registrar la vista persistente al inicio
            options.append(
                discord.SelectOption(label="Cargando...", value="none_dummy_value")
            )
        else:
            for row in rows:
                name = row["player"]
                if len(name) > 100:
                    name = name[:97] + "..."
                tribe_desc = row["tribe"]
                if len(tribe_desc) > 100:
                    tribe_desc = tribe_desc[:97] + "..."
                options.append(
                    discord.SelectOption(
                        label=name,
                        description=f"Tribu: {tribe_desc}",
                        value=row["player"],
                    )
                )

        super().__init__(
            placeholder="Ver detalles de un jugador (K4Ultra)...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
            custom_id="warfare_player_detail_select",
        )

    async def callback(self, interaction: discord.Interaction):
        player_name = self.values[0]
        if player_name == "none_dummy_value":
            await interaction.response.send_message(
                "El menú se está actualizando, cierra este mensaje y reintenta en el dashboard nuevo.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id or 0
        embed = await build_player_detail_embed(self.bot, player_name, guild_id)
        await interaction.followup.send(embed=embed, ephemeral=True)


class BlacklistView(discord.ui.View):
    def __init__(self, bot, rows=None, page: int = 0):
        super().__init__(timeout=None)
        self.bot = bot
        self.rows = rows or []
        self.page = page
        total_pages = max(1, (len(self.rows) + PAGE_SIZE - 1) // PAGE_SIZE)

        # Select de Jugadores para esta página
        start = page * PAGE_SIZE
        chunk = self.rows[start : start + PAGE_SIZE]
        self.add_item(PlayerDetailSelect(bot, chunk))

        # Deshabilitar flechas si no hay páginas
        self.prev_btn.disabled = page == 0
        self.next_btn.disabled = page >= total_pages - 1

    @discord.ui.button(
        label="Añadir",
        style=discord.ButtonStyle.success,
        custom_id="blacklist_add_btn",
        emoji="➕",
        row=0,
    )
    async def add_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(AddBlacklistModal(self.bot))

    @discord.ui.button(
        label="Modificar",
        style=discord.ButtonStyle.secondary,
        custom_id="blacklist_modify_btn",
        emoji="📝",
        row=0,
    )
    async def modify_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            # Buscar el comando global para obtener su ID
            cmds = await self.bot.tree.fetch_commands()
            cmd_id = next((c.id for c in cmds if c.name == "bl_editar"), None)
            
            if cmd_id:
                await interaction.followup.send(
                    f"Haz clic para ver el comando y modificar: </bl_editar:{cmd_id}>",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "📝 Escribe el comando **`/bl_editar`** en el chat para modificar a un jugador.",
                    ephemeral=True
                )
        except Exception:
            await interaction.followup.send("📝 Escribe el comando **`/bl_editar`** en el chat.", ephemeral=True)

    @discord.ui.button(
        label="Eliminar",
        style=discord.ButtonStyle.danger,
        custom_id="blacklist_delete_btn",
        emoji="🗑️",
        row=0,
    )
    async def delete_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(DeleteBlacklistModal(self.bot))

    @discord.ui.button(
        label="◀️",
        style=discord.ButtonStyle.blurple,
        custom_id="blacklist_prev_btn",
        row=2,
    )
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Página anterior de la Blacklist."""
        new_page = max(0, self.page - 1)
        await self._update_page(interaction, new_page)

    @discord.ui.button(
        label="▶️",
        style=discord.ButtonStyle.blurple,
        custom_id="blacklist_next_btn",
        row=2,
    )
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Página siguiente de la Blacklist."""
        total_pages = max(1, (len(self.rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        new_page = min(total_pages - 1, self.page + 1)
        await self._update_page(interaction, new_page)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        """Carga los datos frescos, construye el embed de la página pedida y edita el mensaje."""
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM blacklist WHERE guild_id = ? ORDER BY is_enemy DESC, id DESC",
                (interaction.guild_id,),
            )
            rows = await cursor.fetchall()

        embed, current_page, _ = build_blacklist_embed(rows, new_page)
        new_view = BlacklistView(self.bot, rows, current_page)
        await interaction.response.edit_message(embed=embed, view=new_view)


class Warfare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Rutina de seguridad para asegurar el esquema correcto (Migración legacy)
        asyncio.create_task(self.check_schema())

    async def check_schema(self):
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Comprobación de existencia del esquema antiguo (steam_id vs id)
            try:
                # Intento de lectura de la columna ID (Nuevo estándar)
                await db.execute("SELECT id FROM blacklist LIMIT 1")
            except aiosqlite.OperationalError:
                # Falla de lectura: Detectado esquema antiguo
                logger.warning(
                    "⚠️ Detectada versión antigua de Blacklist. Migrando tabla..."
                )
                try:
                    backup_name = (
                        f"blacklist_backup_{int(datetime.datetime.now().timestamp())}"
                    )
                    await db.execute(f"ALTER TABLE blacklist RENAME TO {backup_name}")
                    logger.info(f"✅ Tabla antigua renombrada a {backup_name}")

                    await db.execute("""
                        CREATE TABLE blacklist (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            player TEXT,
                            tribe TEXT,
                            map TEXT,
                            notes TEXT,
                            created_at TEXT
                        )
                    """)
                    logger.info("✅ Nueva tabla blacklist creada con schema correcto.")
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ Error durante la migración de Blacklist: {e}")

    # --- Funciones de Autocompletado ---
    async def tribe_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT DISTINCT tribe FROM blacklist WHERE tribe LIKE ? AND guild_id = ? ORDER BY tribe ASC LIMIT 25",
                (
                    f"%{current}%",
                    interaction.guild_id,
                ),
            )
            rows = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=row[0], value=row[0]) for row in rows if row[0]
        ]
        # Retorno de coincidencias o permite texto libre por defecto (Discord behavior)
        return choices

    async def warfare_map_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dinámico de mapas basado en los servidores del Guild."""
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        choices = [name for name in servers.keys() if current.lower() in name.lower()]
        return [app_commands.Choice(name=m, value=m) for m in choices[:25]]

    # --- Definición de Comandos ---

    @app_commands.command(
        name="blacklist",
        description="Muestra el dashboard de la Blacklist (Auto-actualizable).",
    )
    async def blacklist(self, interaction: discord.Interaction):
        await interaction.response.defer(
            thinking=True
        )  # Aplazamiento de respuesta para prevenir Timeout de la interacción

        # Generación del placeholder inicial (Actualización sincrónica inminente)
        embed = discord.Embed(
            title="Cargando Blacklist...", color=discord.Color.dark_grey()
        )
        await interaction.followup.send(embed=embed)
        message = await interaction.original_response()

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO blacklist_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (interaction.guild_id, interaction.channel_id, message.id),
            )
            await db.commit()

        await update_blacklist_dashboards(self.bot, interaction.guild_id)

    # /blacklist_add y /blacklist_mod eliminados — cubiertos por botones del dashboard

    @app_commands.command(
        name="sos", description="¡ALERTA DE RAID! Envía una señal de ayuda."
    )
    @app_commands.describe(
        tipo="Tipo de amenaza (Opcional)",
        mapa="Mapa del ataque (Opcional)",
        atacantes="Número aprox. de enemigos",
        defensores="Número de aliados presentes",
        notas="Información extra",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="🔴 RAIDEO (Base Principal)", value="Raideo"),
            app_commands.Choice(name="🟠 FOB Enemiga", value="FOB"),
            app_commands.Choice(name="🟡 Soaking (Tanqueo)", value="Soaking"),
            app_commands.Choice(name="⚔️ PvP Masivo", value="PvP"),
            app_commands.Choice(name="👀 Scouting Hostil", value="Scouting"),
        ]
    )
    @app_commands.autocomplete(mapa=warfare_map_autocomplete)
    async def sos(
        self,
        interaction: discord.Interaction,
        tipo: app_commands.Choice[str] = None,
        mapa: str = None,
        atacantes: int = None,
        defensores: int = None,
        notas: str = None,
    ):
        # Recuperación del Rol SOS desde variables de entorno
        role_id = os.getenv("SOS_ROLE_ID")
        role_mention = f"<@&{role_id}>" if role_id else "@everyone"

        if not tipo and not mapa and not atacantes and not defensores and not notas:
            # Fallback: Dispatch de SOS Generalizado (Falta de argumentos)
            embed = discord.Embed(
                title="🚨 ¡SOS GENERAL! 🚨",
                description=f"**¡SE NECESITA AYUDA URGENTE!**\n\nEl usuario {interaction.user.mention} ha solicitado asistencia inmediata.\n¡Entrad al canal de voz YA!",
                color=discord.Color.brand_red(),
            )
            embed.set_footer(text="⚠️ Alerta de Prioridad MÁXIMA")
        else:
            # Dispatch: SOS Estructurado y Detallado
            titulo = (
                f"🚨 ALERTA: {tipo.value.upper()}" if tipo else "🚨 ALERTA DE COMBATE"
            )
            color = discord.Color.red()

            embed = discord.Embed(title=titulo, color=color)
            embed.description = f"**Solicitud de ayuda de** {interaction.user.mention}"

            if mapa:
                embed.add_field(name="🗺️ Mapa", value=f"**{mapa}**", inline=True)
            if tipo:
                embed.add_field(name="🔥 Tipo", value=tipo.value, inline=True)

            # Formateo de recuento de fuerzas (Enemigos/Aliados)
            atack_str = str(atacantes) if atacantes is not None else "?"
            def_str = str(defensores) if defensores is not None else "?"
            embed.add_field(
                name="⚔️ Status",
                value=f"👿 **Enemigos:** {atack_str}\n🛡️ **Aliados:** {def_str}",
                inline=False,
            )

            if notas:
                embed.add_field(name="📝 Notas", value=notas, inline=False)

            embed.set_footer(text="¡Dejad lo que estéis haciendo y venid!")

        # Broadcast de la alerta al canal de registro
        await interaction.channel.send(content=role_mention, embed=embed)
        await interaction.response.send_message(
            "✅ Alerta SOS enviada.", ephemeral=True
        )

    # --- K/D/A Tracker (Ranking Manco) ---

    @app_commands.command(
        name="ranking",
        description="Muestra el panel en vivo del Ranking K/D/A (El Más Manco).",
    )
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(
            title="Cargando Ranking...", color=discord.Color.dark_red()
        )
        await interaction.followup.send(embed=embed)
        message = await interaction.original_response()

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO kda_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (interaction.guild_id, interaction.channel_id, message.id),
            )
            await db.commit()

        await update_kda_dashboards(self.bot, interaction.guild_id)

    @app_commands.command(
        name="ranking_char_add",
        description="Vincula un personaje In-Game a un jugador para contar sus kills/muertes.",
    )
    @app_commands.describe(
        jugador="Nombre del jugador de Tribu",
        personaje="Nombre exacto del personaje en ARK",
    )
    async def ranking_char_add(
        self, interaction: discord.Interaction, jugador: str, personaje: str
    ):
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Upsert (Insert or Update) del vínculo Personaje-Jugador
            await db.execute(
                """
                INSERT INTO tribe_characters (guild_id, character_name, player_name)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, character_name) DO UPDATE SET player_name = excluded.player_name
                """,
                (interaction.guild_id, personaje, jugador),
            )
            # Inicialización segura del perfil del jugador en el Tracker KDA a 0
            await db.execute(
                "INSERT OR IGNORE INTO tribe_kda (guild_id, player_name, kills, deaths) VALUES (?, ?, 0, 0)",
                (
                    interaction.guild_id,
                    jugador,
                ),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Ahora el personaje in-game **{personaje}** registrará muertes y bajas para el jugador **{jugador}**.",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot, interaction.guild_id)

    @app_commands.command(
        name="ranking_char_remove",
        description="Desvincula un personaje del sistema de KDA.",
    )
    @app_commands.describe(personaje="Nombre exacto del personaje en ARK")
    async def ranking_char_remove(
        self, interaction: discord.Interaction, personaje: str
    ):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM tribe_characters WHERE character_name = ? AND guild_id = ?",
                (
                    personaje,
                    interaction.guild_id,
                ),
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Personaje **{personaje}** eliminado del registro de logs KDA.",
            ephemeral=False,
        )

    @app_commands.command(
        name="ranking_remove",
        description="¡ADMIN! Borra a un jugador entero del KDA Tracker.",
    )
    @app_commands.describe(jugador="Nombre del jugador a purgar")
    async def ranking_remove(self, interaction: discord.Interaction, jugador: str):
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM tribe_kda WHERE player_name = ? AND guild_id = ?",
                (
                    jugador,
                    interaction.guild_id,
                ),
            )
            await db.execute(
                "DELETE FROM tribe_characters WHERE player_name = ? AND guild_id = ?",
                (
                    jugador,
                    interaction.guild_id,
                ),
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ El jugador **{jugador}** ha sido borrado del Leaderboard (Kills y Muertes reseteadas).",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot, interaction.guild_id)


async def setup(bot):
    await bot.add_cog(Warfare(bot))
