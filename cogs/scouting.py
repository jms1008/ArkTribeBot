import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import logging

# Definición de opciones de mapas soportados
MAP_CHOICES = [
    app_commands.Choice(name="The Hub", value="Hub"),
    app_commands.Choice(name="Valguero", value="Valguero"),
    app_commands.Choice(name="Scorched Earth", value="Scorched Earth"),
    app_commands.Choice(name="Crystal Isles", value="Crystal Isles"),
    app_commands.Choice(name="Lost Island", value="Lost Island"),
    app_commands.Choice(name="Gen1", value="Gen1"),
    app_commands.Choice(name="The Island", value="The Island"),
    app_commands.Choice(name="Extinction", value="Extinction"),
    app_commands.Choice(name="Aberration", value="Aberration"),
    app_commands.Choice(name="Gen2", value="Gen2"),
    app_commands.Choice(name="Fjordur", value="Fjordur"),
    app_commands.Choice(name="The Center", value="The Center"),
    app_commands.Choice(name="Ragnarok", value="Ragnarok"),
]


class ScoutView(discord.ui.View):
    def __init__(self, bot, map_filter):
        super().__init__(timeout=None)
        self.bot = bot
        self.map_filter = map_filter

    @discord.ui.button(
        label="Eliminar Scout",
        style=discord.ButtonStyle.danger,
        custom_id="scout_delete_btn",
    )
    async def delete_scout_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(DeleteScoutModal(self.bot))

    @discord.ui.button(
        label="Modificar Scout",
        style=discord.ButtonStyle.secondary,
        custom_id="scout_modify_btn",
        emoji="📝",
    )
    async def modify_scout_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(ModifyScoutModal(self.bot))


async def update_scout_dashboards(bot, target_map=None):
    """Actualiza los dashboards. target_map es el mapa que ha sufrido cambios (o None si unknown)."""

    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        # Actualización dual: Dashboards Globales y Dashboards del mapa afectado
        if target_map:
            cursor = await db.execute(
                "SELECT * FROM scout_messages WHERE map_filter = ? OR map_filter = 'Global'",
                (target_map,),
            )
        else:
            cursor = await db.execute("SELECT * FROM scout_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    messages_to_remove = []

    for dash in dashboards:
        map_filter = dash["map_filter"]

        # Construcción de Embed
        async with aiosqlite.connect(bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            if map_filter == "Global":
                cursor = await db.execute(
                    "SELECT * FROM scouts ORDER BY mapa, nivel_amenaza DESC"
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM scouts WHERE mapa = ? ORDER BY nivel_amenaza DESC",
                    (map_filter,),
                )
            rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                title=f"📡 Scouting: {map_filter}",
                description="No hay registros.\n💡 Usa `/scout_add` para añadir uno.",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title=f"📡 Scouting: {map_filter}", color=discord.Color.red()
            )
            count = 0
            for row in rows:
                if count >= 20:
                    embed.set_footer(
                        text="...y más registros. | 💡 Usa /scout_add para añadir."
                    )
                    break

                amenaza_str = "⭐" * row["nivel_amenaza"]
                # Adición de prefijo de mapa (Solo vista Global)
                prefix = f"**[{row['mapa']}]** " if map_filter == "Global" else ""

                link_img = ""
                # Resolución de imagen activa (A partir de Message ID de backup o URL histórica)
                if row["url_imagen"] and row["url_imagen"] != "N/A":
                    try:
                        # Detección de Message ID numérico (Dato purgado)
                        if str(row["url_imagen"]).strip().isdigit():
                            msg_id = int(str(row["url_imagen"]).strip())
                            async with aiosqlite.connect(bot.db_name) as db:
                                c = await db.execute(
                                    "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                                    (dash["guild_id"],),
                                )
                                row = await c.fetchone()
                                upload_id = row[0] if row else None

                            thread = None
                            if upload_id:
                                thread = bot.get_channel(
                                    upload_id
                                ) or await bot.fetch_channel(upload_id)
                            if thread:
                                backup_msg = await thread.fetch_message(msg_id)
                                if backup_msg.attachments:
                                    # Generación de hipervínculo clickeable
                                    link_img = f" [[📷 Ver Imagen]({backup_msg.attachments[0].url})]"
                        else:
                            # Mantenimiento de retrocompatibilidad con URLs antiguas
                            link_img = f" [[📷 Ver Imagen]({row['url_imagen']})]"
                    except Exception as e:
                        logging.getLogger("ArkTribeBot").warning(
                            f"No se pudo recuperar imagen fresca para scout {row['id']}: {e}"
                        )
                        pass

                value_text = f"📍 {row['coordenadas']} | ⚠️ {amenaza_str}\n📝 {row['notas']}{link_img}\n🆔 **ID: {row['id']}**"
                embed.add_field(
                    name=f"{prefix}{row['tribu_enemiga']}",
                    value=value_text,
                    inline=False,
                )
                count += 1

            if count < 20:
                embed.set_footer(text="💡 Usa /scout_add para añadir una nueva base.")

        view = ScoutView(bot, map_filter)

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
            print(f"Error update scout dash {dash['id']}: {e}")

    # Limpieza de registros inactivos o mensajes borrados
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM scout_messages WHERE id = ?", (mid,))
            await db.commit()


class DeleteScoutModal(discord.ui.Modal, title="Eliminar Scout"):
    scout_id = discord.ui.TextInput(label="ID del Scout", placeholder="Número ID")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            sid = int(self.scout_id.value)
        except Exception:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT mapa FROM scouts WHERE id = ?", (sid,))
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message(
                    "❌ No encontrado.", ephemeral=True
                )
                return

            target_map = row[0]
            await db.execute("DELETE FROM scouts WHERE id = ?", (sid,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Scout **#{sid}** eliminado.", ephemeral=False
        )
        await update_scout_dashboards(self.bot, target_map)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


class ModifyScoutModal(discord.ui.Modal, title="Modificar Scout"):
    scout_id = discord.ui.TextInput(
        label="ID del Scout",
        placeholder="Número ID",
        style=discord.TextStyle.short,
        required=True,
    )
    nuevas_notas = discord.ui.TextInput(
        label="Nuevas Notas",
        placeholder="Escribe aquí para añadir información...",
        style=discord.TextStyle.paragraph,
        required=False,
    )
    nueva_amenaza = discord.ui.TextInput(
        label="Nuevo Nivel de Amenaza (1-5)",
        placeholder="Ej: 5",
        style=discord.TextStyle.short,
        required=False,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            sid = int(self.scout_id.value)
        except Exception:
            await interaction.response.send_message(
                "❌ El ID debe ser un número.", ephemeral=True
            )
            return

        notas = self.nuevas_notas.value.strip()
        amenaza = self.nueva_amenaza.value.strip()

        if not notas and not amenaza:
            await interaction.response.send_message(
                "❌ Debes rellenar al menos un campo para modificar.", ephemeral=True
            )
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT mapa, notas, nivel_amenaza FROM scouts WHERE id = ?", (sid,)
            )
            row = await cursor.fetchone()
            if not row:
                await interaction.response.send_message(
                    "❌ Scout no encontrado.", ephemeral=True
                )
                return

            target_map = row[0]
            existing_notas = row[1]
            existing_amenaza = row[2]

            new_amenaza = existing_amenaza
            if amenaza:
                try:
                    new_amenaza = int(amenaza)
                    if new_amenaza < 1 or new_amenaza > 5:
                        await interaction.response.send_message(
                            "❌ La amenaza debe ser entre 1 y 5.", ephemeral=True
                        )
                        return
                except Exception:
                    await interaction.response.send_message(
                        "❌ La amenaza debe ser un número.", ephemeral=True
                    )
                    return

            new_notas = existing_notas
            if notas:
                import datetime as dt

                today = dt.date.today().strftime("%d/%m")
                new_notas = (
                    f"{existing_notas}\n[{today}]: {notas}"
                    if existing_notas
                    else f"[{today}]: {notas}"
                )

            await db.execute(
                "UPDATE scouts SET notas = ?, nivel_amenaza = ? WHERE id = ?",
                (new_notas, new_amenaza, sid),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Scout **#{sid}** actualizado.", ephemeral=False
        )
        await update_scout_dashboards(self.bot, target_map)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


class Scouting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="scout_add", description="Registra una base enemiga (Con imagen)."
    )
    @app_commands.choices(mapa=MAP_CHOICES)
    @app_commands.describe(
        tribu="Nombre de la tribu enemiga",
        mapa="Mapa donde se encuentra",
        coords="Coordenadas (Lat, Lon)",
        amenaza="Nivel de amenaza (1-5)",
        imagen="Captura de pantalla (Opcional)",
        notas="Información extra",
    )
    async def scout_add(
        self,
        interaction: discord.Interaction,
        tribu: str,
        mapa: app_commands.Choice[str],
        coords: str,
        amenaza: int,
        imagen: discord.Attachment = None,
        notas: str = "",
    ):
        await interaction.response.defer(ephemeral=False)
        url_imagen = "N/A"

        if imagen:
            try:
                async with aiosqlite.connect(self.bot.db_name) as db:
                    c = await db.execute(
                        "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                        (interaction.guild_id,),
                    )
                    row = await c.fetchone()
                    upload_id = row[0] if row else None

                thread = None
                if upload_id:
                    thread = self.bot.get_channel(
                        upload_id
                    ) or await self.bot.fetch_channel(upload_id)
                if thread:
                    f = await imagen.to_file()
                    upload_msg = await thread.send(file=f)
                    # Almacenamiento de ID (backup) para evitar caducidad de URLs provistas por Discord
                    url_imagen = str(upload_msg.id)
                else:
                    url_imagen = imagen.url
            except Exception as e:
                logging.getLogger("ArkTribeBot").error(
                    f"Error redirigiendo imagen: {e}"
                )
                url_imagen = imagen.url

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO scouts (tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (tribu, mapa.value, coords, amenaza, url_imagen, notas),
            )
            await db.commit()

        await interaction.followup.send(
            f"✅ Base de **{tribu}** ({mapa.value}) registrada."
        )
        await update_scout_dashboards(self.bot, mapa.value)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    @app_commands.command(
        name="scout_list",
        description="Menú de Scouting: Sin argumentos = Dashboard PÚBLICO. Con mapa = Vista PRIVADA.",
    )
    @app_commands.choices(mapa=MAP_CHOICES)
    @app_commands.describe(mapa="Filtrar por mapa (Opcional)")
    async def scout_list(
        self, interaction: discord.Interaction, mapa: app_commands.Choice[str] = None
    ):
        # División lógica según presencia de parámetro de mapa
        # Sin mapa: Modo Global Público (Dashboard persistente)
        # Con mapa: Modo Privado Temporal (Snapshot efímero)

        target_map = mapa.value if mapa else "Global"
        ephemeral_mode = True if mapa else False

        # Recuperación de registros de la Base de Datos
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            if target_map == "Global":
                cursor = await db.execute(
                    "SELECT * FROM scouts ORDER BY mapa, nivel_amenaza DESC"
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM scouts WHERE mapa = ? ORDER BY nivel_amenaza DESC",
                    (target_map,),
                )
            rows = await cursor.fetchall()

        # Creación del Embed principal
        if not rows:
            embed = discord.Embed(
                title=f"📡 Scouting: {target_map}",
                description="No hay registros.\n💡 Usa `/scout_add` para añadir uno.",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title=f"📡 Scouting: {target_map}", color=discord.Color.red()
            )
            count = 0
            for row in rows:
                if count >= 20:
                    embed.set_footer(
                        text="...y más registros. | 💡 Usa /scout_add para añadir."
                    )
                    break
                amenaza_str = "⭐" * row["nivel_amenaza"]
                # Inserción de prefijo identificador de mapa (sólo Global)
                prefix = f"**[{row['mapa']}]** " if target_map == "Global" else ""

                link_img = ""
                if row["url_imagen"] and row["url_imagen"] != "N/A":
                    try:
                        if str(row["url_imagen"]).strip().isdigit():
                            msg_id = int(str(row["url_imagen"]).strip())
                            async with aiosqlite.connect(self.bot.db_name) as db:
                                c = await db.execute(
                                    "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                                    (interaction.guild_id,),
                                )
                                row = await c.fetchone()
                                upload_id = row[0] if row else None

                            thread = None
                            if upload_id:
                                thread = self.bot.get_channel(
                                    upload_id
                                ) or await self.bot.fetch_channel(upload_id)
                            if thread:
                                backup_msg = await thread.fetch_message(msg_id)
                                if backup_msg.attachments:
                                    link_img = f" [[📷 Ver Imagen]({backup_msg.attachments[0].url})]"
                        else:
                            link_img = f" [[📷 Ver Imagen]({row['url_imagen']})]"
                    except Exception:
                        pass

                value_text = f"📍 {row['coordenadas']} | ⚠️ {amenaza_str}\n📝 {row['notas']}{link_img}\n🆔 **ID: {row['id']}**"
                embed.add_field(
                    name=f"{prefix}{row['tribu_enemiga']}",
                    value=value_text,
                    inline=False,
                )
                count += 1

            if count < 20:
                embed.set_footer(text="💡 Usa /scout_add para añadir una nueva base.")

        # Vinculación de vista interactiva (View)
        view = ScoutView(self.bot, target_map)

        # Envío de la respuesta
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=ephemeral_mode
        )

        # Persistencia en Modo Global para garantizar auto-actualizaciones
        if not ephemeral_mode:
            message = await interaction.original_response()
            async with aiosqlite.connect(self.bot.db_name) as db:
                await db.execute(
                    "INSERT INTO scout_messages (channel_id, message_id, map_filter) VALUES (?, ?, ?)",
                    (interaction.channel_id, message.id, "Global"),
                )
                await db.commit()

    @app_commands.command(
        name="scout_delete", description="Elimina una entrada de scouting por ID."
    )
    @app_commands.describe(id="ID del registro a eliminar")
    async def scout_delete(self, interaction: discord.Interaction, id: int):
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT mapa FROM scouts WHERE id = ?", (id,))
            row = await cursor.fetchone()

            if not row:
                await interaction.response.send_message(
                    f"❌ ID {id} no encontrado.", ephemeral=True
                )
                return

            map_target = row[0]

            await db.execute("DELETE FROM scouts WHERE id = ?", (id,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Registro #{id} eliminado.", ephemeral=False
        )
        await update_scout_dashboards(self.bot, map_target)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Scouting(bot))
