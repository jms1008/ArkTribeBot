import discord
import aiosqlite
import logging
from cogs.warfare import build_player_detail_embed

logger = logging.getLogger("ArkTribeBot")

class AddRelationshipModal(discord.ui.Modal, title="Añadir Relación"):
    jugador1 = discord.ui.TextInput(
        label="Jugador 1", placeholder="Nombre exacto del jugador 1...", max_length=100
    )
    jugador2 = discord.ui.TextInput(
        label="Jugador 2", placeholder="Nombre exacto del jugador 2...", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        p1 = self.jugador1.value.strip()
        p2 = self.jugador2.value.strip()

        # Normalización de orden alfabético
        if p1 > p2:
            p1, p2 = p2, p1

        guild_id = interaction.guild_id
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Verificación de existencia previa
            cursor = await db.execute(
                "SELECT id FROM k4ultra_relationships WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                (p1, p2, guild_id),
            )
            if await cursor.fetchone():
                await db.execute(
                    "UPDATE k4ultra_relationships SET is_manual = 1, probability_score = 100 WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                    (p1, p2, guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_relationships (guild_id, player1, player2, probability_score, is_manual) VALUES (?, ?, ?, 100, 1)",
                    (guild_id, p1, p2),
                )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Relación manual añadida entre **{p1}** y **{p2}**.", ephemeral=True
        )


class RemoveRelationshipModal(discord.ui.Modal, title="Eliminar Relación"):
    jugador1 = discord.ui.TextInput(
        label="Jugador 1", placeholder="Nombre exacto del jugador 1...", max_length=100
    )
    jugador2 = discord.ui.TextInput(
        label="Jugador 2", placeholder="Nombre exacto del jugador 2...", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        p1 = self.jugador1.value.strip()
        p2 = self.jugador2.value.strip()

        # Normalización de orden alfabético
        if p1 > p2:
            p1, p2 = p2, p1

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "DELETE FROM k4ultra_relationships WHERE player1 = ? AND player2 = ? AND guild_id = ?",
                (p1, p2, interaction.guild_id),
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Relación eliminada entre **{p1}** y **{p2}**.", ephemeral=True
        )


class RenameTribeModal(discord.ui.Modal, title="Asignar Nombre a Tribu"):
    miembro_ref = discord.ui.TextInput(
        label="Miembro de Referencia",
        placeholder="Nombre exacto de un jugador de la tribu...",
        max_length=100,
    )
    nuevo_nombre = discord.ui.TextInput(
        label="Nuevo Nombre", placeholder="Ej: Los Alfas", max_length=100
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        miembro = self.miembro_ref.value.strip()
        nuevo_nombre = self.nuevo_nombre.value.strip()

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id FROM k4ultra_tribe_names WHERE tribe_signature = ? AND guild_id = ?",
                (miembro, interaction.guild_id),
            )
            if await cursor.fetchone():
                await db.execute(
                    "UPDATE k4ultra_tribe_names SET custom_name = ? WHERE tribe_signature = ? AND guild_id = ?",
                    (nuevo_nombre, miembro, interaction.guild_id),
                )
            else:
                await db.execute(
                    "INSERT INTO k4ultra_tribe_names (guild_id, tribe_signature, custom_name) VALUES (?, ?, ?)",
                    (interaction.guild_id, miembro, nuevo_nombre),
                )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Tribu de **{miembro}** renombrada a **{nuevo_nombre}**. Se aplicará en el próximo refresco.",
            ephemeral=True,
        )


class PlayerSelectMenu(discord.ui.Select):
    def __init__(self, bot, guild_id: int, players, aliases=None):
        self.bot = bot
        self.guild_id = guild_id
        if aliases is None:
            aliases = {}
        options = []
        for i, p in enumerate(players[:25]):
            alias_desc = f"Alias: {aliases[p]}" if p in aliases else "Ver detalles y horarios"
            label = f"{p} [{aliases[p]}]" if p in aliases else p
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(
                discord.SelectOption(
                    label=label, description=alias_desc, value=p
                )
            )
        if not options:
            options.append(discord.SelectOption(label="Sin datos", value="none"))
        super().__init__(
            custom_id="k4ultra_player_select",
            placeholder="Selecciona un jugador para ver su perfil detallado...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player_name = self.values[0]
        if player_name == "none":
            await interaction.followup.send("No hay datos.", ephemeral=True)
            return

        try:
            embed = await build_player_detail_embed(self.bot, player_name, self.guild_id)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"[K4Ultra] Error generating unified profile: {e}")
            await interaction.followup.send(f"❌ Error al generar el perfil: {e}", ephemeral=True)


class K4UltraView(discord.ui.View):
    def __init__(self, bot, guild_id: int, top_players=None, aliases=None, pages=None, current_page=0, mode="radar"):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        if top_players is None:
            top_players = []
        self.pages = pages or []
        self.current_page = current_page
        self.mode = mode
        self.add_item(PlayerSelectMenu(bot, guild_id, top_players, aliases))

    @discord.ui.button(
        label="Añadir Relación",
        style=discord.ButtonStyle.primary,
        emoji="➕",
        custom_id="k4ultra_add_rel",
        row=1,
    )
    async def add_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(AddRelationshipModal(self.bot))

    @discord.ui.button(
        label="Eliminar Relación",
        style=discord.ButtonStyle.danger,
        emoji="➖",
        custom_id="k4ultra_rem_rel",
        row=1,
    )
    async def rem_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(RemoveRelationshipModal(self.bot))

    @discord.ui.button(
        label="Renombrar Tribu",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id="k4ultra_ren_rel",
        row=1,
    )
    async def ren_rel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(RenameTribeModal(self.bot))

    @discord.ui.button(
        label="◀️",
        style=discord.ButtonStyle.blurple,
        custom_id="k4ultra_prev_page",
        row=2,
    )
    async def prev_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._flip_page(interaction, -1)

    @discord.ui.button(
        label="▶️",
        style=discord.ButtonStyle.blurple,
        custom_id="k4ultra_next_page",
        row=2,
    )
    async def next_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._flip_page(interaction, 1)

    async def _flip_page(self, interaction: discord.Interaction, direction: int):
        k_cog = self.bot.get_cog("K4Ultra")
        if not k_cog:
            await interaction.response.send_message("Módulo no disponible.", ephemeral=True)
            return

        pages, top_players, aliases = await k_cog.generate_k4ultra_embed(self.guild_id, self.mode)
        if not pages:
            return

        total = len(pages)
        self.current_page = (self.current_page + direction) % total
        new_embed = pages[self.current_page]

        view = K4UltraView(self.bot, self.guild_id, top_players, aliases, pages, self.current_page, self.mode)
        await interaction.response.edit_message(embed=new_embed, view=view)
