import discord
from discord.ext import commands
import aiosqlite
import re
import random
import json
import logging

from main import PoliciaSosView, get_guild_logger

class LogProcessor(commands.Cog, name="LogProcessor"):
    """
    Cog encargado de procesar los mensajes en los canales de log.
    Saca la lógica fuera de main.py para mantener el código modular.
    Incluye el KDA Tracker, SOS Policía y sarcasmos de muerte.
    """
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("ArkTribeBot.LogProcessor")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes del propio bot
        if message.author.id == self.bot.user.id:
            return

        guild_id = message.guild.id if message.guild else None

        # Verificación del canal puente de logs configurado para este servidor
        is_log_channel = False
        sos_channel_id = None
        guild_log = logging.getLogger("ArkTribeBot.Global")  # Fallback

        if guild_id:
            guild_log = get_guild_logger(guild_id)
            async with aiosqlite.connect(self.bot.db_name) as db:
                c = await db.execute(
                    "SELECT log_channel_id, sos_channel_id FROM guild_config WHERE guild_id = ?",
                    (guild_id,),
                )
                config = await c.fetchone()
                if config:
                    log_channel_id, sos_channel_id = config
                    if log_channel_id and message.channel.id == log_channel_id:
                        is_log_channel = True

        if is_log_channel:
            # Extraer texto de Embeds enviados por webhooks/bots de logs
            content_lower = message.content.lower()
            if message.embeds:
                for embed in message.embeds:
                    if embed.description:
                        content_lower += " " + embed.description.lower()
                    if embed.title:
                        content_lower += " " + embed.title.lower()

            # Lectura case-insensitive
            # Detección de mención al rol @policia y emoji 🔪
            contains_policia = "@policia" in content_lower or "<@&" in content_lower
            contains_knife = (
                "was :knife:" in content_lower
                or "fue :knife:" in content_lower
                or "was 🔪" in content_lower
                or "fue 🔪" in content_lower
            )

            if contains_knife:
                # Extraer contenido original formateado
                texto_original = message.content
                if (
                    not texto_original
                    and message.embeds
                    and message.embeds[0].description
                ):
                    texto_original = message.embeds[0].description

                # Procesamiento de SOS de Policía
                if contains_policia and sos_channel_id:
                    map_match = re.search(r"\((.*?)\)", texto_original)
                    map_name = map_match.group(1) if map_match else "Desconocido"
                    try:
                        sos_channel = self.bot.get_channel(
                            sos_channel_id
                        ) or await self.bot.fetch_channel(sos_channel_id)
                        if sos_channel:
                            view = PoliciaSosView()
                            await sos_channel.send(
                                f"@here 🚨 **SOS en {map_name}** 🚨\n📝 Log original:\n> {texto_original}",
                                view=view,
                            )
                    except Exception as e:
                        guild_log.error(f"[SOS] Error enviando alerta de policia: {e}")

                # Procesamiento de K/D/A Tracker y Sarcasmos
                try:
                    # Normalización de texto para regex
                    t_clean = (
                        texto_original.replace(":knife:", "🔪")
                        .replace("was 🔪 by", "fue 🔪 por")
                        .replace(
                            "was 🔪",
                            "ha muerto 🔪",  # Fallback para muertes sin asesino
                        )
                    )

                    # 1. Caso: Muerte confirmada con asesino
                    # Patrón: Tribemember [Victima] - Lvl [X] fue 🔪 por [Asesino] - Lvl [Y]
                    player_death_match = re.search(
                        r"Tribemember (.*?) - Lvl.*?fue 🔪 por (.*?) - Lvl",
                        t_clean,
                        re.IGNORECASE,
                    )

                    # 2. Caso: Muerte genérica (dino, comida, etc)
                    # Patrón: Tribemember [Victima] - Lvl [X] ha muerto 🔪
                    generic_death_match = re.search(
                        r"Tribemember (.*?) - Lvl.*?(?:ha muerto 🔪|was 🔪)",
                        t_clean,
                        re.IGNORECASE,
                    )

                    if player_death_match or generic_death_match:
                        victima_char = ""
                        asesino_char = None
                        
                        if player_death_match:
                            victima_char = player_death_match.group(1).strip()
                            asesino_char = player_death_match.group(2).strip()
                        else:
                            victima_char = generic_death_match.group(1).strip()

                        async with aiosqlite.connect(self.bot.db_name) as db:
                            # 1. Obtener miembros de la tribu propia para identificación automática
                            c_own = await db.execute("SELECT members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?", (guild_id,))
                            own_row = await c_own.fetchone()
                            own_members = []
                            if own_row:
                                try:
                                    own_members = json.loads(own_row[0])
                                except Exception:
                                    pass

                            # 2. Mapeo de víctima (personaje in-game -> jugador real)
                            c1 = await db.execute(
                                "SELECT player_name FROM tribe_characters WHERE LOWER(character_name) = LOWER(?) AND guild_id = ?",
                                (victima_char, guild_id),
                            )
                            victima_res = await c1.fetchone()
                            victima_player = victima_res[0] if victima_res else None
                            
                            # Fallback: si no hay vínculo, mirar si el nombre coincide con un miembro de la tribu propia
                            if not victima_player:
                                for m in own_members:
                                    if m.lower() == victima_char.lower():
                                        victima_player = m
                                        break

                            # 3. Mapeo de asesino
                            asesino_player = None
                            if asesino_char:
                                c2 = await db.execute(
                                    "SELECT player_name FROM tribe_characters WHERE LOWER(character_name) = LOWER(?) AND guild_id = ?",
                                    (asesino_char, guild_id),
                                )
                                asesino_res = await c2.fetchone()
                                asesino_player = asesino_res[0] if asesino_res else None
                                
                                # Fallback para el asesino
                                if not asesino_player:
                                    for m in own_members:
                                        if m.lower() == asesino_char.lower():
                                            asesino_player = m
                                            break

                            # Solo procesamos muertes de miembros registrados
                            if victima_player:
                                if victima_player and asesino_player:
                                    guild_log.info(
                                        f"[KDA] Fuego amigo: {asesino_player} mató a {victima_player}. No suma KDA."
                                    )
                                else:
                                    # Incrementar muertes en KDA
                                    await db.execute(
                                        "INSERT INTO tribe_kda (guild_id, player_name, deaths) VALUES (?, ?, 1) ON CONFLICT(guild_id, player_name) DO UPDATE SET deaths = deaths + 1",
                                        (guild_id, victima_player),
                                    )
                                # Registrar muerte individual con timestamp para estadísticas pico
                                await db.execute(
                                    "INSERT INTO tribe_death_log (guild_id, player_name) VALUES (?, ?)",
                                    (guild_id, victima_player),
                                )
                                
                                # Obtener el total de muertes actualizado para el sarcasmo
                                cursor = await db.execute(
                                    "SELECT deaths FROM tribe_kda WHERE guild_id = ? AND player_name = ?",
                                    (guild_id, victima_player),
                                )
                                d_row = await cursor.fetchone()
                                num_muertes = d_row[0] if d_row else 1
                                
                                # Respuestas sarcásticas variadas e Hitos
                                hitos = {
                                    1: ("¡Bienvenido a ARK! Tu primera muerte oficial de muchas... 🎉", "https://tenor.com/view/welcome-to-jurassic-park-gif-11623192"),
                                    10: ("Doble dígito de muertes... Ya eres un veterano en besar el suelo. 🥉", "https://tenor.com/view/facepalm-picard-star-trek-disappointment-gif-14639209"),
                                    50: ("¡Medio centenar de muertes! 🥈 Estás a medias de convertirte en el mayor donante de loot del servidor.", "https://tenor.com/view/sarcastic-clapping-golf-clap-cheers-well-done-jon-stewart-gif-16167909"),
                                    69: ("69 muertes... Nice. Pero sigues estando muerto. 😏", "https://tenor.com/view/nice-south-park-gif-9226462"),
                                    100: ("¡100 MUERTES! 🥇 Oficialmente eres el jugador más manco de la tribu. Eres leyenda.", "https://tenor.com/view/nuclear-explosion-boom-blast-atomic-bomb-gif-16056637"),
                                    300: ("¡ESTO ES ESPARTA! Y tú eres el mensajero que acaban de tirar al pozo. 300 muertes.", "https://tenor.com/view/sparta-kick-hole-fall-leonidas-gif-3420829"),
                                    420: ("420 muertes... 🌿 Demasiado humo en esa base, ¡deja de fumar flor rara!", "https://tenor.com/view/snoop-dogg-smoke-smoke-weed-420-gif-14352528"),
                                    666: ("666 muertes... 😈 Has invocado al Demonio de la Inutilidad. Vas directo al infierno.", "https://tenor.com/view/hell-elmo-fire-flames-elmo-fire-gif-17631853"),
                                    777: ("¡VEGETTA777! ⛏️ Muy bonito, pero te acaba de farmear un dodo por la espalda.", "https://tenor.com/view/vegetta777-minecraft-saludo-gif-14546416"),
                                    1000: ("1000 MUERTES. 🏆 Hemos contactado con Wildcard. Te vamos a borrar el juego de Steam para que dejes de sufrir.", "https://tenor.com/view/mind-blown-explosion-boom-explode-gif-12051642")
                                }
                                
                                final_msg = ""
                                if num_muertes in hitos:
                                    texto, gif = hitos[num_muertes]
                                    final_msg = f"{texto}\n{gif}"
                                elif num_muertes > 0 and num_muertes % 100 == 0:
                                    final_msg = f"Sigues sumando de 100 en 100... ¿no te cansas? Ya van **{num_muertes}** muertes. 💀\nhttps://tenor.com/view/confused-john-travolta-pulp-fiction-where-gif-14436531"
                                else:
                                    sarcasmos_base = [
                                        f"Estás pendejo... ya te moriste **{num_muertes}** veces...",
                                        f"¡Felicidades! Has desbloqueado el logro: *Morir por {num_muertes}ª vez*. 🏆",
                                        f"¿Otra vez? A este ritmo te van a cobrar alquiler en el respawn. (Muertes: **{num_muertes}**)",
                                        f"Tranquilo, la **{num_muertes}ª** es la vencida... o no. 🤡",
                                        f"Eres como un dodo, pero con menos instinto de supervivencia. (Total: **{num_muertes}**)",
                                        f"¡Míralo! Si es que no se le puede dejar solo... Muertes: **{num_muertes}** 🤦‍♂️",
                                        f"¿Has probado lo de no morir? Dicen que funciona bastante bien. (Contador: **{num_muertes}**)",
                                        f"A este paso vas a amansar a los dinos salvajes a base de darles de comer tu propio cadáver. (**{num_muertes}** muertes)",
                                        f"En el menú del servidor hoy toca: Carpaccio de {victima_player}. Ya llevas **{num_muertes}** muertes.",
                                        f"Ni un mosco en verano muere tantas veces... Contador sube a **{num_muertes}**.",
                                        f"Vete preparando saco, porque la cama ya la has derretido del uso. (Total: **{num_muertes}**)",
                                        f"Tus padres no te criaron para feedear de esta manera tan vergonzosa. (**{num_muertes}** ☠️)",
                                        f"Si la tribu dependiera de ti, seguiríamos con herramientas de piedra. (**{num_muertes}** veces)",
                                        f"Muertes totales: **{num_muertes}**. El servidor está empezando a sentir lástima por ti.",
                                        f"Bob the Builder construía mejor y moría menos que tú. (**{num_muertes}** defunciones)",
                                        f"Tómate un respiro, ve a beber agua, porque madre mía la que estás liando... (**{num_muertes}**)",
                                        f"Cuidado de no tropezar con una piedra y resbalar, que igual mueres por **{num_muertes}ª** vez consecutiva.",
                                        f"Oye, que en este servidor no dan premio por ser el que más veces mira la pantalla de muerte. (**{num_muertes}**)",
                                        f"Hasta un Triceratops despistado vive más tiempo que tú. Y eso que extinguieron hace milenios. (**{num_muertes}** bajas)",
                                        f"¿Quién dejó la puerta abierta? Ah, no, que fuiste tú intentando huir... otra vez. (**{num_muertes}** muertes)"
                                    ]
                                    final_msg = random.choice(sarcasmos_base)
                                
                                sent_msg = await message.reply(final_msg)
                                
                                try:
                                    emojis_muerte = ["💀", "🤡", "🪦", "🥚", "🍗", "🧻", "🗑️"]
                                    await sent_msg.add_reaction(random.choice(emojis_muerte))
                                except Exception:
                                    pass
                                guild_log.info(
                                    f"[Sarcasmo] Muerte detectada: {victima_player} (#{num_muertes})"
                                )
                                # Se han eliminado las Kills activas debido a que solo se usan muertes.
                                await db.commit()

                            # Actualización global de dashboards si hubo algún cambio
                            if victima_player or (asesino_player and not victima_player):
                                try:
                                    from cogs.warfare import update_kda_dashboards
                                    await update_kda_dashboards(self.bot, guild_id)
                                except Exception as e:
                                    self.logger.error(f"[KDA] Error recargando dashboards: {e}")

                except Exception as e:
                    self.logger.error(f"[KDA] Error parseando kill log: {e}")

        # Importante: Como es un listener en un Cog, no debe llamar a await self.bot.process_commands(message)
        # ya que la propia clase Bot lo maneja.

async def setup(bot):
    await bot.add_cog(LogProcessor(bot))
