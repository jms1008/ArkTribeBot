import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import logging
from cogs.server_status import get_guild_servers

logger = logging.getLogger("ArkTribeBot")

SCOUT_PAGE_SIZE = 10  # Entradas por página en vista privada


class AddScoutModal(discord.ui.Modal, title="Añadir Scout"):
    """Modal para añadir un scout desde el botón del dashboard (sin imagen)."""

    tribu = discord.ui.TextInput(label="Tribu Enemiga", placeholder="Ej: Los Raiders")
    mapa = discord.ui.TextInput(label="Mapa", placeholder="Ej: Fjordur")
    coords = discord.ui.TextInput(label="Coordenadas", placeholder="Ej: 45.2, 78.3")
    amenaza = discord.ui.TextInput(
        label="Nivel de Amenaza (1-5)",
        placeholder="1 = Baja  |  5 = Extrema",
        max_length=1,
    )
    notas = discord.ui.TextInput(
        label="Notas",
        placeholder="Info extra (opcional)",
        style=discord.TextStyle.paragraph,
        required=False,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amenaza_int = int(self.amenaza.value)
            if not 1 <= amenaza_int <= 5:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ La amenaza debe ser un número del 1 al 5.", ephemeral=True
            )
            return

        tribu = self.tribu.value
        mapa = self.mapa.value
        coords = self.coords.value
        notas = self.notas.value or ""

        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "INSERT INTO scouts (tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas) "
                "VALUES (?, ?, ?, ?, 'N/A', ?)",
                (tribu, mapa, coords, amenaza_int, notas),
            )
            scout_id = cursor.lastrowid
            await db.commit()

        await interaction.response.send_message(
            f"✅ Scout **#{scout_id}** registrado: **{tribu}** en {mapa}.\n"
            f"Para adjuntar una imagen usa `/scout_add` con el campo *imagen*.",
            ephemeral=True,
        )
        await update_scout_dashboards(self.bot, mapa)


class ScoutView(discord.ui.View):
    def __init__(self, bot, map_filter):
        super().__init__(timeout=None)
        self.bot = bot
        self.map_filter = map_filter

    @discord.ui.button(
        label="Añadir Scout",
        style=discord.ButtonStyle.success,
        custom_id="scout_add_btn",
        emoji="\ud83d\udde1\ufe0f",
    )
    async def add_scout_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(AddScoutModal(self.bot))

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

    @discord.ui.button(
        label="Eliminar Scout",
        style=discord.ButtonStyle.danger,
        custom_id="scout_delete_btn",
    )
    async def delete_scout_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(DeleteScoutModal(self.bot))


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
                        # Detección de Message ID numérico (dato de backup)
                        if str(row["url_imagen"]).strip().isdigit():
                            msg_id = int(str(row["url_imagen"]).strip())
                            async with aiosqlite.connect(bot.db_name) as _db:
                                c = await _db.execute(
                                    "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                                    (dash["guild_id"],),
                                )
                                cfg_row = await c.fetchone()
                                upload_id = cfg_row[0] if cfg_row else None

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
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT mapa, url_imagen, guild_id FROM scouts WHERE id = ?", (sid,)
            )
            scout = await cursor.fetchone()
            if not scout:
                await interaction.response.send_message(
                    "❌ No encontrado.", ephemeral=True
                )
                return

            target_map = scout["mapa"]

            # Eliminar imagen del hilo de archivos si existe
            url_img = scout["url_imagen"]
            if url_img and str(url_img).strip().isdigit():
                try:
                    guild_id = scout["guild_id"] or interaction.guild_id
                    c2 = await db.execute(
                        "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                        (guild_id,),
                    )
                    cfg = await c2.fetchone()
                    if cfg and cfg[0]:
                        thread = self.bot.get_channel(
                            cfg[0]
                        ) or await self.bot.fetch_channel(cfg[0])
                        if thread:
                            try:
                                img_msg = await thread.fetch_message(
                                    int(url_img.strip())
                                )
                                await img_msg.delete()
                            except Exception:
                                pass  # Mensaje ya eliminado o inaccesible
                except Exception as e:
                    logging.getLogger("ArkTribeBot").warning(
                        f"No se pudo eliminar imagen del scout #{sid}: {e}"
                    )

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

    async def mapa_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dinámico de mapas basado en los servidores del Guild."""
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        return [
            app_commands.Choice(name=name, value=name)
            for name in servers.keys()
            if current.lower() in name.lower()
        ][:25]

    @app_commands.command(
        name="scout_add", description="Registra una base enemiga (Con imagen)."
    )
    @app_commands.autocomplete(mapa=mapa_autocomplete)
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
        mapa: str,
        coords: str,
        amenaza: int,
        imagen: discord.Attachment = None,
        notas: str = "",
    ):
        await interaction.response.defer(ephemeral=False)

        # Insertar primero para obtener el ID autogenerado
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                """
                INSERT INTO scouts (tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas)
                VALUES (?, ?, ?, ?, 'N/A', ?)
            """,
                (tribu, mapa, coords, amenaza, notas),
            )
            scout_id = cursor.lastrowid
            await db.commit()

        url_imagen = "N/A"
        if imagen:
            try:
                async with aiosqlite.connect(self.bot.db_name) as db:
                    c = await db.execute(
                        "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                        (interaction.guild_id,),
                    )
                    cfg_row = await c.fetchone()
                    upload_id = cfg_row[0] if cfg_row else None

                thread = None
                if upload_id:
                    thread = self.bot.get_channel(
                        upload_id
                    ) or await self.bot.fetch_channel(upload_id)
                if thread:
                    f = await imagen.to_file()
                    # Caption identificativa con el ID del scout
                    caption = f"Scout #{scout_id} — {tribu} ({mapa})"
                    upload_msg = await thread.send(caption, file=f)
                    # Almacenamiento de ID para evitar caducidad de URLs de Discord
                    url_imagen = str(upload_msg.id)
                else:
                    url_imagen = imagen.url
            except Exception as e:
                logging.getLogger("ArkTribeBot").error(
                    f"Error redirigiendo imagen: {e}"
                )
                url_imagen = imagen.url

            # Actualizar url_imagen ahora que ya tenemos el mensaje subido
            async with aiosqlite.connect(self.bot.db_name) as db:
                await db.execute(
                    "UPDATE scouts SET url_imagen = ? WHERE id = ?",
                    (url_imagen, scout_id),
                )
                await db.commit()

        await interaction.followup.send(
            f"✅ Base de **{tribu}** ({mapa}) registrada. [Scout **#{scout_id}**]"
        )
        await update_scout_dashboards(self.bot, mapa)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    @app_commands.command(
        name="scout_add_image",
        description="Añade o reemplaza la imagen de un registro de scout existente.",
    )
    @app_commands.describe(
        id="ID del scout al que añadir la imagen",
        imagen="Captura de pantalla a adjuntar",
    )
    async def scout_add_image(
        self,
        interaction: discord.Interaction,
        id: int,
        imagen: discord.Attachment,
    ):
        await interaction.response.defer(ephemeral=False)

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT tribu_enemiga, mapa FROM scouts WHERE id = ?", (id,))
            row = await cursor.fetchone()

        if not row:
            await interaction.followup.send(f"❌ No existe un registro de scout con ID {id}.")
            return

        tribu = row["tribu_enemiga"]
        mapa = row["mapa"]
        url_imagen = "N/A"

        try:
            async with aiosqlite.connect(self.bot.db_name) as db:
                c = await db.execute(
                    "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                    (interaction.guild_id,),
                )
                cfg_row = await c.fetchone()
                upload_id = cfg_row[0] if cfg_row else None

            thread = None
            if upload_id:
                thread = self.bot.get_channel(upload_id) or await self.bot.fetch_channel(upload_id)
            if thread:
                f = await imagen.to_file()
                caption = f"Scout #{id} — {tribu} ({mapa}) [Añadida a posteriori]"
                upload_msg = await thread.send(caption, file=f)
                url_imagen = str(upload_msg.id)
            else:
                url_imagen = imagen.url
        except Exception as e:
            logging.getLogger("ArkTribeBot").error(f"Error redirigiendo imagen (scout_add_image): {e}")
            url_imagen = imagen.url

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "UPDATE scouts SET url_imagen = ? WHERE id = ?",
                (url_imagen, id),
            )
            await db.commit()

        await interaction.followup.send(
            f"✅ Imagen adjuntada satisfactoriamente al Scout **#{id}** ({tribu})."
        )
        await update_scout_dashboards(self.bot, mapa)

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
    @app_commands.autocomplete(mapa=mapa_autocomplete)
    @app_commands.describe(mapa="Filtrar por mapa (Opcional)")
    async def scout_list(self, interaction: discord.Interaction, mapa: str = None):
        target_map = mapa if mapa else "Global"
        ephemeral_mode = bool(mapa)

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

        if ephemeral_mode:
            # Vista privada paginada — página 0
            await self._send_private_scout_page(interaction, rows, target_map, page=0)
        else:
            # Modo Global público (Dashboard persistente)
            if not rows:
                embed = discord.Embed(
                    title=f"📡 Scouting: {target_map}",
                    description="No hay registros.\n💡 Usa `/scout_add` para añadir uno.",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title=f"📡 Scouting: {target_map}",
                    color=discord.Color.red(),
                )
                count = 0
                for row in rows:
                    if count >= 20:
                        embed.set_footer(
                            text="...y más registros. | 💡 Usa /scout_add_image [id] [imagen] para añadir foto."
                        )
                        break
                    amenaza_str = "\u2b50" * row["nivel_amenaza"]
                    prefix = f"**[{row['mapa']}]** " if target_map == "Global" else ""
                    value_text = f"\ud83d\udccd {row['coordenadas']} | \u26a0\ufe0f {amenaza_str}\n\ud83d\udcdd {row['notas']}\n\ud83c\udd94 **ID: {row['id']}**"
                    embed.add_field(
                        name=f"{prefix}{row['tribu_enemiga']}",
                        value=value_text,
                        inline=False,
                    )
                    count += 1
                if count < 20:
                    embed.set_footer(
                        text="💡 Usa /scout_add_image [id] [imagen] para añadir foto a un scout."
                    )

            view = ScoutView(self.bot, target_map)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=False
            )
            message = await interaction.original_response()
            async with aiosqlite.connect(self.bot.db_name) as db:
                await db.execute(
                    "INSERT INTO scout_messages (channel_id, message_id, map_filter) VALUES (?, ?, ?)",
                    (interaction.channel_id, message.id, "Global"),
                )
                await db.commit()

    async def _send_private_scout_page(
        self,
        interaction: discord.Interaction,
        rows: list,
        target_map: str,
        page: int,
        edit: bool = False,
    ):
        """Construye y envía/edita una página de la vista privada de scouts."""
        total = len(rows)
        total_pages = max(1, (total + SCOUT_PAGE_SIZE - 1) // SCOUT_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * SCOUT_PAGE_SIZE
        chunk = rows[start : start + SCOUT_PAGE_SIZE]

        if not rows:
            embed = discord.Embed(
                title=f"\ud83d\udce1 Scouting: {target_map}",
                description="No hay registros en este mapa.",
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title=f"\ud83d\udce1 Scouting: {target_map}", color=discord.Color.red()
            )
            for row in chunk:
                amenaza_str = "\u2b50" * row["nivel_amenaza"]
                value_text = f"\ud83d\udccd {row['coordenadas']} | \u26a0\ufe0f {amenaza_str}\n\ud83d\udcdd {row['notas']}\n\ud83c\udd94 **ID: {row['id']}**"
                embed.add_field(
                    name=row["tribu_enemiga"],
                    value=value_text,
                    inline=False,
                )
            embed.set_footer(
                text=f"Página {page + 1}/{total_pages} • {total} bases registradas | 💡 Usa /scout_add_image [id] [imagen] para foto"
            )

        view = ScoutPrivateListView(self.bot, rows, target_map, page)

        if edit:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )


class ScoutPrivateListView(discord.ui.View):
    """Vista de paginación para la vista privada de /scout_list con mapa."""

    def __init__(self, bot, rows, target_map: str, page: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.rows = rows
        self.target_map = target_map
        self.page = page
        total_pages = max(1, (len(rows) + SCOUT_PAGE_SIZE - 1) // SCOUT_PAGE_SIZE)
        self.prev_page_btn.disabled = page == 0
        self.next_page_btn.disabled = page >= total_pages - 1

    @discord.ui.button(
        label="\u25c4", style=discord.ButtonStyle.blurple, custom_id="scout_priv_prev"
    )
    async def prev_page_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        cog = self.bot.cogs.get("Scouting")
        if cog:
            async with aiosqlite.connect(self.bot.db_name) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM scouts WHERE mapa = ? ORDER BY nivel_amenaza DESC",
                    (self.target_map,),
                )
                rows = await cursor.fetchall()
            await cog._send_private_scout_page(
                interaction,
                rows,
                self.target_map,
                page=max(0, self.page - 1),
                edit=True,
            )

    @discord.ui.button(
        label="\u25ba", style=discord.ButtonStyle.blurple, custom_id="scout_priv_next"
    )
    async def next_page_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        cog = self.bot.cogs.get("Scouting")
        if cog:
            async with aiosqlite.connect(self.bot.db_name) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM scouts WHERE mapa = ? ORDER BY nivel_amenaza DESC",
                    (self.target_map,),
                )
                rows = await cursor.fetchall()
            total_pages = max(1, (len(rows) + SCOUT_PAGE_SIZE - 1) // SCOUT_PAGE_SIZE)
            await cog._send_private_scout_page(
                interaction,
                rows,
                self.target_map,
                page=min(total_pages - 1, self.page + 1),
                edit=True,
            )

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
