import json
import logging
import random
import re
import time

import discord
from discord.ext import commands

from cogs.server_status import get_guild_servers
from main import PoliciaSosView, get_guild_logger
from utils import bus
from utils.i18n import resolve_lang, t
from utils.parsing import parse_destruction_line

logger = logging.getLogger("ArkTribeBot")

# Cooldown (segundos) entre alertas por la MISMA estructura destruida. Una raid
# tira decenas de líneas "was destroyed!" seguidas — sin esto, el canal SOS se
# llenaría de @here.
DESTRUCTION_ALERT_COOLDOWN_S = 600


class LogProcessor(commands.Cog, name="LogProcessor"):
    """
    Cog encargado de procesar los mensajes en los canales de log.
    Saca la lógica fuera de main.py para mantener el código modular.
    Incluye el KDA Tracker, SOS Policía/Log, alertas de destrucción y sarcasmos.
    """

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("ArkTribeBot.LogProcessor")
        # (guild_id, mapa, estructura) → epoch de la última alerta enviada.
        self._destruction_alerted: dict[tuple, float] = {}

    async def _resolve_map_name(self, guild_id: int, abbrev: str | None) -> str:
        """Convierte el tag de mapa del log ("Abr") en el nombre completo del
        servidor configurado ("Aberration"), comparando por prefijo contra los
        mapas del cluster. Si no hay match, devuelve el tag tal cual."""
        if not abbrev:
            return "?"
        try:
            servers = await get_guild_servers(self.bot, guild_id)
        except Exception:
            servers = {}
        ab = abbrev.lower()
        for name in servers:
            if name.lower().startswith(ab):
                return name
            # Tags tipo "Cen" para "The Center": probar prefijo por palabra.
            if any(word.startswith(ab) for word in name.lower().split()):
                return name
        return abbrev

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar mensajes del propio bot
        if message.author.id == self.bot.user.id:
            return

        # Ignorar DMs por completo — el procesador solo opera en canales de guild.
        if message.guild is None:
            return

        guild_id = message.guild.id

        # Verificación del canal puente de logs configurado para este servidor
        is_log_channel = False
        sos_channel_id = None
        guild_log = logging.getLogger("ArkTribeBot.Global")  # Fallback

        if guild_id:
            guild_log = get_guild_logger(guild_id)
            config = await self.bot.db.fetchone(
                "SELECT log_channel_id, sos_channel_id FROM guild_config WHERE guild_id = ?",
                (guild_id,),
            )
            if config:
                log_channel_id = config["log_channel_id"]
                sos_channel_id = config["sos_channel_id"]
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

            # Extraer contenido original formateado (común a todas las detecciones)
            texto_original = message.content
            if not texto_original and message.embeds and message.embeds[0].description:
                texto_original = message.embeds[0].description

            # Lectura case-insensitive
            # Detección de tripwires (@policia / @log) y emoji 🔪
            contains_tripwire = (
                "@policia" in content_lower or "@log" in content_lower or "<@&" in content_lower
            )
            contains_knife = (
                "was :knife:" in content_lower
                or "fue :knife:" in content_lower
                or "was 🔪" in content_lower
                or "fue 🔪" in content_lower
            )

            # --- Detección de ESTRUCTURAS DESTRUIDAS ---
            # Ej.: "(Abr) Day 1, 09:47: Your 'GLOWTAIL WALL (SS Storage Box) (Unlocked) ' was destroyed!"
            # → alerta de intruso en GLOWTAIL WALL de Aberration.
            destruction = parse_destruction_line(texto_original)
            if destruction and sos_channel_id:
                map_abbrev, structure = destruction
                map_name = await self._resolve_map_name(guild_id, map_abbrev)

                # Cooldown por estructura: una raid genera decenas de líneas seguidas.
                key = (guild_id, map_name, structure.lower())
                now_s = time.time()
                if now_s - self._destruction_alerted.get(key, 0) >= DESTRUCTION_ALERT_COOLDOWN_S:
                    self._destruction_alerted[key] = now_s
                    try:
                        sos_channel = self.bot.get_channel(
                            sos_channel_id
                        ) or await self.bot.fetch_channel(sos_channel_id)
                        if sos_channel:
                            lang = await resolve_lang(self.bot, guild_id, "command")
                            await sos_channel.send(
                                t(
                                    "log.destroyed.alert",
                                    lang,
                                    structure=structure,
                                    map=map_name,
                                    raw=texto_original.strip(),
                                ),
                                view=PoliciaSosView(),
                            )
                            guild_log.info(
                                f"[Destrucción] Alerta: {structure} ({map_name}) destruida."
                            )
                    except Exception as e:
                        guild_log.error(f"[Destrucción] Error enviando alerta: {e}")

            if contains_knife:
                # Procesamiento de SOS por tripwire (@policia / @log en el nombre del dino)
                if contains_tripwire and sos_channel_id:
                    map_match = re.search(r"\((.*?)\)", texto_original)
                    map_name = map_match.group(1) if map_match else "Desconocido"
                    map_name = await self._resolve_map_name(guild_id, map_name)
                    try:
                        sos_channel = self.bot.get_channel(sos_channel_id) or await self.bot.fetch_channel(
                            sos_channel_id
                        )
                        if sos_channel:
                            view = PoliciaSosView()
                            lang = await resolve_lang(self.bot, guild_id, "command")
                            await sos_channel.send(
                                t("log.sos.alert", lang, map=map_name, raw=texto_original),
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

                        db = self.bot.db
                        # 1. Obtener miembros de la tribu propia para identificación automática
                        own_row = await db.fetchone(
                            "SELECT members_json FROM k4ultra_fixed_tribes WHERE is_own = 1 AND guild_id = ?",
                            (guild_id,),
                        )
                        own_members = []
                        if own_row:
                            try:
                                own_members = json.loads(own_row["members_json"])
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"[LogProcessor] members_json inválido en tribu propia: {e}")

                        # 2. Mapeo de víctima (personaje in-game -> jugador real)
                        victima_res = await db.fetchone(
                            "SELECT player_name FROM tribe_characters WHERE LOWER(character_name) = LOWER(?) AND guild_id = ?",
                            (victima_char, guild_id),
                        )
                        victima_player = victima_res["player_name"] if victima_res else None

                        # Fallback: si no hay vínculo, mirar si el nombre coincide con un miembro de la tribu propia
                        if not victima_player:
                            for m in own_members:
                                if m.lower() == victima_char.lower():
                                    victima_player = m
                                    break

                        # 3. Mapeo de asesino
                        asesino_player = None
                        if asesino_char:
                            asesino_res = await db.fetchone(
                                "SELECT player_name FROM tribe_characters WHERE LOWER(character_name) = LOWER(?) AND guild_id = ?",
                                (asesino_char, guild_id),
                            )
                            asesino_player = asesino_res["player_name"] if asesino_res else None

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
                            d_row = await db.fetchone(
                                "SELECT deaths FROM tribe_kda WHERE guild_id = ? AND player_name = ?",
                                (guild_id, victima_player),
                            )
                            num_muertes = d_row["deaths"] if d_row else 1

                            # Idioma del servidor para los mensajes públicos de muerte
                            # (scope command: solo inglés si el modo es en_total).
                            lang = await resolve_lang(self.bot, guild_id, "command")

                            # GIF por hito (el texto viene del catálogo i18n).
                            hito_gifs = {
                                1: "https://tenor.com/view/welcome-to-jurassic-park-gif-11623192",
                                10: "https://tenor.com/view/facepalm-picard-star-trek-disappointment-gif-14639209",
                                50: "https://tenor.com/view/sarcastic-clapping-golf-clap-cheers-well-done-jon-stewart-gif-16167909",
                                69: "https://tenor.com/view/nice-south-park-gif-9226462",
                                100: "https://tenor.com/view/nuclear-explosion-boom-blast-atomic-bomb-gif-16056637",
                                300: "https://tenor.com/view/sparta-kick-hole-fall-leonidas-gif-3420829",
                                420: "https://tenor.com/view/snoop-dogg-smoke-smoke-weed-420-gif-14352528",
                                666: "https://tenor.com/view/hell-elmo-fire-flames-elmo-fire-gif-17631853",
                                777: "https://tenor.com/view/vegetta777-minecraft-saludo-gif-14546416",
                                1000: "https://tenor.com/view/mind-blown-explosion-boom-explode-gif-12051642",
                            }

                            final_msg = ""
                            if num_muertes in hito_gifs:
                                texto = t(f"death.milestone.{num_muertes}", lang)
                                final_msg = f"{texto}\n{hito_gifs[num_muertes]}"
                            elif num_muertes > 0 and num_muertes % 100 == 0:
                                final_msg = (
                                    t("death.milestone.century", lang, n=num_muertes)
                                    + "\nhttps://tenor.com/view/confused-john-travolta-pulp-fiction-where-gif-14436531"
                                )
                            else:
                                phrases = t("death.sarcasm", lang).split("\n")
                                final_msg = random.choice(phrases).format(
                                    n=num_muertes, victim=victima_player
                                )

                            sent_msg = await message.reply(final_msg)

                            try:
                                emojis_muerte = ["💀", "🤡", "🪦", "🥚", "🍗", "🧻", "🗑️"]
                                await sent_msg.add_reaction(random.choice(emojis_muerte))
                            except (discord.Forbidden, discord.HTTPException) as e:
                                logger.debug(f"[LogProcessor] add_reaction falló: {e}")
                            guild_log.info(f"[Sarcasmo] Muerte detectada: {victima_player} (#{num_muertes})")
                            # Se han eliminado las Kills activas debido a que solo se usan muertes.
                            await db.commit()

                        # Actualización global de dashboards si hubo algún cambio
                        if victima_player or (asesino_player and not victima_player):
                            # Aviso al cog Warfare vía bus de eventos.
                            self.bot.dispatch(bus.KDA_UPDATED, guild_id)

                except Exception as e:
                    self.logger.error(f"[KDA] Error parseando kill log: {e}")

        # Importante: Como es un listener en un Cog, no debe llamar a await self.bot.process_commands(message)
        # ya que la propia clase Bot lo maneja.


async def setup(bot):
    await bot.add_cog(LogProcessor(bot))
