import aiosqlite
import logging
import os
import pytest
from datetime import datetime, timedelta

logger = logging.getLogger("Test")


class MockBot:
    db_name = "test_memory.db"


@pytest.mark.asyncio
async def test_k4ultra_generic():
    bot = MockBot()
    if os.path.exists(bot.db_name):
        os.remove(bot.db_name)

    async with aiosqlite.connect(bot.db_name) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS k4ultra_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, player_name TEXT, map_name TEXT, start_time DATETIME, end_time DATETIME, is_active INTEGER DEFAULT 1, last_duration INTEGER DEFAULT 0)"
        )
        # Insert historical data: 123 is offline, 123_1 is offline, 123_2 is offline
        now = datetime.now()
        thirty_mins_ago = (now - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

        # NOTE: 123 and 123_2 logged off 30 mins ago. 123_1 logged off 1 minute ago!
        one_min_ago = (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            "INSERT INTO k4ultra_sessions (player_name, map_name, start_time, end_time, is_active) VALUES (?, ?, ?, ?, 0)",
            ("123", "Isla", thirty_mins_ago, thirty_mins_ago),
        )
        await db.execute(
            "INSERT INTO k4ultra_sessions (player_name, map_name, start_time, end_time, is_active) VALUES (?, ?, ?, ?, 0)",
            ("123_1", "Aberration", one_min_ago, one_min_ago),
        )
        await db.execute(
            "INSERT INTO k4ultra_sessions (player_name, map_name, start_time, end_time, is_active) VALUES (?, ?, ?, ?, 0)",
            ("123_2", "Gen2", thirty_mins_ago, thirty_mins_ago),
        )

        await db.execute(
            "CREATE TABLE IF NOT EXISTS k4ultra_players_log (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT, map_name TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS k4ultra_playtime (id INTEGER PRIMARY KEY AUTOINCREMENT, player_name TEXT, map_name TEXT, total_minutes INTEGER DEFAULT 0, last_seen DATETIME)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS k4ultra_relationships (id INTEGER PRIMARY KEY AUTOINCREMENT, player1 TEXT, player2 TEXT, probability_score INTEGER DEFAULT 0, is_manual INTEGER DEFAULT 0, UNIQUE(player1, player2))"
        )
        await db.commit()

    async def gather_player_data(all_fetched):
        now = datetime.now()
        async with aiosqlite.connect(bot.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, player_name, map_name, start_time, end_time FROM k4ultra_sessions WHERE is_active = 1"
            )
            active_pool = [dict(s) for s in await cursor.fetchall()]

            ten_mins_ago = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute(
                "SELECT id, player_name, map_name, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND end_time >= ? ORDER BY end_time DESC",
                (ten_mins_ago,),
            )
            recent_closed_pool = [dict(s) for s in await cursor.fetchall()]

            seen_identities = set()
            active_pool_dict = {s["id"]: s for s in active_pool}

            def extract_base(ident):
                parts = ident.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return parts[0]
                return ident

            for fp in all_fetched:
                map_m = fp["map"]
                raw_name = fp["raw_name"]
                true_identity = None
                for sid, s in active_pool_dict.items():
                    if sid not in seen_identities and s["map_name"] == map_m:
                        if extract_base(s["player_name"]) == raw_name:
                            true_identity = s["player_name"]
                            seen_identities.add(sid)
                            await db.execute(
                                "UPDATE k4ultra_sessions SET end_time = ? WHERE id = ?",
                                (now.strftime("%Y-%m-%d %H:%M:%S"), sid),
                            )
                            fp["matched"] = True
                            fp["true_identity"] = true_identity
                            break

            for fp in all_fetched:
                if fp.get("matched"):
                    continue

                map_m = fp["map"]
                raw_name = fp["raw_name"]
                true_identity = None
                identities_already_online = [
                    active_pool_dict[sid]["player_name"]
                    for sid in seen_identities
                    if sid in active_pool_dict
                ]
                generic_names = {"123", "human", "humano", "survivor", "player", "bob"}
                is_generic = raw_name.lower() in generic_names

                pool_to_check = recent_closed_pool
                if is_generic:
                    cursor = await db.execute(
                        "SELECT id, player_name, map_name, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND player_name LIKE ? ORDER BY end_time DESC",
                        (f"{raw_name}_%",),
                    )
                    cursor2 = await db.execute(
                        "SELECT id, player_name, map_name, start_time, end_time FROM k4ultra_sessions WHERE is_active = 0 AND player_name = ? ORDER BY end_time DESC",
                        (raw_name,),
                    )
                    generic_inactive = [dict(s) for s in await cursor.fetchall()]
                    generic_inactive.extend([dict(s) for s in await cursor2.fetchall()])

                    for sid, sinfo in active_pool_dict.items():
                        if (
                            sid not in seen_identities
                            and extract_base(sinfo["player_name"]) == raw_name
                        ):
                            dummy_inactive = {
                                "id": sinfo["id"],
                                "player_name": sinfo["player_name"],
                                "map_name": sinfo["map_name"],
                                "start_time": sinfo.get("start_time", ""),
                                "end_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            generic_inactive.append(dummy_inactive)

                    generic_inactive.sort(
                        key=lambda x: (x["end_time"], -len(x["player_name"])),
                        reverse=True,
                    )
                    pool_to_check = generic_inactive

                for s in pool_to_check:
                    if (
                        extract_base(s["player_name"]) == raw_name
                        and s["player_name"] not in identities_already_online
                    ):
                        true_identity = s["player_name"]
                        cursor = await db.execute(
                            "INSERT INTO k4ultra_sessions (player_name, map_name, start_time, end_time, is_active) VALUES (?, ?, ?, ?, 1)",
                            (
                                true_identity,
                                map_m,
                                now.strftime("%Y-%m-%d %H:%M:%S"),
                                now.strftime("%Y-%m-%d %H:%M:%S"),
                            ),
                        )
                        new_id = cursor.lastrowid
                        seen_identities.add(new_id)
                        active_pool_dict[new_id] = {
                            "id": new_id,
                            "player_name": true_identity,
                            "map_name": map_m,
                        }
                        fp["true_identity"] = true_identity
                        break

                if not true_identity:
                    if is_generic:
                        cursor = await db.execute(
                            "SELECT player_name FROM k4ultra_sessions WHERE player_name LIKE ?",
                            (f"{raw_name}_%",),
                        )
                        existing = await cursor.fetchall()
                        max_suffix = 0
                        for e in existing:
                            parts = e["player_name"].rsplit("_", 1)
                            if (
                                len(parts) == 2
                                and parts[1].isdigit()
                                and parts[0] == raw_name
                            ):
                                val = int(parts[1])
                                if val > max_suffix:
                                    max_suffix = val

                        if raw_name not in identities_already_online and not any(
                            e["player_name"] == raw_name for e in existing
                        ):
                            true_identity = raw_name
                        else:
                            true_identity = f"{raw_name}_{max_suffix + 1}"
                    else:
                        true_identity = raw_name

                    cursor = await db.execute(
                        "INSERT INTO k4ultra_sessions (player_name, map_name, start_time, end_time, is_active) VALUES (?, ?, ?, ?, 1)",
                        (
                            true_identity,
                            map_m,
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    new_id = cursor.lastrowid
                    seen_identities.add(new_id)
                    active_pool_dict[new_id] = {
                        "id": new_id,
                        "player_name": true_identity,
                        "map_name": map_m,
                    }
                    fp["true_identity"] = true_identity

                await db.execute(
                    "INSERT INTO k4ultra_players_log (player_name, map_name) VALUES (?, ?)",
                    (true_identity, map_m),
                )
                cursor = await db.execute(
                    "SELECT id FROM k4ultra_playtime WHERE player_name = ? AND map_name = ?",
                    (true_identity, map_m),
                )
                pt_row = await cursor.fetchone()
                if pt_row:
                    await db.execute(
                        "UPDATE k4ultra_playtime SET total_minutes = total_minutes + 5, last_seen = ? WHERE id = ?",
                        (now.strftime("%Y-%m-%d %H:%M:%S"), pt_row["id"]),
                    )
                else:
                    await db.execute(
                        "INSERT INTO k4ultra_playtime (player_name, map_name, total_minutes, last_seen) VALUES (?, ?, ?, ?)",
                        (true_identity, map_m, 5, now.strftime("%Y-%m-%d %H:%M:%S")),
                    )

            for sid, s in active_pool_dict.items():
                if sid not in seen_identities and sid in [a["id"] for a in active_pool]:
                    await db.execute(
                        "UPDATE k4ultra_sessions SET is_active = 0 WHERE id = ?", (sid,)
                    )

            await db.commit()

            # Print current active sessions
            cursor = await db.execute(
                "SELECT id, player_name, map_name FROM k4ultra_sessions WHERE is_active = 1"
            )
            print("ACTIVE SESSIONS:", [dict(r) for r in await cursor.fetchall()])
