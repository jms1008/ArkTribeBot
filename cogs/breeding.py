import discord
from discord import app_commands
import aiosqlite
import asyncio
import logging
import datetime
from discord.ext import commands, tasks

# Opciones de Estadísticas
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

        # Opciones para el select
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
                "SELECT * FROM dinos WHERE especie = ?", (self.dino,)
            )
            row = await cursor.fetchone()

            if row:
                old_val = row[stat_selected] or 0
                new_val = old_val + 2
                await db.execute(
                    f"UPDATE dinos SET {stat_selected} = ? WHERE especie = ?",
                    (new_val, self.dino),
                )

                # Log the mutation
                logging.getLogger("ArkTribeBot").info(
                    f"MUTATION: {self.dino} {stat_selected} +2"
                )
            else:
                new_val = 2
                await db.execute(
                    f"INSERT INTO dinos (especie, {stat_selected}) VALUES (?, ?)",
                    (self.dino, new_val),
                )

            await db.commit()

        # Refrescar dashboard
        await interaction.response.edit_message(
            content=f"✅ Muta registrada: **{self.dino}** (+2 en {stat_selected}). Nuevo valor: {new_val}",
            view=None,
        )
        await update_breeding_dashboards(self.bot)


class DinoSelectView(discord.ui.View):
    def __init__(self, bot, dinos):
        super().__init__(timeout=120)
        self.bot = bot

        options = []
        # Discord Select limits to 25 items
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
                INSERT INTO breeding_alarms (user_id, channel_id, alert_time)
                VALUES (?, ?, ?)
            """,
                (
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


class BreedingDashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

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
                "SELECT DISTINCT especie FROM dinos ORDER BY especie ASC"
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


async def update_breeding_dashboards(bot):
    """Actualiza todos los mensajes de lista de líneas (dashboards)."""

    # Obtener datos de todos los dashboards activos
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM breeding_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Consultar Dinos (Modo Single Row per Species)
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM dinos ORDER BY especie ASC")
        rows = await cursor.fetchall()

    # Construir Embed
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
            # Formatear valores (si son None, poner 0)
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

            embed.add_field(name=f"🦖 {row['especie']}", value=stats_text, inline=False)

        embed.set_footer(
            text="💡 Usa /linea_add para añadir nuevo dino | /linea_mod para modificar stats."
        )

    messages_to_remove = []

    for dash in dashboards:
        try:
            channel = bot.get_channel(dash["channel_id"]) or await bot.fetch_channel(
                dash["channel_id"]
            )
            if channel:
                message = await channel.fetch_message(dash["message_id"])
                view = BreedingDashboardView(bot)
                await message.edit(embed=embed, view=view)
            else:
                messages_to_remove.append(dash["id"])
        except (discord.NotFound, discord.Forbidden):
            messages_to_remove.append(dash["id"])
        except Exception as e:
            print(f"Error updating breeding dash {dash['id']}: {e}")

    # Limpiar dashboards rotos
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM breeding_messages WHERE id = ?", (mid,))
            await db.commit()


class Breeding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Intentar migración de columnas por si la DB es vieja
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

                    # Borrar ejecutada
                    await db.execute(
                        "DELETE FROM breeding_alarms WHERE id = ?", (alarm["id"],)
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

    async def upsert_stat(self, dino, stat_col, puntos):
        """Helper para Insertar o Actualizar una stat de una especie."""
        async with aiosqlite.connect(self.bot.db_name) as db:
            # Verificar si existe
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dinos WHERE especie = ?", (dino,))
            row = await cursor.fetchone()

            if row:
                # Update
                old_val = row[stat_col] or 0
                diff = puntos - old_val

                await db.execute(
                    f"UPDATE dinos SET {stat_col} = ? WHERE especie = ?", (puntos, dino)
                )
                action = "stats actualizados"

                # Log Mutations
                if diff == 2:
                    logging.getLogger("ArkTribeBot").info(
                        f"MUTATION: {dino} {stat_col} +2"
                    )
                elif diff == 4:
                    logging.getLogger("ArkTribeBot").info(
                        f"DOUBLE MUTATION: {dino} {stat_col} +4"
                    )

            else:
                # Insert
                await db.execute(
                    f"INSERT INTO dinos (especie, {stat_col}) VALUES (?, ?)",
                    (dino, puntos),
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
        action = await self.upsert_stat(dino, estadistica.value, puntos)

        await interaction.response.send_message(
            f"✅ 🧬 **{dino}** con **{puntos}** en **{estadistica.name}** {action}.",
            ephemeral=False,
        )
        await update_breeding_dashboards(self.bot)

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
                "SELECT DISTINCT especie FROM dinos WHERE especie LIKE ? ORDER BY especie ASC LIMIT 25",
                (f"%{current}%",),
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
        # Es funcionalmente idéntico a linea_add con la nueva lógica de 'Single Row'
        await self.upsert_stat(dino, estadistica.value, puntos)

        await interaction.response.send_message(
            f"✅ Estadística modificada: **{dino}** -> **{estadistica.name}**: {puntos}.",
            ephemeral=False,
        )
        await update_breeding_dashboards(self.bot)

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
        # Generar contenido inicial
        async with aiosqlite.connect(self.bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dinos ORDER BY especie ASC")
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

        view = BreedingDashboardView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Guardar Message ID para updates
        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                "INSERT INTO breeding_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
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
            cursor = await db.execute("SELECT * FROM dinos WHERE especie = ?", (dino,))
            row = await cursor.fetchone()

        if not row:
            await interaction.response.send_message(
                f"No se encontró información para **{dino}**.", ephemeral=True
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

    @app_commands.command(
        name="log_mutas",
        description="Muestra las últimas 20 mutaciones registradas en el servidor.",
    )
    async def log_mutas(self, interaction: discord.Interaction):
        import os

        log_dir = os.path.dirname(self.bot.log_filename)
        mutations = []

        try:
            # Leer todos los archivos .log en la carpeta
            for filename in os.listdir(log_dir):
                if filename.endswith(".log"):
                    filepath = os.path.join(log_dir, filename)
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            if "MUTATION:" in line:
                                parts = line.split("MUTATION:")
                                if len(parts) < 2:
                                    continue

                                timestamp = line[:19]  # yyyy-mm-dd hh:mm:ss
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
                # Sort by timestamp ascending, then reverse to get most recent first
                mutations.sort(key=lambda x: x[0], reverse=True)

                # Take top 20
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
