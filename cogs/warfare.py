import os
import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
import datetime
from cogs.server_status import get_guild_servers


async def update_blacklist_dashboards(bot):
    """Actualiza todos los mensajes de lista negra (dashboards)."""

    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM blacklist_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Recuperación de registros de la Blacklist
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM blacklist ORDER BY id DESC")
        rows = await cursor.fetchall()

    if not rows:
        embed = discord.Embed(
            title="☠️ Blacklist de Tribu",
            description="No hay jugadores en la lista negra.",
            color=discord.Color.darker_grey(),
        )
        embed.set_footer(
            text="💡 /blacklist_add para añadir | /blacklist_mod para modificar"
        )
    else:
        embed = discord.Embed(
            title="☠️ Blacklist de Tribu", color=discord.Color.dark_grey()
        )
        for row in rows:
            # ID: Player [Tribe] - Map
            # Notes
            embed.add_field(
                name=f"🆔 {row['id']} | 👤 **{row['player']}**",
                value=f"🏠 **Tribu:** {row['tribe']}\n🗺️ **Mapa:** {row['map']}\n📝 **Nota:** {row['notes']}\n────────────────",
                inline=False,
            )

        embed.set_footer(
            text="💡 /blacklist_add para añadir | /blacklist_mod para modificar | Botón para borrar."
        )

    view = BlacklistView(bot)
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
            print(f"Error updating blacklist dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos o inaccesibles
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM blacklist_messages WHERE id = ?", (mid,))
            await db.commit()


async def update_kda_dashboards(bot, guild_id=None):
    """Actualiza todos los mensajes persistentes del Ranking KDA (El Más Manco)."""
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        if guild_id:
            cursor = await db.execute(
                "SELECT * FROM kda_messages WHERE guild_id = ?", (guild_id,)
            )
        else:
            cursor = await db.execute("SELECT * FROM kda_messages")
        dashboards = await cursor.fetchall()

    if not dashboards:
        return

    # Generación del Leaderboard con cálculo dinámico de K/D
    async with aiosqlite.connect(bot.db_name) as db:
        db.row_factory = aiosqlite.Row
        # Ordenación ascendente por K/D (Peor ratio = "El Más Manco").
        # Prevención de división por cero tratando muertes=0 como 1 lógicamente en la consulta.
        if guild_id:
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
        else:
            cursor = await db.execute("""
                SELECT player_name, kills, deaths,
                       CAST(kills AS FLOAT) / CASE WHEN deaths = 0 THEN 1 ELSE deaths END as kd_ratio
                FROM tribe_kda
                ORDER BY kd_ratio ASC, deaths DESC
            """)
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
            print(f"Error updating KDA dash {dash['id']}: {e}")

    # Purgado de dashboards inactivos
    if messages_to_remove:
        async with aiosqlite.connect(bot.db_name) as db:
            for mid in messages_to_remove:
                await db.execute("DELETE FROM kda_messages WHERE id = ?", (mid,))
            await db.commit()


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
            await db.execute("DELETE FROM blacklist WHERE id = ?", (bid,))
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ Entrada ID {bid} eliminada.", ephemeral=True
        )
        await update_blacklist_dashboards(self.bot)


class BlacklistView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Eliminar (por ID)",
        style=discord.ButtonStyle.danger,
        custom_id="blacklist_delete_btn",
        emoji="🗑️",
    )
    async def delete_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(DeleteBlacklistModal(self.bot))


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
                print("⚠️ Detectada versión antigua de Blacklist. Migrando tabla...")
                try:
                    # Renombrado de la tabla legacy (Backup)
                    backup_name = (
                        f"blacklist_backup_{int(datetime.datetime.now().timestamp())}"
                    )
                    await db.execute(f"ALTER TABLE blacklist RENAME TO {backup_name}")
                    print(f"✅ Tabla antigua renombrada a {backup_name}")

                    # Creación de la tabla saneada (Nuevo esquema)
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
                    print("✅ Nueva tabla blacklist creada con schema correcto.")
                    await db.commit()
                except Exception as e:
                    print(f"❌ Error durante la migración de Blacklist: {e}")

    # --- Funciones de Autocompletado ---
    async def tribe_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute(
                "SELECT DISTINCT tribe FROM blacklist WHERE tribe LIKE ? ORDER BY tribe ASC LIMIT 25",
                (f"%{current}%",),
            )
            rows = await cursor.fetchall()

        choices = [
            app_commands.Choice(name=row[0], value=row[0]) for row in rows if row[0]
        ]
        # Retorno de coincidencias o permite texto libre por defecto (Discord behavior)
        return choices

    async def map_autocomplete(
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
                "INSERT INTO blacklist_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
            )
            await db.commit()

        await update_blacklist_dashboards(self.bot)

    @app_commands.command(
        name="blacklist_add", description="Añade un jugador a la Blacklist."
    )
    @app_commands.describe(
        jugador="Nombre del jugador",
        tribu="Tribu (Selecciona o escribe nueva)",
        mapa="Mapa principal",
        notas="Motivo o notas adicionales",
    )
    @app_commands.autocomplete(tribu=tribe_autocomplete, mapa=map_autocomplete)
    async def blacklist_add(
        self,
        interaction: discord.Interaction,
        jugador: str,
        tribu: str,
        mapa: str,
        notas: str,
    ):
        created_at = datetime.date.today().isoformat()

        async with aiosqlite.connect(self.bot.db_name) as db:
            await db.execute(
                """
                INSERT INTO blacklist (player, tribe, map, notes, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (jugador, tribu, mapa, notas, created_at),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ **{jugador}** ({tribu}) añadido a la blacklist.", ephemeral=False
        )
        await update_blacklist_dashboards(self.bot)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

    @app_commands.command(
        name="blacklist_mod", description="Modifica una entrada de la Blacklist."
    )
    @app_commands.describe(
        id="ID de la entrada", campo="Campo a modificar", nuevo_valor="Nuevo valor"
    )
    @app_commands.choices(
        campo=[
            app_commands.Choice(name="Nombre Jugador", value="player"),
            app_commands.Choice(name="Tribu", value="tribe"),
            app_commands.Choice(name="Mapa", value="map"),
            app_commands.Choice(name="Notas", value="notes"),
        ]
    )
    async def blacklist_mod(
        self,
        interaction: discord.Interaction,
        id: int,
        campo: app_commands.Choice[str],
        nuevo_valor: str,
    ):
        # Validación de existencia del registro por ID
        async with aiosqlite.connect(self.bot.db_name) as db:
            cursor = await db.execute("SELECT id FROM blacklist WHERE id = ?", (id,))
            row = await cursor.fetchone()

            if not row:
                await interaction.response.send_message(
                    f"❌ No existe la entrada ID {id}.", ephemeral=True
                )
                return

            # Update
            col_name = campo.value
            await db.execute(
                f"UPDATE blacklist SET {col_name} = ? WHERE id = ?", (nuevo_valor, id)
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ ID {id} actualizado: **{campo.name}** -> {nuevo_valor}",
            ephemeral=False,
        )
        await update_blacklist_dashboards(self.bot)

        await asyncio.sleep(5)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except Exception:
            pass

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
    @app_commands.autocomplete(mapa=map_autocomplete)
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
                "INSERT INTO kda_messages (channel_id, message_id) VALUES (?, ?)",
                (interaction.channel_id, message.id),
            )
            await db.commit()

        await update_kda_dashboards(self.bot)

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
                "INSERT INTO tribe_characters (character_name, player_name) VALUES (?, ?) ON CONFLICT(character_name) DO UPDATE SET player_name=excluded.player_name",
                (personaje, jugador),
            )
            # Inicialización segura del perfil del jugador en el Tracker KDA a 0
            await db.execute(
                "INSERT OR IGNORE INTO tribe_kda (player_name, kills, deaths) VALUES (?, 0, 0)",
                (jugador,),
            )
            await db.commit()

        await interaction.response.send_message(
            f"✅ Ahora el personaje in-game **{personaje}** registrará muertes y bajas para el jugador **{jugador}**.",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot)

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
                "DELETE FROM tribe_characters WHERE character_name = ?", (personaje,)
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
            await db.execute("DELETE FROM tribe_kda WHERE player_name = ?", (jugador,))
            await db.execute(
                "DELETE FROM tribe_characters WHERE player_name = ?", (jugador,)
            )
            await db.commit()

        await interaction.response.send_message(
            f"🗑️ El jugador **{jugador}** ha sido borrado del Leaderboard (Kills y Muertes reseteadas).",
            ephemeral=False,
        )
        await update_kda_dashboards(self.bot)


async def setup(bot):
    await bot.add_cog(Warfare(bot))
