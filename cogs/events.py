import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("ArkTribeBot")


class OptionButton(discord.ui.Button):
    def __init__(self, option_id, event_view, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.option_id = option_id
        self.event_view = event_view

    async def callback(self, inter: discord.Interaction):
        if not inter.response.is_done():
            await inter.response.defer()
        await self.event_view.process_vote(inter, self.option_id)


class RemoveVoteButton(discord.ui.Button):
    def __init__(self, event_view, *args, **kwargs):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="No puedo asistir / Quitar voto",
            **kwargs,
        )
        self.event_view = event_view

    async def callback(self, inter: discord.Interaction):
        if not inter.response.is_done():
            await inter.response.defer()
        await self.event_view.process_vote(inter, 0, remove_only=True)


class EventPollView(discord.ui.View):
    def __init__(self, bot, event_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.event_id = event_id

    @classmethod
    async def build(cls, bot, event_id: int):
        view = cls(bot, event_id)
        opts = await bot.db.fetchall(
            "SELECT id, option_text FROM event_options WHERE event_id = ?",
            (event_id,),
        )

        for opt_row in opts:
            opt_id = opt_row["id"]
            opt_text = opt_row["option_text"]
            btn = OptionButton(
                option_id=opt_id,
                event_view=view,
                label=opt_text,
                style=discord.ButtonStyle.primary,
                custom_id=f"event_v_{event_id}_{opt_id}",
            )
            view.add_item(btn)

        btn_remove = RemoveVoteButton(event_view=view, custom_id=f"event_rm_{event_id}")
        view.add_item(btn_remove)
        return view

    async def update_embed(self, interaction: discord.Interaction):
        """Reconstruye el embed con los votos actuales y lo edita."""
        db = self.bot.db
        # Obtener datos del evento
        event_row = await db.fetchone(
            "SELECT title, description, creator_id FROM events WHERE id = ?",
            (self.event_id,),
        )
        if not event_row:
            await interaction.response.send_message(
                "El evento ya no existe en la base de datos.", ephemeral=True
            )
            return
        title = event_row["title"]
        description = event_row["description"]
        creator_id = event_row["creator_id"]

        # Obtener opciones y votos
        options = await db.fetchall(
            "SELECT option_text, voter_ids FROM event_options WHERE event_id = ? AND guild_id = ? ORDER BY id",
            (self.event_id, interaction.guild_id),
        )

        creator = interaction.guild.get_member(creator_id)
        creator_name = creator.display_name if creator else "Desconocido"

        embed = discord.Embed(
            title=f"📅 Evento: {title}",
            description=description,
            color=discord.Color.blue(),
        )
        embed.set_author(name=f"Organizado por {creator_name}")

        total_votes = sum(len(json.loads(o["voter_ids"])) for o in options)

        for opt in options:
            opt_text = opt["option_text"]
            voters = json.loads(opt["voter_ids"])
            voter_names = [f"<@{v_id}>" for v_id in voters]

            count = len(voters)
            pct = (count / total_votes * 100) if total_votes > 0 else 0
            filled = round(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)

            voters_str = "\n".join([f"• {name}" for name in voter_names]) if count > 0 else "*Nadie todavía*"

            embed.add_field(
                name=f"✅ {opt_text}",
                value=f"`{bar}` **{pct:.0f}%** ({count} votos)\n{voters_str}",
                inline=False,
            )

        embed.set_footer(text=f"Total de participantes: {total_votes}")

        try:
            # Usamos edit_original_response o message.edit según el contexto de la interacción
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.error(f"Error actualizando embed de evento {self.event_id}: {e}")

    async def process_vote(
        self,
        interaction: discord.Interaction,
        option_id: int,
        remove_only: bool = False,
    ):
        user_id = interaction.user.id
        db = self.bot.db

        # Primero, eliminar el voto del usuario de TODAS las opciones de este evento
        # (Para que solo pueda votar por una opción a la vez)
        all_opts = await db.fetchall(
            "SELECT id, voter_ids FROM event_options WHERE event_id = ? AND guild_id = ?",
            (self.event_id, interaction.guild_id),
        )

        for opt in all_opts:
            voters_list = json.loads(opt["voter_ids"])
            if user_id in voters_list:
                voters_list.remove(user_id)
                await db.execute(
                    "UPDATE event_options SET voter_ids = ? WHERE id = ? AND guild_id = ?",
                    (json.dumps(voters_list), opt["id"], interaction.guild_id),
                )

        # Si no es "remove_only" (No puedo asistir), añadimos el voto a la nueva opción
        if not remove_only:
            row = await db.fetchone(
                "SELECT voter_ids FROM event_options WHERE id = ? AND guild_id = ?",
                (option_id, interaction.guild_id),
            )
            if row:
                voters_list = json.loads(row["voter_ids"])
                voters_list.append(user_id)
                await db.execute(
                    "UPDATE event_options SET voter_ids = ? WHERE id = ? AND guild_id = ?",
                    (json.dumps(voters_list), option_id, interaction.guild_id),
                )

        await db.commit()

        # Refrescar UI
        await self.update_embed(interaction)


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="evento",
        description="Crea una encuesta para organizar un Boss o Evento",
    )
    @app_commands.describe(
        titulo="Nombre del evento (Ej: Dragon Alpha)",
        descripcion="Detalles o requisitos (Ej: Traer 100 de elemento)",
        opcion_1="Hora o fecha 1 (Ej: Viernes 22:00)",
        opcion_2="Hora o fecha 2 (Ej: Sábado 18:00)",
        opcion_3="Hora o fecha 3 (Opcional)",
        opcion_4="Hora o fecha 4 (Opcional)",
    )
    async def create_event(
        self,
        interaction: discord.Interaction,
        titulo: str,
        descripcion: str,
        opcion_1: str,
        opcion_2: str,
        opcion_3: str = None,
        opcion_4: str = None,
    ):

        # Validar opciones
        opciones_validas = [
            opt for opt in [opcion_1, opcion_2, opcion_3, opcion_4] if opt is not None and opt.strip() != ""
        ]

        if len(opciones_validas) < 2:
            await interaction.response.send_message(
                "Debes proporcionar al menos 2 opciones de fecha/hora válidas para la encuesta.",
                ephemeral=True,
            )
            return

        # Deferir respuesta ya que interactuamos con BD
        await interaction.response.defer()
        db = self.bot.db

        # 1. Crear Evento
        cursor = await db.execute(
            "INSERT INTO events (guild_id, title, description, creator_id, channel_id, status) VALUES (?, ?, ?, ?, ?, 'active')",
            (
                interaction.guild_id,
                titulo,
                descripcion,
                interaction.user.id,
                interaction.channel_id,
            ),
        )
        event_id = cursor.lastrowid

        # 2. Crear Opciones
        for opt in opciones_validas:
            await db.execute(
                "INSERT INTO event_options (event_id, option_text, voter_ids, guild_id) VALUES (?, ?, ?, ?)",
                (event_id, opt, "[]", interaction.guild_id),
            )

        await db.commit()

        # 3. Crear View y Botones dinámicos
        view = await EventPollView.build(self.bot, event_id)

        # Para el embed necesitamos los nombres de las opciones
        inserted_opts = await db.fetchall(
            "SELECT id, option_text FROM event_options WHERE event_id = ? AND guild_id = ?",
            (event_id, interaction.guild_id),
        )

        # 4. Construir Embed inicial
        embed = discord.Embed(
            title=f"📅 Evento: {titulo}",
            description=descripcion,
            color=discord.Color.blue(),
        )
        creator_name = interaction.user.display_name
        embed.set_author(name=f"Organizado por {creator_name}")

        for opt in inserted_opts:
            embed.add_field(
                name=f"✅ {opt['option_text']} (0 votos)",
                value="*Nadie todavía*",
                inline=False,
            )
        embed.set_footer(text="Total de participantes: 0")

        # 5. Enviar mensaje y guardar refs
        msg = await interaction.followup.send(embed=embed, view=view)

        await db.execute(
            "UPDATE events SET channel_id = ?, message_id = ? WHERE id = ?",
            (msg.channel.id, msg.id, event_id),
        )
        await db.commit()


async def setup(bot):
    await bot.add_cog(Events(bot))
