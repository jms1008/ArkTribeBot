"""Esquema centralizado de la base de datos de ArkTribeBot.

Toda creación de tablas, migraciones e índices vive aquí.
Los cogs NUNCA deben crear tablas — si una tabla falta, añádela en TABLES.
"""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger("ArkTribeBot")


# --- DDL: CREATE TABLE IF NOT EXISTS ---
TABLES: list[str] = [
    # Configuración por servidor
    """
    CREATE TABLE IF NOT EXISTS guild_config (
        guild_id INTEGER PRIMARY KEY,
        sos_channel_id INTEGER,
        log_channel_id INTEGER,
        upload_channel_id INTEGER,
        update_interval INTEGER DEFAULT 2,
        admin_role_id INTEGER,
        bot_owner_id INTEGER,
        battlemetrics_urls TEXT,
        daily_points_enabled INTEGER DEFAULT 1,
        vote_urls TEXT
    )
    """,
    # Scouting
    """
    CREATE TABLE IF NOT EXISTS scouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        tribu_enemiga TEXT,
        mapa TEXT,
        coordenadas TEXT,
        nivel_amenaza INTEGER,
        url_imagen TEXT,
        notas TEXT
    )
    """,
    # To-Do
    """
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        tarea TEXT,
        asignado_a INTEGER,
        estado TEXT DEFAULT 'Pendiente'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS todo_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scout_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER,
        map_filter TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS breeding_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER
    )
    """,
    # Breeding
    """
    CREATE TABLE IF NOT EXISTS dinos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        especie TEXT,
        sexo TEXT,
        hp INTEGER,
        melee INTEGER,
        stam INTEGER,
        weight INTEGER,
        oxy INTEGER,
        food INTEGER,
        speed INTEGER,
        mutaciones INTEGER,
        estado TEXT
    )
    """,
    # Blacklist
    """
    CREATE TABLE IF NOT EXISTS blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player TEXT,
        tribe TEXT,
        map TEXT,
        notes TEXT,
        created_at TEXT,
        last_seen TEXT,
        total_hours REAL DEFAULT 0,
        is_enemy INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS blacklist_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER
    )
    """,
    # Server status
    """
    CREATE TABLE IF NOT EXISTS status_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER,
        map_name TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS status_online_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS server_status_cache (
        guild_id INTEGER NOT NULL,
        server_name TEXT NOT NULL,
        ip_port TEXT,
        ping INTEGER,
        player_count INTEGER,
        player_names TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(guild_id, server_name)
    )
    """,
    # Daily points
    """
    CREATE TABLE IF NOT EXISTS daily_points_users (
        user_id INTEGER,
        guild_id INTEGER NOT NULL,
        alert_hour INTEGER DEFAULT 8,
        timezone TEXT DEFAULT 'es',
        last_sent_date TEXT,
        PRIMARY KEY (guild_id, user_id)
    )
    """,
    # K4Ultra
    """
    CREATE TABLE IF NOT EXISTS k4ultra_players_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player_name TEXT,
        map_name TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_playtime (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player_name TEXT,
        map_name TEXT,
        total_minutes INTEGER DEFAULT 0,
        last_seen DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player1 TEXT,
        player2 TEXT,
        probability_score INTEGER DEFAULT 0,
        is_manual INTEGER DEFAULT 0,
        shared_minutes INTEGER DEFAULT 0,
        UNIQUE(guild_id, player1, player2)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        week_number INTEGER,
        embed_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER,
        mode TEXT DEFAULT 'radar'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player_name TEXT,
        map_name TEXT,
        start_time DATETIME,
        end_time DATETIME,
        is_active INTEGER DEFAULT 1,
        last_duration INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_tribe_names (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        tribe_signature TEXT,
        custom_name TEXT,
        UNIQUE(guild_id, tribe_signature)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_fixed_tribes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        name TEXT,
        members_json TEXT,
        is_own INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS k4ultra_aliases (
        player_name TEXT,
        guild_id INTEGER NOT NULL,
        alias TEXT,
        PRIMARY KEY (guild_id, player_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS player_identities_link (
        guild_id INTEGER NOT NULL,
        secondary_name TEXT NOT NULL,
        primary_name TEXT NOT NULL,
        PRIMARY KEY (guild_id, secondary_name)
    )
    """,
    # KDA
    """
    CREATE TABLE IF NOT EXISTS tribe_kda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player_name TEXT,
        kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        UNIQUE(guild_id, player_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tribe_characters (
        character_name TEXT,
        guild_id INTEGER NOT NULL,
        player_name TEXT,
        PRIMARY KEY (guild_id, character_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kda_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        channel_id INTEGER,
        message_id INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tribe_death_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        player_name TEXT NOT NULL,
        died_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Breeding alarms
    """
    CREATE TABLE IF NOT EXISTS breeding_alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER,
        channel_id INTEGER,
        alert_time TIMESTAMP
    )
    """,
    # Alarmas de intrusos
    """
    CREATE TABLE IF NOT EXISTS map_alarms (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        map_name TEXT NOT NULL,
        channel_id INTEGER,
        PRIMARY KEY(guild_id, user_id, map_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS map_last_players (
        guild_id INTEGER NOT NULL,
        map_name TEXT NOT NULL,
        players_json TEXT,
        PRIMARY KEY(guild_id, map_name)
    )
    """,
    # Eventos
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        title TEXT,
        description TEXT,
        creator_id INTEGER,
        channel_id INTEGER,
        message_id INTEGER,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        event_id INTEGER,
        option_text TEXT,
        voter_ids TEXT DEFAULT '[]',
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """,
    # Control de ciclos de actualización de A2S (reemplazo del `current_minute % interval`)
    """
    CREATE TABLE IF NOT EXISTS guild_loop_state (
        guild_id INTEGER PRIMARY KEY,
        last_a2s_run TIMESTAMP
    )
    """,
]


# --- Migraciones aditivas (ALTER TABLE) ---
# Cada entrada: (tabla, columna, ddl_completo)
# Tolerantes a "columna ya existe" — usar OperationalError.
MIGRATIONS: list[tuple[str, str]] = [
    ("guild_config", "ALTER TABLE guild_config ADD COLUMN bot_owner_id INTEGER"),
    ("guild_config", "ALTER TABLE guild_config ADD COLUMN daily_points_enabled INTEGER DEFAULT 1"),
    ("guild_config", "ALTER TABLE guild_config ADD COLUMN vote_urls TEXT"),
    ("blacklist", "ALTER TABLE blacklist ADD COLUMN last_seen TEXT"),
    ("blacklist", "ALTER TABLE blacklist ADD COLUMN total_hours REAL DEFAULT 0"),
    ("blacklist", "ALTER TABLE blacklist ADD COLUMN is_enemy INTEGER DEFAULT 1"),
    ("daily_points_users", "ALTER TABLE daily_points_users ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0"),
    ("daily_points_users", "ALTER TABLE daily_points_users ADD COLUMN alert_hour INTEGER DEFAULT 8"),
    ("daily_points_users", "ALTER TABLE daily_points_users ADD COLUMN timezone TEXT DEFAULT 'es'"),
    ("daily_points_users", "ALTER TABLE daily_points_users ADD COLUMN last_sent_date TEXT"),
    ("k4ultra_messages", "ALTER TABLE k4ultra_messages ADD COLUMN mode TEXT DEFAULT 'radar'"),
    ("k4ultra_sessions", "ALTER TABLE k4ultra_sessions ADD COLUMN last_duration INTEGER DEFAULT 0"),
    ("k4ultra_fixed_tribes", "ALTER TABLE k4ultra_fixed_tribes ADD COLUMN is_own INTEGER DEFAULT 0"),
    ("k4ultra_fixed_tribes", "ALTER TABLE k4ultra_fixed_tribes ADD COLUMN is_ally INTEGER DEFAULT 0"),
    (
        "k4ultra_relationships",
        "ALTER TABLE k4ultra_relationships ADD COLUMN shared_minutes INTEGER DEFAULT 0",
    ),
    ("dinos", "ALTER TABLE dinos ADD COLUMN oxy INTEGER"),
    ("dinos", "ALTER TABLE dinos ADD COLUMN food INTEGER"),
    ("dinos", "ALTER TABLE dinos ADD COLUMN speed INTEGER"),
]

# Auto-migración de guild_id para tablas legacy que pudieran no tenerla.
LEGACY_GUILD_ID_TABLES: list[str] = [
    "k4ultra_config",  # tabla legacy histórica
    "k4ultra_relationships",
    "k4ultra_tribe_names",
    "tribe_kda",
    "tribe_characters",
    "k4ultra_aliases",
]


# --- Índices (mejora de rendimiento) ---
INDEXES: list[str] = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tribe_kda_guild_player ON tribe_kda(guild_id, player_name)",
    "CREATE INDEX IF NOT EXISTS idx_k4u_sessions_guild_player  ON k4ultra_sessions(guild_id, player_name)",
    "CREATE INDEX IF NOT EXISTS idx_k4u_sessions_active        ON k4ultra_sessions(guild_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_k4u_playtime_guild_player  ON k4ultra_playtime(guild_id, player_name)",
    "CREATE INDEX IF NOT EXISTS idx_k4u_players_log_guild_time ON k4ultra_players_log(guild_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_k4u_relations_guild        ON k4ultra_relationships(guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_blacklist_guild            ON blacklist(guild_id)",
    "CREATE INDEX IF NOT EXISTS idx_death_log_guild_player     ON tribe_death_log(guild_id, player_name)",
    "CREATE INDEX IF NOT EXISTS idx_event_options_event        ON event_options(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_scouts_guild_map           ON scouts(guild_id, mapa)",
    "CREATE INDEX IF NOT EXISTS idx_dinos_guild_especie        ON dinos(guild_id, especie)",
]


# --- PRAGMAs de rendimiento ---
PRAGMAS: list[str] = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
]


async def apply_pragmas(db: aiosqlite.Connection) -> None:
    """Aplica los PRAGMAs de rendimiento a una conexión abierta."""
    for pragma in PRAGMAS:
        try:
            await db.execute(pragma)
        except aiosqlite.Error as e:
            logger.warning(f"[Schema] PRAGMA falló ('{pragma}'): {e}")


async def create_tables(db: aiosqlite.Connection) -> None:
    """Crea todas las tablas si no existen."""
    for ddl in TABLES:
        await db.execute(ddl)
    await db.commit()


async def create_indexes(db: aiosqlite.Connection) -> None:
    """Crea todos los índices si no existen."""
    for ddl in INDEXES:
        try:
            await db.execute(ddl)
        except aiosqlite.OperationalError as e:
            logger.debug(f"[Schema] Índice ya existente: {e}")
    await db.commit()


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Aplica migraciones aditivas idempotentes."""
    for _table, ddl in MIGRATIONS:
        try:
            await db.execute(ddl)
        except aiosqlite.OperationalError:
            pass  # La columna ya existe — comportamiento esperado.

    for table in LEGACY_GUILD_ID_TABLES:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER")
            logger.info(f"[Schema] Migración: columna guild_id añadida a {table}")
        except aiosqlite.OperationalError:
            pass  # La columna ya existe o la tabla no existe.

    await db.commit()


async def init_database(db_path: str) -> None:
    """Punto único de entrada. Aplica PRAGMAs, crea tablas, índices y migraciones."""
    async with aiosqlite.connect(db_path) as db:
        await apply_pragmas(db)
        await create_tables(db)
        await run_migrations(db)
        await create_indexes(db)
    logger.info("[Schema] Base de datos inicializada (tablas, índices, migraciones).")
