"""Long /info and /help guides in English.

Parallel translation of ``guides_es.INFO_TEXTS``. Keys must match 1:1 with the
Spanish dict so /info and /help can pick either version by language.

Command names (``/sos``, ``/tribu propia`` ...) are kept verbatim because the
slash commands themselves are not renamed per language.
"""

INFO_TEXTS_EN = {
    "sos": """# :rotating_light: HOME-DELIVERY AMBULANCES & SOS

This channel is for **REAL EMERGENCIES**. Use it responsibly.

### :loudspeaker: SOS Alert System
- **/sos**: Fires a mass alert mentioning the tribe role.
  - **Quick use:** `/sos` (sends a generic "HELP NOW" alert).
  - **Detailed use:** `/sos tipo:Raideo mapa:MainBase atacantes:10 defensores:2 notas:"In the north cave"`.
  - **Available types:** :red_circle: Raid · :orange_circle: Enemy FOB · :yellow_circle: Soaking · and more.
- Every posted SOS carries a **✅ Solved** button that anyone can press to delete the message once the emergency is over.

### :man_police_officer: Silent Tip-off (@policia)
Passive alarm system. If someone in-game kills a dino whose name contains `@policia`, the **Log Processor** detects it in the logs channel and automatically posts a warning here. Useful to detect silent infiltrators without the attacker knowing you caught them.

### :bell: Relation to Intruder Alarms
The **🔔 Intruder Alarms** module (`/info modulo:🔔 Alarmas`) complements this by warning you when a non-tribe player enters a map you are watching.

> :warning: Abusing the `/sos` command for jokes is uncool. Use it only if we're truly under attack.""",
    "todo_list": """# :pencil: TO-DO List

Add pending tasks, claim the ones you'll do yourself, and delete them when done.

### :white_check_mark: Task Management
- **/todo add**: Adds a new task to the "Pending" list.
  - *Usage:* `/todo add tarea:"Farm 50k metal on Aberration"`
- **/todo panel**: Generates/refreshes the interactive task panel (auto-updating).

### :mouse_three_button: Panel Buttons
1. **Add Task**: Opens a form to write a new task.
2. **Claim Task**: Assigns a task to you and marks it "In Progress" :hammer:.
   - *It's a toggle*: pressing "Claim" again on the same task **removes** you from the list.
   - A task can have **several assignees** at once (they stack).
3. **Delete Task**: Wipes a task off the face of the earth once finished.
4. :arrow_backward: and :arrow_forward: **Pagination**: 10 tasks per page, infinite pages, survives restarts.

> :bell: Check this channel before asking "what needs doing?".""",
    "lineas": """# :dna: Breeding Lines

Here we register and track our tribe's lines (Top Stats).

### :sauropod: Breeding Commands
- **/linea add**: Registers a new dino or updates a stat if yours is higher.
  - *Usage:* `/linea add dino:Rex estadistica:HP puntos:50`
- **/linea mod**: Modifies a specific stat (in case of a typo or a fresh mutation).
- **/linea ver**: Private lookup of all stats for a species (hidden message).
- **/linea panel**: Refreshes the main Dashboard with all stats and live buttons.
- **/linea log**: Shows the last 20 mutations registered on the server.

### :bar_chart: Available Stats
HP · Stamina · Weight · Melee · Oxygen · Food · Speed · Mutations (pure counter).

### :mouse_three_button: Dashboard Buttons
1. :arrow_backward: :arrow_forward: **Pagination**: 10 species per page, persistent across restarts.
2. **New Mutation**: Adds +2 to a dino stat and logs it in the mutation log automatically.
3. **Alarms**: Schedules imprint/growth timers. Options: **1.5h · 2.5h · 4h · 10h**. It pings you in the channel when it expires.
4. **View Mut. Logs**: Same as the `/linea log` command but a click away.
5. **Individual Selector**: Bottom dropdown to isolate a specific dino and see its detailed sheet privately.""",
    "blacklist": """# :skull_crossbones: Blacklist

"Kill on Sight" (KOS) players. If they're here, they're confirmed enemies; the more info, the better.

### :no_entry_sign: Blacklist System
- **/blacklist**: Generates and pins the interactive Blacklist Dashboard (auto-updating).
- **/bl_editar**: Direct shortcut to the edit modal without going through the panel (handy for quick changes).

### :mouse_three_button: Panel Buttons
1. **Add**: Quick form (Tribe, Map, Notes) to create an enemy.
2. **Edit**: Change notes/map/name, or **toggle between Enemy and Neutral**.
3. **Delete**: Removes an entry by ID.
4. :arrow_backward: :arrow_forward: **Pagination**: 10 entries per page.

### :red_circle: Enemies vs :white_circle: Neutrals
- :red_circle: **ENEMIES** (`is_enemy=1`): players to neutralize no matter what.
- :white_circle: **RECORDS / NEUTRALS** (`is_enemy=0`): players auto-detected by K4Ultra who haven't done anything to us yet (tracking and monitoring).

### :gear: Automatic Enrichment
Every minute, **K4Ultra** completes each entry with:
- **Total hours** observed on the cluster.
- **Last seen** + the map they were on.
- **Suspected tribe** (when relationship data exists).
You don't have to fill anything by hand — the bot completes it in the background.""",
    "scouting": """# :satellite_orbital: Scouting

Enemy base reports. Information is power.

### :telescope: Recon Commands
- **/scout add**: Registers an enemy base with full details (accepts an image as a link).
  - *Fields:* `tribu`, `mapa`, `coords`, `amenaza` (1-5 :star:, validated), `imagen`, `notas`.
- **/scout imagen**: Attaches an image from your PC to an existing scout.
  - *Usage:* `/scout imagen id:12 imagen:[attach file]`.
- **/scout lista**: Opens the Dashboard panel.
  - *No arguments:* paginated **GLOBAL** list of every map.
  - *With `mapa:` argument:* private filter showing only that map's bases.
- **/scout borrar**: Removes an obsolete report by ID.

### :mouse_three_button: Panel Buttons & Menu
- **Add Scout**: form without image (add it later with `/scout imagen`).
- **Edit / Delete Scout**: by ID.
- :arrow_backward: :arrow_forward: **Pagination** across maps.
- :pushpin: **Bottom selector**: click a listed scout and see its **full sheet with image** in a private message.

> :bulb: Valid threat levels: from **1 (low)** to **5 (extreme)**. Any other value is rejected.""",
    "status": """# :green_circle: Server Status

Monitors in real time whether servers are online, who's connected and their ping.

### :computer: Commands
- **/status mapa**: One-off query of a server (autocompletes with your maps).
- **/status cluster**: Summary view of the **whole cluster** in a single embed.
- **/status fijar mapa:Gen2**: Pins a message that auto-updates every 2 min indefinitely.

### :arrows_counterclockwise: Auto-Update & Colors
Persistent panels refresh automatically and change their look based on status:
- :green_circle: **Green** — server online with players inside (it lists them).
- :yellow_circle: **Yellow** — server online but empty.
- :red_circle: **Red** — server down (timeout / no A2S response).

### :stopwatch: Technical Detail
A2S queries are centralized with a shared 90s cache, letting **Status**, **K4Ultra** and **Alarms** reuse the same poll without hammering the servers.

### :bell: Intruder Alarms (summary)
- **/alarma mapa:Fjordur estado:on** enables watching a map; **off** disables it.
- **/alarmas** opens the quick panel with all your configurable alarms.
- The bot pings you when a player who is NOT in your own tribe nor a registered character enters the map. Each alert carries a **✅ Done** button to silence it.

> :bulb: More detail in `/info modulo:🔔 Alarmas de Intrusos`.""",
    "k4ultra": """# :eye: Intelligence Tracker (K4Ultra)

K4Ultra passively monitors the cluster to compute behavior, sessions and enemy alliances from the A2S protocol (without touching Battlemetrics).

### :satellite: View Modes
- **/k4ultra**: Brings up the main panel (Radar mode by default).
  - **Radar / Ranking**: online players + top played hours (paginated :arrow_backward: :arrow_forward:).
  - **Tribes / Relationships**: predictive alliance graph. Each pair of players accrues points for minutes shared on the same map, synchronized logins/logouts and simultaneous transfers. It decays **5% per day** if they stop coinciding.

### :crown: Identifying your own tribe
- **/tribu propia crear nombre:"MyTribe" jugadores:"a, b, c"** — marks your base.
- **/tribu propia modificar opcion:... valor:...** — add/remove members or rename.
- **/tribu propia borrar seguro:True** — clears the record.
- **/tribu fijar / /tribu desfijar** — to mark **other** known tribes (confirmed enemies, allies, etc.) so they appear labeled in Tribes mode.

### :busts_in_silhouette: Identity Management
Essential so the ranking and blacklist don't fill up with duplicates:
- **/tribu miembro usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registers a full member in a single call.
- **/tribu fusionar origen:OldName destino:NewName** — everything the bot recorded under the old name (hours, maps, sessions, relationships, blacklist) is reassigned to the new one permanently.
- **/tribu separar origen:... destino:...** — splits the current session of a profile the bot grouped by mistake.
- **/tribu limpiar** — [Admin] mass cleanup: merges every `name_1`/`_2` with its base.

### :mouse_three_button: Panel Buttons
- **➕ Add Relationship / ➖ Remove Relationship**: declare/undeclare manual alliances (they don't decay).
- **✏️ Rename Tribe**: assigns a persistent alias to a detected tribe (e.g. "Cluster A" → "The Alphas").
- **Player Selector**: click a player → full dossier (unified profile with KDA + hours + maps) privately.""",
    "ranking": """# :skull_crossbones: THE HALL OF INFAMY (Noob-o-meter)

The bot uses a **Log Processor** that listens 24/7 to the server Logs channel and parses every death.

### :chart_with_downwards_trend: How it works
- **Automatic detection:** each `fue 🔪` or `was :knife:` in the logs increments the character's death counter. Kills are ignored on purpose (we only count deaths).
- **Anti-friendly-fire:** if the killer is also a registered member of your tribe (via `/tribu miembro`), the death does NOT count — it only stays in the log with a "friendly fire" notice.
- **Sarcasm:** the bot replies to each death with a random phrase + random emoji (💀🤡🪦🥚🍗🧻🗑️).
- **Special milestones:** deaths numbered **1, 10, 50, 69, 100, 300, 420, 666, 777, 1000** and every multiple of 100 trigger messages with a dedicated GIF. Keep racking them up.

### :busts_in_silhouette: Required Setup
For the system to attribute deaths:
- **/tribu miembro usuario:@x personaje:Bob steam:"BobSteam" apodo:"Bobby"** — registers a member.
- **/ranking** — Death Counter Dashboard sorted by casualties.

### :sunrise: Vote Reminders
The **Daily Points** module (`/info modulo:🌅 Puntos Diarios`) is optional and complementary — it DMs you every day to redeem the cluster votes.""",
    "alarmas": """# :bell: Per-Map Intruder Alarms

Passive defense system: the bot watches the maps you choose and **mentions you in the channel** where you enabled the alarm when a player enters who is NOT in your own tribe, an allied tribe, nor registered as a known character.

### :gear: Commands
- **/alarma mapa:Fjordur estado:on** — Enables watching a map.
- **/alarma mapa:Fjordur estado:off** — Disables it.
- **/alarmas** — Opens the **interactive panel** with all the cluster's configurable alarms (handier than the standalone command).
- **/tribu aliada crear / modificar / borrar / lista** *(admin)* — Registers allied tribes so their players don't trigger alarms.

### :brain: How it decides someone is an intruder
Every minute the bot reads the Status cache (no extra traffic) and compares against the map's last snapshot. For each NEW player:
1. If they're in your own tribe (`/tribu propia`) → ignore.
2. If they're in an allied tribe (`/tribu aliada`) → ignore.
3. If they're registered as a known character (`/tribu miembro`) → ignore.
4. Otherwise → :rotating_light: **alarm**: the bot mentions you in the channel where you enabled the alarm with the list of intruders.

### :pushpin: Detail
- Alarms are **per user** and per map: each member can have their own list.
- Multi-map: you can watch several maps at once at no extra cost.
- The alarm message includes a **✅ Silence** button to dismiss it.
- The channel where the alert is sent is the same one where you enabled the alarm (`/alarma` or the `/alarmas` panel).""",
    "puntos_diarios": """# :sunrise: Daily Vote Points

A personal DM reminder to redeem your daily points by voting your cluster on the public rankings.

### :gear: User Commands
- **/puntos_diarios estado:on hora:8 zona:España** — Enables the daily reminder at the given hour.
  - Supported zones: **Spain (es)** and **Mexico (mx)**.
  - Valid hour: **0-23** (default 8).
- **/puntos_diarios estado:off** — Cancels the reminders.

### :man_office_worker: Admin Commands
- **/config_puntos estado:on|off vote_links:"Map1|URL1,Map2|URL2"** — Enables/disables the system for the whole server and customizes the vote URLs.
- **/config_puntos** (no args) — Shows the current status and configured URLs.

### :white_check_mark: How It Works
1. At the chosen hour the bot DMs you the cluster vote links.
2. The DM includes a **✅ Done** button that marks the day as done (visual only, it doesn't touch your ARK account).
3. The next day it warns you again automatically.

> :bulb: If the admin disables the system for the whole server with `/config_puntos estado:off`, it stops sending reminders even if you have an active subscription.""",
    "eventos": """# :calendar_spiral: LFG Event Management

Plan raids, defenses, bosses or coordinated farming with group voting.

### :calendar: Single Command
- **/evento titulo:"Alpha Dragon" descripcion:"Bring 10 rexes" opcion_1:"Fri 22:00" opcion_2:"Sat 18:00" opcion_3:... opcion_4:...**
  - Minimum **2 valid options**; opcion_3 and opcion_4 are optional.

### :ballot_box: Voting
The bot creates an embed with one button per option plus an extra **❌ Can't attend** button.
- Each user can vote **a single option** (voting another replaces the previous one automatically).
- The embed refreshes with live counts and progress bars.
- Voters' names are listed under each option.

### :pushpin: Persistence
Events are saved to the database and the buttons keep working even if you restart the bot.""",
    "admin": """# :shield: Configuration and Administration

Commands reserved for server administrators or the role/user marked as owner in `guild_config`.

### :rocket: Initial Setup
- **/inicio_ark** — Wizard that links the bot to the server:
  - Channels: SOS, Logs, Uploads.
  - Admin and owner roles.
  - Cluster: `battlemetrics_urls` with format `Map1|IP:PORT,Map2|IP:PORT2`.
  - Automatically creates the dashboard threads/channels.
- **/config** — Same form as `/inicio_ark` but to **edit** the existing configuration without recreating the dashboards. With no arguments, shows the current status.
- **/idioma** — Changes the bot's language on this server: Spanish, English (dashboards only) or English (everything).
- **/bind_k4ultra message_id:... channel_id:...** — Associates an existing message with the K4Ultra dashboard (handy after reinstalling the bot).

### :recycle: Maintenance
- **/clear_updates** — Deletes only the message/dashboard records (doesn't touch data). Useful when dashboards get out of sync.
- **/wipe_db** — :radioactive: Deletes **ALL** server data (scouts, blacklist, to-do list, lines, etc.). Destructive action — asks for confirmation. Owner only.

### :memo: Diagnostics
- **/log** — Shows the last commands run in the bot's current session.
- **/help** — Full text guide of the bot (summary of every module).
- **/info modulo:...** — This same contextual help per module.""",
    "backup": """# :floppy_disk: Database Backups

The bot automatically keeps a daily copy of `tribe_data.db` to recover state after incidents.

### :alarm_clock: Automatic Backup
- Runs **every day at 04:00 UTC**.
- Files are saved to `backups/tribe_data_YYYY-MM-DD.db`.
- **Retention: 7 days**: backups older than a week are deleted automatically.

### :gear: Manual Backup
- **/db_backup** — Generates a backup **instantly**. Useful before destructive changes (`/wipe_db`, version migration, etc.).
  - Returns the file name and size in KB.
  - Also applies the 7-day retention.

### :information_source: Recovery
If you need to restore a backup, copy the desired `.db` over `tribe_data.db` with the bot **stopped** (`systemctl stop arkbot`). On startup, the schema is validated and migrated automatically via `db/schema.py`.

> :warning: Backups are **local to the bot's server**. If you lose the whole server, you lose the DB. Consider keeping an external copy every so often.""",
}
