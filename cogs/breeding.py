import discord
from discord import app_commands
import aiosqlite
import asyncio
import logging
import datetime
from discord.ext import commands, tasks

# Opciones del menú de estadísticas
STAT_CHOICES = [
    app_commands.Choice(name="Vida (HP)", value="hp"),
    app_commands.Choice(name="Estamina", value="stam"),
    app_commands.Choice(name="Peso", value="weight"),
    app_commands.Choice(name="Daño (Melee)", value="melee"),
    app_commands.Choice(name="Oxígeno", value="oxy"),
    app_commands.Choice(name="Comida", value="food"),
    app_commands.Choice(name="Velocidad", value="speed"),
]


class StatSelectView(discord.ui.View):
    def __init__(self, bot, dino: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.dino = dino

        # Configuración de opciones del menú desplegable
        options = [
            discord.SelectOption(label="Vida (HP)", value="hp"),
            discord.SelectOption(label="Estamina", value="stam"),
            discord.SelectOption(label="Peso", value="weight"),
            discord.SelectOption(label="Daño (Melee)", value="melee"),
            discord.SelectOption(label="Oxígeno", value="oxy"),
            discord.SelectOption(label="Comida", value="food"),
            discord.SelectOption(label="Velocidad", value="speed"),
        ]

        self.select = discord.ui.Select(
            placeholder="Selecciona la estadística a mutar (+2)",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        stat_selected = self.select.values[0]

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM dinos WHERE especie = ? AND guild_id = ?", (self.dino, interaction.guild_id,)
            )
            row = await cursor.fetchone()

            if row:
                old_val = row[stat_selected] or 0
                new_val = old_val + 2
                await db.execute(
                    f"UPDATE dinos SET {stat_selected} = ? WHERE especie = ? AND guild_id = ?",
                    (new_val, self.dino, interaction.guild_id,),
                )

                # Registro de mutación en log
                breeding_cog = self.bot.get_cog("Breeding")
                if breeding_cog:
                    breeding_cog.log_mutation(interaction.guild_id, f"MUTATION: {self.dino} {stat_selected} +2")
            else:
                new_val = 2
                await db.execute(
                    f"INSERT INTO dinos (guild_id, especie, {stat_selected}) VALUES (?, ?, ?)",
                    (interaction.guild_id, self.dino, new_val),
                )

            await db.commit()

        # Actualización del dashboard
        await interaction.response.edit_message(
            content=f"✅ Muta registrada: **{self.dino}** (+2 en {stat_selected}). Nuevo valor: {new_val}",
            view=None,
        )
        await update_breeding_dashboards(self.bot, interaction.guild_id)


class DinoSelectView(discord.ui.View):
    def __init__(self, bot, dinos):
        super().__init__(timeout=120)
        self.bot = bot

        options = []
        # Límite de 25 elementos en select de Discord
        for dino in dinos[:25]:
            options.append(discord.SelectOption(label=dino, value=dino))

        self.select = discord.ui.Select(
            placeholder="Selecciona el dino",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        dino_selected = self.select.values[0]
        view = StatSelectView(self.bot, dino_selected)
        await interaction.response.edit_message(
            content=f"Has seleccionado **{dino_selected}**. Ahora selecciona la stat:",
            view=view,
        )


class AlarmSelectView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=120)
        self.bot = bot

        options = [
            discord.SelectOption(label="1,5 Horas", value="1.5", emoji="⏰"),
            discord.SelectOption(label="2,5 Horas", value="2.5", emoji="⏰"),
            discord.SelectOption(label="4 Horas", value="4.0", emoji="⏰"),
            discord.SelectOption(label="10 Horas", value="10.0", emoji="⏰"),
        ]

        self.select = discord.ui.Select(
            placeholder="Elige cuándo sonará la alarma...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        horas_select = float(self.select.values[0])
        alert_time = datetime.datetime.now() + datetime.timedelta(hours=horas_select)

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO breeding_alarms (guild_id, user_id, channel_id, alert_time)
                VALUES (?, ?, ?, ?)
            """,
                (
                    interaction.guild_id,
                    interaction.user.id,
                    interaction.channel_id,
                    alert_time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            await db.commit()

        await interaction.response.edit_message(
            content=f"✅ Alarma configurada. Te avisaré en **{horas_select} horas**.",
            view=None,
        )


class BreedingDinoSelectMenu(discord.ui.Select):
    """Menú desplegable persistente para seleccionar un dino del dashboard y ver sus stats en privado."""
    def __init__(self, bot, current_dinos):
        self.bot = bot
        
        options = []
        if not current_dinos:
            options.append(discord.SelectOption(label="Sin dinos", value="none"))
        else:
            for dino in current_dinos[:25]:
                options.append(discord.SelectOption(label=dino, value=dino, emoji="🦖"))
            
        super().__init__(
            custom_id="breeding_dino_select",
            placeholder="Selecciona un dino para verlo en detalle...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        dino_name = self.values[0]
        
        if dino_name == "none":
            await interaction.followup.send("No hay dinos disponibles.", ephemeral=True)
            return

        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM dinos WHERE especie = ? AND guild_id = ?", (dino_name, interaction.guild_id,)
            )
            row = await cursor.fetchone()

        if not row:
            await interaction.followup.send(f"❌ No se encontraron datos para **{dino_name}**.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🧬 Stats Detalladas: {row['especie']}", color=discord.Color.green()
        )

        hp = row["hp"] or 0
        stam = row["stam"] or 0
        weight = row["weight"] or 0
        melee = row["melee"] or 0
        oxy = row["oxy"] or 0
        food = row["food"] or 0
        speed = row["speed"] or 0

        if hp > 0: 
            embed.add_field(name="❤️ Vida (HP)", value=str(hp), inline=True)
        if stam > 0: 
            embed.add_field(name="⚡ Estamina", value=str(stam), inline=True)
        if weight > 0: 
            embed.add_field(name="⚖️ Peso", value=str(weight), inline=True)
        if melee > 0: 
            embed.add_field(name="⚔️ Daño (Melee)", value=str(melee), inline=True)
        if oxy > 0: 
            embed.add_field(name="🫧 Oxígeno", value=str(oxy), inline=True)
        if food > 0: 
            embed.add_field(name="🍖 Comida", value=str(food), inline=True)
        if speed > 0: 
            embed.add_field(name="💨 Velocidad", value=str(speed), inline=True)

        embed.set_footer(text=f"ID Interno: {row['especie']}")
        await interaction.followup.send(embed=embed, ephemeral=True)


class BreedingDashboardView(discord.ui.View):
    def __init__(self, bot, current_dinos=None):
        super().__init__(timeout=None)
        self.bot = bot
        
        # Inyectamos el menú desplegable si hay dinos
        if current_dinos is not None:
            self.add_item(BreedingDinoSelectMenu(bot, current_dinos))
        else:
            # Requerido para persistencia de la vista base
            self.add_item(BreedingDinoSelectMenu(bot, []))

    @discord.ui.button(
        label="Nueva muta",
        style=discord.ButtonStyle.primary,
        custom_id="breeding_nueva_muta_btn",
        emoji="🧬",
    )
    async def nueva_muta_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT DISTINCT especie FROM dinos WHERE guild_id = ? ORDER BY especie ASC", (interaction.guild_id,)
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.response.send_message(
                "❌ No hay dinos registrados en la base de datos.", ephemeral=True
            )
            return

        dinos = [row[0] for row in rows]
        view = DinoSelectView(self.bot, dinos)
        await interaction.response.send_message(
            "Selecciona el Dino al que aplicarle la muta (+2):",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Alarmas",
        style=discord.ButtonStyle.secondary,
        custom_id="breeding_alarms_btn",
        emoji="⏰",
    )
    async def alarmas_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        view = AlarmSelectView(self.bot)
        await interaction.response.send_message(
            "Selecciona el tiempo de la alarma para este canal:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Ver Logs Muta",
        style=discord.ButtonStyle.secondary,
        custom_id="breeding_log_mutas_btn",
        emoji="📜",
    )
    async def ver_logs_mutas_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        import os

        # Determinar el directorio de logs de mutaciones de este servidor
        if not self.bot.log_filename:
            await interaction.response.send_message("El sistema de logs no está configurado de forma estática.", ephemeral=True)
            return
            
        log_dir = os.path.join(os.path.dirname(self.bot.log_filename), str(interaction.guild_id))
        mutations = []

        if not os.path.exists(log_dir):
            await interaction.response.send_message(
                "No hay logs de mutaciones para este servidor.", ephemeral=True
            )
            return

        try:
            # Lectura de ficheros .log del directorio
            for filename in os.listdir(log_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(log_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            if "MUTATION:" in line:
                                parts = line.split("MUTATION:")
                                if len(parts) < 2:
                                    continue

                                # yyyy-mm-dd hh:mm:ss
                                timestamp = line[:19]
                                content = parts[1].strip()

                                try:
                                    dino, stat, amount = content.rsplit(maxsplit=2)
                                    if "DOUBLE" in line:
                                        mutations.append(
                                            (
                                                timestamp,
                                                f"⏰ `{timestamp}`: **Doble muta** 🧬 **{dino}** en **{stat}**",
                                            )
                                        )
                                    else:
                                        mutations.append(
                                            (
                                                timestamp,
                                                f"⏰ `{timestamp}`: **Muta** 🧬 **{dino}** en **{stat}**",
                                            )
                                        )
                                except Exception:
                                    mutations.append(
                                        (timestamp, f"`{timestamp}`: {content}")
                                    )

            if not mutations:
                await interaction.response.send_message(
                    "No se han registrado mutaciones históricamente.", ephemeral=True
                )
            else:
                mutations.sort(key=lambda x: x[0], reverse=True)
                recent_mutations = [mut[1] for mut in mutations[:15]]
                response_text = "\n".join(recent_mutations)

                embed = discord.Embed(
                    title="📜 Últimas Mutaciones Registradas",
                    description=response_text,
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Error al leer logs: {e}", ephemeral=True
            )

    @discord.ui.button(
        style=discord.ButtonStyle.secondary,
        custom_id="breeding_prev_btn",
        emoji="◀️",
        row=2
    )
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.message.embeds:
            await interaction.response.defer()
            return

        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text if embed.footer else ""
        
        import re
        match = re.search(r"Página (\d+)/(\d+)", footer_text)
        if match:
            current_page = int(match.group(1))
            
            if current_page > 1:
                new_page = current_page - 1
                await update_breeding_dashboards(self.bot, interaction.guild_id, interaction.message.id, new_page)
                await interaction.response.defer()
            else:
                await interaction.response.defer()
        else:
            await interaction.response.defer()

    @discord.ui.button(
        style=discord.ButtonStyle.secondary,
        custom_id="breeding_next_btn",
        emoji="▶️",
        row=2
    )
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not interaction.message.embeds:
            await interaction.response.defer()
            return

        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text if embed.footer else ""
        
        import re
        match = re.search(r"Página (\d+)/(\d+)", footer_text)
        if match:
            current_page = int(match.group(1))
            total_pages = int(match.group(2))
            
            if current_page < total_pages:
                new_page = current_page + 1
                await update_breeding_dashboards(self.bot, interaction.guild_id, interaction.message.id, new_page)
                await interaction.response.defer()
            else:
                await interaction.response.defer()


async def update_breeding_dashboards(bot, guild_id: int, specific_message_id=None, page=1):
    """Actualiza todos los mensajes de lista de líneas (dashboards)."""

    # Extracción de dashboards activos
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        if specific_message_id:
            cursor = await db.execute("SELECT * FROM breeding_messages WHERE message_id = ? AND guild_id = ?", (specific_message_id, guild_id,))
        else:
            cursor = await db.execute("SELECT * FROM breeding_messages WHERE guild_id = ?", (guild_id,))
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Consulta de especies registradas
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM dinos WHERE guild_id = ? ORDER BY especie ASC", (guild_id,))
        rows = await cursor.fetchall()

    # Construcción de Embed
    if not rows:
        embed = discord.Embed(
            title="🧬 Líneas de Crianza",
            description="No hay líneas registradas aún.",
            color=discord.Color.gold(),
        )
        embed.set_footer(
            text="💡 Usa /linea_add para registrar o /linea_mod para actualizar."
        )
    else:
        import math
        items_per_page = 10
        total_rows = len(rows)
        total_pages = math.ceil(total_rows / items_per_page)
        
        # Validación de página límite
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
            
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        rows_to_display = rows[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🧬 LÍNEAS DE CRIANZA (Top Stats)", color=discord.Color.from_rgb(255, 215, 0)
        )
        
        lines = []
        lines.append(f"📊 `{total_rows}` especies registradas · Página `{page}/{total_pages}`")
        lines.append("")
        
        for row in rows_to_display:
            hp = row["hp"] or 0
            stam = row["stam"] or 0
            weight = row["weight"] or 0
            melee = row["melee"] or 0
            oxy = row["oxy"] or 0
            food = row["food"] or 0
            speed = row["speed"] or 0

            stats_list = []
            if hp > 0:
                stats_list.append(f"❤️ **{hp}**")
            if stam > 0:
                stats_list.append(f"⚡ **{stam}**")
            if weight > 0:
                stats_list.append(f"⚖️ **{weight}**")
            if melee > 0:
                stats_list.append(f"⚔️ **{melee}**")
            if oxy > 0:
                stats_list.append(f"🫧 **{oxy}**")
            if food > 0:
                stats_list.append(f"🍖 **{food}**")
            if speed > 0:
                stats_list.append(f"💨 **{speed}**")

            stats_text = " | ".join(stats_list) if stats_list else "*Sin stats*"
            
            lines.append(f"> 🦖 **{row['especie']}**")
            lines.append(f">  {stats_text}")
            lines.append("")
        
        embed.description = "\n".join(lines).strip()

        embed.set_footer(
            text="💡 /linea_add para registrar · /linea_mod para actualizar"
        )

    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                
                # Si estamos en modo update masivo (no specific), mantenemos la página en la que estuviera
                current_page = 1
                if not specific_message_id and message.embeds:
                    footer_text = message.embeds[0].footer.text if message.embeds[0].footer else ""
                    import re
                    match = re.search(r"Página (\d+)/(\d+)", footer_text)
                    if match:
                        current_page = int(match.group(1))
                        # Tenemos que regenerar el embed para su página guardada
                        if current_page != page:
                            if current_page < 1: 
                                current_page = 1
                            if current_page > total_pages: 
                                current_page = total_pages
                            local_start = (current_page - 1) * items_per_page
                            local_end = local_start + items_per_page
                            local_rows = rows[local_start:local_end]
                            
                            local_embed = discord.Embed(
                                title="🧬 Líneas de Crianza (Top Stats)", color=discord.Color.gold()
                            )
                            for l_row in local_rows:
                                l_hp = l_row["hp"] or 0
                                l_stam = l_row["stam"] or 0
                                l_weight = l_row["weight"] or 0
                                l_melee = l_row["melee"] or 0
                                l_oxy = l_row["oxy"] or 0
                                l_food = l_row["food"] or 0
                                l_speed = l_row["speed"] or 0

                                l_stats_list = []
                                if l_hp > 0: 
                                    l_stats_list.append(f"❤️ HP: **{l_hp}**")
                                if l_stam > 0: 
                                    l_stats_list.append(f"⚡ Stam: **{l_stam}**")
                                if l_weight > 0: 
                                    l_stats_list.append(f"⚖️ Peso: **{l_weight}**")
                                if l_melee > 0: 
                                    l_stats_list.append(f"⚔️ Melee: **{l_melee}**")
                                if l_oxy > 0: 
                                    l_stats_list.append(f"🫧 Oxy: **{l_oxy}**")
                                if l_food > 0: 
                                    l_stats_list.append(f"🍖 Food: **{l_food}**")
                                if l_speed > 0: 
                                    l_stats_list.append(f"💨 Speed: **{l_speed}**")

                                l_stats_text = " | ".join(l_stats_list) if l_stats_list else "Sin stats registradas."
                                l_stats_text += "\n────────────────────────────"
                                local_embed.add_field(name=f"🦖 {l_row['especie']}", value=l_stats_text, inline=False)
                                
                            local_embed.set_footer(
                                text=f"Página {current_page}/{total_pages} • {total_rows} dinos total | 💡 Usa /linea_add para añadir nuevo dino."
                            )
                            target_embed = local_embed
                            
                            current_dinos = [r["especie"] for r in local_rows]
                        else:
                            target_embed = embed
                            current_dinos = [r["especie"] for r in rows_to_display]
                    else:
                        target_embed = embed
                        current_dinos = [r["especie"] for r in rows_to_display]
                else:
                    target_embed = embed
                    current_dinos = [r["especie"] for r in rows_to_display] if rows else []

                view = BreedingDashboardView(bot, current_dinos)
                await message.edit(embed=target_embed, view=view)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            print(f"Error updating breeding dash {dash['id']}: {e}")

    # Limpieza de dashboards inactivos o rotos
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM breeding_messages WHERE id = ?", (mid,))
            await db.commit()


class Breeding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Intento de migración de columnas por versión antigua de DB
        asyncio.create_task(self.check_schema())
        self.check_alarms.start()

    def cog_unload(self):
        self.check_alarms.cancel()

    @tasks.loop(minutes=1)
    async def check_alarms(self):
        try:
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            async with aiosqlite.connect(self.bot.db_name) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM breeding_alarms WHERE alert_time <= ?", (now_str,)
                )
                alarms = await cursor.fetchall()

                if not alarms:
                    return

                from main import (
                    DismissAlarmView,
                )  # Asegurar importar la vista persistente

                for alarm in alarms:
                    try:
                        channel = self.bot.get_channel(
                            alarm["channel_id"]
                        ) or await self.bot.fetch_channel(alarm["channel_id"])
                        if channel:
                            view = DismissAlarmView()
                            await channel.send(
                                f"🔔 <@{alarm['user_id']}> Tu alarma ha expirado.",
                                view=view,
                            )
                    except Exception as e:
                        logging.getLogger("ArkTribeBot").error(
                            f"Error procesando alarma {alarm['id']}: {e}"
                        )

                    # Eliminación de alarma ejecutada
                    # Borrado de defensa en profundidad (guild_id)
                    await db.execute(
                        "DELETE FROM breeding_alarms WHERE id = ? AND guild_id = ?",
                        (alarm["id"], alarm["guild_id"]),
                    )
                await db.commit()
        except Exception as e:
            logging.getLogger("ArkTribeBot").error(
                f"Error en loop de breeding alarms: {e}"
            )

    @check_alarms.before_loop
    async def before_check_alarms(self):
        await self.bot.wait_until_ready()

    async def check_schema(self):
        async with aiosqlite.connect(self.bot.db_name) as db:
            try:
                await db.execute("ALTER TABLE dinos ADD COLUMN oxy INTEGER")
                print("Migración: Added oxy column")
                await db.commit()
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE dinos ADD COLUMN food INTEGER")
                print("Migración: Added food column")
                await db.commit()
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE dinos ADD COLUMN speed INTEGER")
                print("Migración: Added speed column")
                await db.commit()
            except Exception:
                pass

    def log_mutation(self, guild_id: int, message: str):
        import os
        import logging

        logger = logging.getLogger(f"ArkTribeBot.guild.{guild_id}")
        if not logger.handlers:
            base_log_dir = os.path.dirname(self.bot.log_filename)
            timestamp_name = os.path.basename(self.bot.log_filename)
            guild_dir = os.path.join(base_log_dir, str(guild_id))
            if not os.path.exists(guild_dir):
                os.makedirs(guild_dir)
            
            handler = logging.FileHandler(os.path.join(guild_dir, timestamp_name), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = True

        logger.info(message)

    async def upsert_stat(self, dino, stat_col, puntos, guild_id):
        """Helper para Insertar o Actualizar una stat de una especie."""
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Verificación de existencia
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dinos WHERE especie = ? AND guild_id = ?", (dino, guild_id,))
            row = await cursor.fetchone()

            if row:
                # Actualización
                old_val = row[stat_col] or 0
                diff = puntos - old_val

                await db.execute(
                    f"UPDATE dinos SET {stat_col} = ? WHERE especie = ? AND guild_id = ?", (puntos, dino, guild_id,)
                )
                action = "stats actualizados"

                # Registro de mutaciones en log
                if diff == 2:
                    self.log_mutation(guild_id, f"MUTATION: {dino} {stat_col} +2")
                elif diff == 4:
                    self.log_mutation(guild_id, f"DOUBLE MUTATION: {dino} {stat_col} +4")

            else:
                # Inserción
                await db.execute(
                    f"INSERT INTO dinos (guild_id, especie, {stat_col}) VALUES (?, ?, ?)",
                    (guild_id, dino, puntos),
                )
                action = "registrada (nueva línea)"

            await db.commit()
        return action

    @app_commands.command(
        name="linea_add",
        description="Registra/Actualiza una estadística para una línea.",
    )
    @app_commands.choices(estadistica=STAT_CHOICES)
    @app_commands.describe(
        dino="Especie del dino (ej. Rex)",
        estadistica="Qué estadística registrar",
        puntos="Valor numérico",
    )
    async def linea_add(
        self,
        interaction: discord.Interaction,
        dino: str,
        estadistica: app_commands.Choice[str],
        puntos: int,
    ):
        action = await self.upsert_stat(dino, estadistica.value, puntos, interaction.guild_id)

        await interaction.response.send_message(
            f"✅ 🧬 **{dino}** con **{puntos}** en **{estadistica.name}** {action}.",
            ephemeral=False,
        )
        await update_breeding_dashboards(self.bot, interaction.guild_id)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    async def dino_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT DISTINCT especie FROM dinos WHERE especie LIKE ? AND guild_id = ? ORDER BY especie ASC LIMIT 25",
                (f"%{current}%", interaction.guild_id,),
            )
            rows = await cursor.fetchall()

        return [app_commands.Choice(name=row[0], value=row[0]) for row in rows]

    @app_commands.command(
        name="linea_mod",
        description="Modifica una estadística específica (Igual que linea_add).",
    )
    @app_commands.choices(estadistica=STAT_CHOICES)
    @app_commands.describe(
        dino="Especie del dino (ej. Rex)",
        estadistica="Qué estadística actualizar",
        puntos="Nuevo valor (Numérico)",
    )
    @app_commands.autocomplete(dino=dino_autocomplete)
    async def linea_mod(
        self,
        interaction: discord.Interaction,
        dino: str,
        estadistica: app_commands.Choice[str],
        puntos: int,
    ):
        # Flujo idéntico a linea_add utilizando lógica Single Row
        await self.upsert_stat(dino, estadistica.value, puntos, interaction.guild_id)

        await interaction.response.send_message(
            f"✅ Estadística modificada: **{dino}** -> **{estadistica.name}**: {puntos}.",
            ephemeral=False,
        )
        await update_breeding_dashboards(self.bot, interaction.guild_id)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    @app_commands.command(
        name="lineas",
        description="Muestra el panel de líneas de crianza (Auto-actualizable).",
    )
    async def lineas(self, interaction: discord.Interaction):
        # Generación de contenido inicial
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dinos WHERE guild_id = ? ORDER BY especie ASC", (interaction.guild_id,))
            rows = await cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                title="🧬 Líneas de Crianza",
                description="No hay líneas registradas aún.",
                color=discord.Color.gold(),
            )
            embed.set_footer(
                text="💡 Usa /linea_add para registrar o /linea_mod para actualizar."
            )
        else:
            embed = discord.Embed(
                title="🧬 Líneas de Crianza (Top Stats)", color=discord.Color.gold()
            )
            for row in rows:
                hp = row["hp"] or 0
                stam = row["stam"] or 0
                weight = row["weight"] or 0
                melee = row["melee"] or 0
                oxy = row["oxy"] or 0
                food = row["food"] or 0
                speed = row["speed"] or 0

                stats_list = []
                if hp > 0:
                    stats_list.append(f"❤️ HP: **{hp}**")
                if stam > 0:
                    stats_list.append(f"⚡ Stam: **{stam}**")
                if weight > 0:
                    stats_list.append(f"⚖️ Peso: **{weight}**")
                if melee > 0:
                    stats_list.append(f"⚔️ Melee: **{melee}**")
                if oxy > 0:
                    stats_list.append(f"🫧 Oxy: **{oxy}**")
                if food > 0:
                    stats_list.append(f"🍖 Food: **{food}**")
                if speed > 0:
                    stats_list.append(f"💨 Speed: **{speed}**")

                stats_text = (
                    " | ".join(stats_list) if stats_list else "Sin stats registradas."
                )
                stats_text += "\n────────────────────────────"

                embed.add_field(
                    name=f"🦖 {row['especie']}", value=stats_text, inline=False
                )

            embed.set_footer(
                text="💡 Usa /linea_add para añadir nuevo dino | /linea_mod para modificar stats."
            )

        # Pasamos las especies para el menú desplegable (máximo las primeras 10 visualizadas)
        current_dinos = [r["especie"] for r in rows[:10]] if rows else []
        view = BreedingDashboardView(self.bot, current_dinos)
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Guardado de Message ID para futuras actualizaciones
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO breeding_messages (guild_id, channel_id, message_id) VALUES (?, ?, ?)",
                (interaction.guild_id, interaction.channel_id, message.id),
            )
            await db.commit()

    @app_commands.command(
        name="linea_ver", description="Consulta las stats de una especie (Epímero)."
    )
    @app_commands.describe(dino="Especie a consultar")
    @app_commands.autocomplete(dino=dino_autocomplete)
    async def linea_ver(self, interaction: discord.Interaction, dino: str):
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dinos WHERE especie = ? AND guild_id = ?", (dino, interaction.guild_id,))
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"❌ No se encontró la especie **{dino}**.", ephemeral=True
            )
            return

        hp = row["hp"] or 0
        stam = row["stam"] or 0
        weight = row["weight"] or 0
        melee = row["melee"] or 0
        oxy = row["oxy"] or 0
        food = row["food"] or 0
        speed = row["speed"] or 0

        stats_list = []
        if hp > 0:
            stats_list.append(f"❤️ HP: **{hp}**")
        if stam > 0:
            stats_list.append(f"⚡ Stam: **{stam}**")
        if weight > 0:
            stats_list.append(f"⚖️ Peso: **{weight}**")
        if melee > 0:
            stats_list.append(f"⚔️ Melee: **{melee}**")
        if oxy > 0:
            stats_list.append(f"🫧 Oxy: **{oxy}**")
        if food > 0:
            stats_list.append(f"🍖 Food: **{food}**")
        if speed > 0:
            stats_list.append(f"💨 Speed: **{speed}**")

        stats_text = " | ".join(stats_list) if stats_list else "Sin stats registradas."

        embed = discord.Embed(title=f"🧬 Stats: {dino}", color=discord.Color.purple())
        embed.description = stats_text
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="log_mutas",
        description="Muestra las últimas 20 mutaciones registradas en el servidor.",
    )
    async def log_mutas(self, interaction: discord.Interaction):
        import os

        log_dir = os.path.join(os.path.dirname(self.bot.log_filename), str(interaction.guild_id))
        mutations = []

        if not os.path.exists(log_dir):
            await interaction.response.send_message(
                "No hay logs de mutaciones para este servidor.", ephemeral=True
            )
            return

        try:
            # Lectura de ficheros .log del directorio
            for filename in os.listdir(log_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(log_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            if "MUTATION:" in line:
                                parts = line.split("MUTATION:")
                                if len(parts) < 2:
                                    continue

                                # yyyy-mm-dd hh:mm:ss
                                timestamp = line[:19]
                                content = parts[1].strip()

                                try:
                                    dino, stat, amount = content.rsplit(maxsplit=2)
                                    if "DOUBLE" in line:
                                        mutations.append(
                                            (
                                                timestamp,
                                                f"⏰ `{timestamp}`: **Doble muta** 🧬 **{dino}** en **{stat}**",
                                            )
                                        )
                                    else:
                                        mutations.append(
                                            (
                                                timestamp,
                                                f"⏰ `{timestamp}`: **Muta** 🧬 **{dino}** en **{stat}**",
                                            )
                                        )
                                except Exception:
                                    mutations.append(
                                        (timestamp, f"`{timestamp}`: {content}")
                                    )

            if not mutations:
                await interaction.response.send_message(
                    "No se han registrado mutaciones históricamente.", ephemeral=True
                )
            else:
                # Ordenación descendente por marca de tiempo
                mutations.sort(key=lambda x: x[0], reverse=True)

                # Límite de 20 registros más recientes
                recent_mutations = [mut[1] for mut in mutations[:20]]
                response_text = "\n".join(recent_mutations)

                embed = discord.Embed(
                    title="🧬 Registro de Mutaciones (Últimas 20)",
                    description=response_text,
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"Error leyendo logs: {e}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Breeding(bot))
