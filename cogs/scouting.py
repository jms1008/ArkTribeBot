import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.server_status import get_guild_servers
from utils.i18n import resolve_lang, t

logger = logging.getLogger("ArkTribeBot")

SCOUT_PAGE_SIZE = 10  # Entradas por página en vista privada


async def _fetch_scout_rows(db, guild_id: int, target_map: str) -> list:
    """Filas de scouts del guild, filtradas por mapa o todas si es 'Global'."""
    if target_map == "Global":
        cursor = await db.execute(
            "SELECT * FROM scouts WHERE guild_id = ? ORDER BY mapa, nivel_amenaza DESC",
            (guild_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM scouts WHERE guild_id = ? AND mapa = ? ORDER BY nivel_amenaza DESC",
            (guild_id, target_map),
        )
    return await cursor.fetchall()


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

        db = self.bot.db
        c = await db.execute(
            "SELECT COALESCE(MAX(entry_number), 0) FROM scouts WHERE guild_id = ?",
            (interaction.guild_id,),
        )
        max_row = await c.fetchone()
        next_num = (max_row[0] or 0) + 1

        await db.execute(
            "INSERT INTO scouts (guild_id, tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas, entry_number) "
            "VALUES (?, ?, ?, ?, ?, 'N/A', ?, ?)",
            (interaction.guild_id, tribu, mapa, coords, amenaza_int, notas, next_num),
        )
        await db.commit()

        await interaction.response.send_message(
            f"✅ Scout **#{next_num}** registrado: **{tribu}** en {mapa}.\n"
            f"Para adjuntar una imagen usa `/scout imagen` con el ID **{next_num}**.",
            ephemeral=True,
        )
        await update_scout_dashboards(self.bot, interaction.guild_id, mapa)


class ScoutSelect(discord.ui.Select):
    def __init__(self, bot, chunk):
        self.bot = bot
        options = []
        for row in chunk:
            try:
                num = row['entry_number'] or row['id']
            except (KeyError, IndexError):
                num = row['id']
            options.append(
                discord.SelectOption(
                    label=f"#{num} {row['tribu_enemiga'][:80]}",
                    description=f"{row['mapa']} | {row['coordenadas']}",
                    value=str(num),
                    emoji="📍",
                )
            )
        if not options:
            options.append(discord.SelectOption(label="Sin scouts", value="none"))

        super().__init__(
            placeholder="Selecciona para ver los detalles completos...",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id="scout_selectView",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return

        scout_id = int(self.values[0])
        db = self.bot.db
        c = await db.execute("SELECT * FROM scouts WHERE entry_number = ? AND guild_id = ?", (scout_id, interaction.guild_id))
        row = await c.fetchone()

        if not row:
            await interaction.response.send_message("❌ Scout no encontrado.", ephemeral=True)
            return

        threat_bar = "🔴" * row["nivel_amenaza"] + "⚫" * (5 - row["nivel_amenaza"])
        notas = row["notas"] or "*Sin notas adicionales*"

        embed = discord.Embed(
            title=f"🔎 SCOUT #{(row['entry_number'] if row['entry_number'] else row['id']):03d}",
            color=discord.Color.from_rgb(200, 50, 50),
        )
        embed.description = (
            f"## 🏴 {row['tribu_enemiga']}\n\n"
            f"> 🗺️ **Mapa:** `{row['mapa']}`\n"
            f"> 📍 **Coordenadas:** `{row['coordenadas']}`\n"
            f"> ⚠️ **Amenaza:** {threat_bar}  `{row['nivel_amenaza']}/5`\n\n"
            f"## 📝 Notas\n"
            f"> {notas}"
        )
        try:
            _num = row['entry_number'] or row['id']
        except (KeyError, IndexError):
            _num = row['id']
        embed.set_footer(text=f"Scout #{_num:03d}  •  /scout borrar id:{_num} para eliminar")

        img_url = None
        if row["url_imagen"] and row["url_imagen"] != "N/A":
            try:
                if str(row["url_imagen"]).strip().isdigit():
                    msg_id = int(str(row["url_imagen"]).strip())
                    _db = self.bot.db
                    c = await _db.execute(
                        "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?", (row["guild_id"],)
                    )
                    cfg_row = await c.fetchone()
                    upload_id = cfg_row[0] if cfg_row else None
                    if upload_id:
                        ch = self.bot.get_channel(upload_id) or await self.bot.fetch_channel(upload_id)
                        if ch:
                            backup_msg = await ch.fetch_message(msg_id)
                            if backup_msg.attachments:
                                img_url = backup_msg.attachments[0].url
                else:
                    img_url = row["url_imagen"]
            except (discord.NotFound, discord.Forbidden, ValueError) as e:
                logger.debug(f"[Scouting] No se pudo recuperar imagen de backup: {e}")

        if img_url:
            embed.set_image(url=img_url)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ScoutView(discord.ui.View):
    def __init__(self, bot, map_filter, chunk=None, page: int = 0, total_rows: int = 0, lang: str = "es"):
        super().__init__(timeout=None)
        self.bot = bot
        self.map_filter = map_filter
        self.page = page
        self.total_rows = total_rows
        self.lang = lang

        # Etiquetas traducibles de los botones de acción.
        self.add_scout_btn.label = t("scout.btn.add", lang)
        self.modify_scout_btn.label = t("scout.btn.modify", lang)
        self.delete_scout_btn.label = t("scout.btn.delete", lang)

        if chunk:
            self.add_item(ScoutSelect(bot, chunk))

        total_pages = max(1, (self.total_rows + 10 - 1) // 10)
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= total_pages - 1

    @discord.ui.button(
        label="Añadir Scout",
        style=discord.ButtonStyle.success,
        custom_id="scout_add_btn",
        emoji="\ud83d\udde1\ufe0f",
    )
    async def add_scout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddScoutModal(self.bot))

    @discord.ui.button(
        label="Modificar Scout",
        style=discord.ButtonStyle.secondary,
        custom_id="scout_modify_btn",
        emoji="📝",
    )
    async def modify_scout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModifyScoutModal(self.bot))

    @discord.ui.button(
        label="Eliminar Scout",
        style=discord.ButtonStyle.danger,
        custom_id="scout_delete_btn",
    )
    async def delete_scout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteScoutModal(self.bot))

    @discord.ui.button(
        label="◀️",
        style=discord.ButtonStyle.blurple,
        custom_id="scout_prev_btn",
    )
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re

        current_page = 0
        if interaction.message.embeds and interaction.message.embeds[0].footer.text:
            m = re.search(r"(\d+)/(\d+)", interaction.message.embeds[0].footer.text)
            if m:
                current_page = int(m.group(1)) - 1
        new_page = max(0, current_page - 1)
        await self._update_page(interaction, new_page)

    @discord.ui.button(
        label="▶️",
        style=discord.ButtonStyle.blurple,
        custom_id="scout_next_btn",
    )
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        import re

        current_page = 0
        total_pages = 1
        if interaction.message.embeds and interaction.message.embeds[0].footer.text:
            m = re.search(r"(\d+)/(\d+)", interaction.message.embeds[0].footer.text)
            if m:
                current_page = int(m.group(1)) - 1
                total_pages = int(m.group(2))
        new_page = min(total_pages - 1, current_page + 1)
        await self._update_page(interaction, new_page)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        db = self.bot.db
        if self.map_filter == "Global":
            cursor = await db.execute(
                "SELECT * FROM scouts WHERE guild_id = ? ORDER BY mapa, nivel_amenaza DESC",
                (interaction.guild_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM scouts WHERE guild_id = ? AND mapa = ? ORDER BY nivel_amenaza DESC",
                (
                    interaction.guild_id,
                    self.map_filter,
                ),
            )
        rows = await cursor.fetchall()

        lang = await resolve_lang(self.bot, interaction.guild_id, "periodic")
        embed, page, view = await build_scout_embed_view(self.bot, rows, self.map_filter, new_page, lang=lang)
        await interaction.response.edit_message(embed=embed, view=view)


async def build_scout_embed_view(bot, rows: list, map_filter: str, page: int = 0, lang: str = "es"):
    page_size = 10
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))

    start = page * page_size
    chunk = rows[start : start + page_size]

    embed = discord.Embed(
        title=t("scout.title", lang, map=map_filter.upper()), color=discord.Color.from_rgb(200, 50, 50)
    )

    if not rows:
        embed.description = t("scout.empty", lang)
    else:
        lines = []
        lines.append(t("scout.badges", lang, total=total))
        lines.append("")

        for row in chunk:
            threat = row["nivel_amenaza"]
            threat_bar = "🔴" * threat + "⚫" * (5 - threat)
            prefix = f"**[{row['mapa']}]** " if map_filter == "Global" else ""

            link_img = ""
            if row["url_imagen"] and row["url_imagen"] != "N/A":
                try:
                    if str(row["url_imagen"]).strip().isdigit():
                        msg_id = int(str(row["url_imagen"]).strip())
                        _db = bot.db
                        c = await _db.execute(
                            "SELECT upload_channel_id FROM guild_config WHERE guild_id = ?",
                            (row["guild_id"],),
                        )
                        cfg_row = await c.fetchone()
                        upload_id = cfg_row[0] if cfg_row else None

                        thread = None
                        if upload_id:
                            thread = bot.get_channel(upload_id) or await bot.fetch_channel(upload_id)
                        if thread:
                            backup_msg = await thread.fetch_message(msg_id)
                            if backup_msg.attachments:
                                link_img = f" [📷]({backup_msg.attachments[0].url})"
                    else:
                        link_img = f" [📷]({row['url_imagen']})"
                except Exception as e:
                    logging.getLogger("ArkTribeBot").warning(
                        f"No se pudo recuperar imagen fresca para scout {row.get('entry_number', row['id']) if hasattr(row, 'get') else row['id']}: {e}"
                    )

            notas = row["notas"] or ""
            notas_txt = f"\n>  ╰ 📝 *{notas[:50]}{'...' if len(notas) > 50 else ''}*" if notas else ""

            try:
                _enum = row['entry_number'] or row['id']
            except (KeyError, IndexError):
                _enum = row['id']
            lines.append(f"> `#{_enum}` {prefix}**{row['tribu_enemiga']}**{link_img}")
            lines.append(f">  📍 `{row['coordenadas']}` · {threat_bar}{notas_txt}")
            lines.append("")

        embed.description = "\n".join(lines).strip()
        embed.set_footer(text=t("scout.footer", lang, page=page + 1, pages=total_pages))
    view = ScoutView(bot, map_filter, chunk, page=page, total_rows=total, lang=lang)
    return embed, page, view


async def update_scout_dashboards(bot, guild_id: int, target_map=None, page: int = 0):
    """Actualiza los dashboards. target_map es el mapa que ha sufrido cambios (o None si unknown)."""

    db = bot.db
    # Actualización dual: Dashboards Globales y Dashboards del mapa afectado
    if target_map:
        cursor = await db.execute(
            "SELECT * FROM scout_messages WHERE guild_id = ? AND (map_filter = ? OR map_filter = 'Global')",
            (
                guild_id,
                target_map,
            ),
        )
    else:
        cursor = await db.execute("SELECT * FROM scout_messages WHERE guild_id = ?", (guild_id,))
    dashboards = await cursor.fetchall()

    if not dashboards:
        return

    messages_to_remove = []

    for dash in dashboards:
        map_filter = dash["map_filter"]

        # Omitimos la recarga completa aquí; simplemente usamos build_scout_embed_view
        # Necesitamos cargar las 'rows' para este dashboard concreto
        db = bot.db
        if map_filter == "Global":
            cursor = await db.execute(
                "SELECT * FROM scouts WHERE guild_id = ? ORDER BY mapa, nivel_amenaza DESC", (guild_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM scouts WHERE guild_id = ? AND mapa = ? ORDER BY nivel_amenaza DESC",
                (
                    guild_id,
                    map_filter,
                ),
            )
        rows = await cursor.fetchall()

        lang = await resolve_lang(bot, guild_id, "periodic")
        embed, _, view = await build_scout_embed_view(bot, rows, map_filter, page, lang=lang)

        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(dash["channel_id"])
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                await message.edit(embed=embed, view=view)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            logger.error(f"Error actualizando dashboard scout {dash['id']}: {e}")

    if messages_to_remove:
        db = bot.db
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
            await interaction.response.send_message("❌ El ID debe ser un número.", ephemeral=True)
            return

        db = self.bot.db
        cursor = await db.execute(
            "SELECT mapa, url_imagen, guild_id FROM scouts WHERE entry_number = ? AND guild_id = ?",
            (sid, interaction.guild_id),
        )
        scout = await cursor.fetchone()
        if not scout:
            await interaction.response.send_message("❌ No encontrado.", ephemeral=True)
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
                    thread = self.bot.get_channel(cfg[0]) or await self.bot.fetch_channel(cfg[0])
                    if thread:
                        try:
                            img_msg = await thread.fetch_message(int(url_img.strip()))
                            await img_msg.delete()
                        except (discord.NotFound, discord.Forbidden, ValueError) as e:
                            logger.debug(f"[Scouting] Imagen de scout ya inaccesible: {e}")
            except Exception as e:
                logging.getLogger("ArkTribeBot").warning(f"No se pudo eliminar imagen del scout #{sid}: {e}")

        await db.execute("DELETE FROM scouts WHERE entry_number = ? AND guild_id = ?", (sid, interaction.guild_id))
        await db.commit()

        await interaction.response.send_message(f"🗑️ Scout **#{sid}** eliminado.", ephemeral=False)
        await update_scout_dashboards(self.bot, interaction.guild_id, target_map)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Scouting] Auto-delete falló: {e}")


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
            await interaction.response.send_message("❌ El ID debe ser un número.", ephemeral=True)
            return

        notas = self.nuevas_notas.value.strip()
        amenaza = self.nueva_amenaza.value.strip()

        if not notas and not amenaza:
            await interaction.response.send_message(
                "❌ Debes rellenar al menos un campo para modificar.", ephemeral=True
            )
            return

        db = self.bot.db
        cursor = await db.execute(
            "SELECT mapa, notas, nivel_amenaza FROM scouts WHERE entry_number = ? AND guild_id = ?",
            (sid, interaction.guild_id),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("❌ Scout no encontrado.", ephemeral=True)
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
                await interaction.response.send_message("❌ La amenaza debe ser un número.", ephemeral=True)
                return

        new_notas = existing_notas
        if notas:
            import datetime as dt

            today = dt.date.today().strftime("%d/%m")
            new_notas = f"{existing_notas}\n[{today}]: {notas}" if existing_notas else f"[{today}]: {notas}"

        await db.execute(
            "UPDATE scouts SET notas = ?, nivel_amenaza = ? WHERE entry_number = ? AND guild_id = ?",
            (new_notas, new_amenaza, sid, interaction.guild_id),
        )
        await db.commit()

        await interaction.response.send_message(f"✅ Scout **#{sid}** actualizado.", ephemeral=False)
        await update_scout_dashboards(self.bot, interaction.guild_id, target_map)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Scouting] Auto-delete falló: {e}")


class Scouting(commands.Cog):
    # Grupo unificado de reconocimiento (antes /scout_add, /scout_add_image,
    # /scout_delete, /scout_list).
    scout = app_commands.Group(name="scout", description="Reconocimiento de bases enemigas.")

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_scouting_updated(self, guild_id: int):
        """Refresca dashboards de scouting cuando algún cog los modifica."""
        try:
            await update_scout_dashboards(self.bot, guild_id)
        except Exception as e:
            logger.error(f"[Scouting] Refresh dashboards falló (guild {guild_id}): {e}")

    async def setup_dashboard(self, guild_id: int, channel: discord.TextChannel):
        """Inicializa el dashboard interactivo de Scouting."""
        import asyncio

        from cogs.management import get_info_texts

        info_lang = await resolve_lang(self.bot, guild_id, "periodic")
        info_embed = discord.Embed(
            description=get_info_texts(info_lang)["scouting"],
            color=discord.Color.from_rgb(43, 45, 49),
        )
        await channel.send(embed=info_embed)

        db = self.bot.db
        cursor = await db.execute(
            "SELECT * FROM scouts WHERE guild_id = ? ORDER BY id DESC",
            (guild_id,),
        )
        rows = await cursor.fetchall()

        lang = await resolve_lang(self.bot, guild_id, "periodic")
        embed, _, view = await build_scout_embed_view(self.bot, rows, "Global", 0, lang=lang)
        msg = await channel.send(embed=embed, view=view)
        await asyncio.sleep(0.5)

        db = self.bot.db
        await db.execute(
            "INSERT INTO scout_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
            (guild_id, channel.id, msg.id),
        )
        await db.commit()

    async def scouting_mapa_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete dinámico de mapas basado en los servidores del Guild."""
        servers = await get_guild_servers(self.bot, interaction.guild_id)
        return [
            app_commands.Choice(name=name, value=name)
            for name in servers.keys()
            if current.lower() in name.lower()
        ][:25]

    @scout.command(name="add", description="Registra una base enemiga (Con imagen).")
    @app_commands.autocomplete(mapa=scouting_mapa_autocomplete)
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

        # Calcular el siguiente entry_number para este guild
        db = self.bot.db
        c = await db.execute(
            "SELECT COALESCE(MAX(entry_number), 0) FROM scouts WHERE guild_id = ?",
            (interaction.guild_id,),
        )
        max_row = await c.fetchone()
        next_num = (max_row[0] or 0) + 1

        await db.execute(
            """
            INSERT INTO scouts (guild_id, tribu_enemiga, mapa, coordenadas, nivel_amenaza, url_imagen, notas, entry_number)
            VALUES (?, ?, ?, ?, ?, 'N/A', ?, ?)
        """,
            (interaction.guild_id, tribu, mapa, coords, amenaza, notas, next_num),
        )
        scout_id = next_num
        await db.commit()

        url_imagen = "N/A"
        if imagen:
            try:
                db = self.bot.db
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
                    # Caption identificativa con el ID del scout
                    caption = f"Scout #{scout_id} — {tribu} ({mapa})"
                    upload_msg = await thread.send(caption, file=f)
                    # Almacenamiento de ID para evitar caducidad de URLs de Discord
                    url_imagen = str(upload_msg.id)
                else:
                    url_imagen = imagen.url
            except Exception as e:
                logging.getLogger("ArkTribeBot").error(f"Error redirigiendo imagen: {e}")
                url_imagen = imagen.url

            # Actualizar url_imagen ahora que ya tenemos el mensaje subido
            db = self.bot.db
            await db.execute(
                "UPDATE scouts SET url_imagen = ? WHERE entry_number = ? AND guild_id = ?",
                (url_imagen, scout_id, interaction.guild_id),
            )
            await db.commit()

        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        await interaction.followup.send(t("scout.cmd.added", lang, tribu=tribu, mapa=mapa, id=scout_id))
        await update_scout_dashboards(self.bot, interaction.guild_id, mapa)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Scouting] Auto-delete falló: {e}")

    @scout.command(
        name="imagen",
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
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)

        db = self.bot.db
        # Buscamos primero el scout sin filtrar por guild para diagnosticar si existe en otro lado
        cursor = await db.execute("SELECT tribu_enemiga, mapa, guild_id FROM scouts WHERE entry_number = ? AND guild_id = ?", (id, interaction.guild_id))
        row = await cursor.fetchone()

        if not row:
            await interaction.followup.send(t("scout.cmd.not_found", lang, id=id))
            return

        # guild_id already filtered in WHERE clause, no cross-guild access possible

        tribu = row["tribu_enemiga"]
        mapa = row["mapa"]
        url_imagen = "N/A"

        try:
            db = self.bot.db
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

        db = self.bot.db
        await db.execute(
            "UPDATE scouts SET url_imagen = ? WHERE entry_number = ? AND guild_id = ?",
            (url_imagen, id, interaction.guild_id),
        )
        await db.commit()

        await interaction.followup.send(t("scout.cmd.image_added", lang, id=id, tribu=tribu))
        await update_scout_dashboards(self.bot, interaction.guild_id, mapa)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Scouting] Auto-delete falló: {e}")

    @scout.command(name="borrar", description="Elimina una entrada de scouting por ID.")
    @app_commands.describe(id="ID del registro a eliminar")
    async def scout_delete(self, interaction: discord.Interaction, id: int):
        lang = await resolve_lang(self.bot, interaction.guild_id, "command", interaction.user.id)
        db = self.bot.db
        cursor = await db.execute(
            "SELECT mapa FROM scouts WHERE entry_number = ? AND guild_id = ?",
            (
                id,
                interaction.guild_id,
            ),
        )
        row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                t("scout.cmd.delete_not_found", lang, id=id), ephemeral=True
            )
            return

        map_target = row[0]

        await db.execute("DELETE FROM scouts WHERE entry_number = ? AND guild_id = ?", (id, interaction.guild_id))
        await db.commit()

        await interaction.response.send_message(t("scout.cmd.deleted", lang, id=id), ephemeral=False)
        await update_scout_dashboards(self.bot, interaction.guild_id, map_target)

        await asyncio.sleep(2)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except (discord.NotFound, discord.Forbidden) as e:
            logger.debug(f"[Scouting] Auto-delete falló: {e}")

    @scout.command(
        name="lista",
        description="Consulta PRIVADA de bases enemigas (todas o filtradas por mapa).",
    )
    @app_commands.autocomplete(mapa=scouting_mapa_autocomplete)
    @app_commands.describe(mapa="Filtrar por mapa (Opcional; sin mapa = todos)")
    async def scout_list(self, interaction: discord.Interaction, mapa: str = None):
        """Vista privada paginada. Antes este comando también creaba el dashboard
        público cuando se invocaba sin mapa — esa función vive ahora en /scout panel."""
        target_map = mapa if mapa else "Global"
        rows = await _fetch_scout_rows(self.bot.db, interaction.guild_id, target_map)
        await self._send_private_scout_page(interaction, rows, target_map, page=0)

    @scout.command(
        name="panel",
        description="Crea el dashboard PÚBLICO de scouting (auto-actualizable).",
    )
    async def scout_panel(self, interaction: discord.Interaction):
        rows = await _fetch_scout_rows(self.bot.db, interaction.guild_id, "Global")
        lang = await resolve_lang(self.bot, interaction.guild_id, "periodic")
        embed, page, view = await build_scout_embed_view(self.bot, rows, "Global", 0, lang=lang)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
        message = await interaction.original_response()
        db = self.bot.db
        await db.execute(
            "INSERT INTO scout_messages (guild_id, channel_id, message_id, map_filter) VALUES (?, ?, ?, ?)",
            (interaction.guild_id, interaction.channel_id, message.id, "Global"),
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
                title=f"🛰️ SCOUTING: {target_map.upper()}",
                description=(
                    "📭 No hay registros en este mapa.\n\n"
                    "💡 Usa `/scout add` para registrar una base enemiga."
                ),
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title=f"🛰️ SCOUTING: {target_map.upper()}",
                color=discord.Color.red(),
            )
            lines = [
                f"📊 `{total}` bases registradas  ·  📄 Página `{page + 1}/{total_pages}`",
                "",
            ]
            for row in chunk:
                threat_bar = "🔴" * row["nivel_amenaza"] + "⚫" * (5 - row["nivel_amenaza"])
                notas = (row["notas"] or "").strip()
                nota_corta = (notas[:50] + "...") if len(notas) > 50 else notas
                map_prefix = f"**[{row['mapa']}]** " if target_map == "Global" else ""
                try:
                    _pnum = row['entry_number'] or row['id']
                except (KeyError, IndexError):
                    _pnum = row['id']
                lines.append(f"`#{_pnum:03d}` 🏴 {map_prefix}**{row['tribu_enemiga']}**")
                lines.append(f"  📍 `{row['coordenadas']}`  ·  {threat_bar}")
                if nota_corta:
                    lines.append(f"  ╰ 📝 *{nota_corta}*")
                lines.append("")
            embed.description = "\n".join(lines).strip()
            embed.set_footer(
                text=f"Página {page + 1}/{total_pages}  •  {total} bases  •  /scout imagen [id] para foto"
            )

        view = ScoutPrivateListView(self.bot, rows, target_map, page)

        if edit:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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

    @discord.ui.button(label="\u25c4", style=discord.ButtonStyle.blurple, custom_id="scout_priv_prev")
    async def prev_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.cogs.get("Scouting")
        if cog:
            rows = await _fetch_scout_rows(self.bot.db, interaction.guild_id, self.target_map)
            await cog._send_private_scout_page(
                interaction,
                rows,
                self.target_map,
                page=max(0, self.page - 1),
                edit=True,
            )

    @discord.ui.button(label="\u25ba", style=discord.ButtonStyle.blurple, custom_id="scout_priv_next")
    async def next_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.cogs.get("Scouting")
        if cog:
            rows = await _fetch_scout_rows(self.bot.db, interaction.guild_id, self.target_map)
            total_pages = max(1, (len(rows) + SCOUT_PAGE_SIZE - 1) // SCOUT_PAGE_SIZE)
            await cog._send_private_scout_page(
                interaction,
                rows,
                self.target_map,
                page=min(total_pages - 1, self.page + 1),
                edit=True,
            )


async def setup(bot):
    await bot.add_cog(Scouting(bot))
