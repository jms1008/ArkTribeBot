import sqlite3
import os

DB_NAME = "tribe_data.db"

def check_db():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print("--- Checking Characters ---")
    cursor.execute("SELECT * FROM tribe_characters WHERE character_name LIKE ?", ('%TPR%',))
    chars = cursor.fetchall()
    if chars:
        for c in chars:
            print(c)
    else:
        print("No characters found matching 'TPR'.")

    print("\n--- Checking Guild Configs ---")
    cursor.execute("SELECT guild_id, log_channel_id FROM guild_config")
    configs = cursor.fetchall()
    for cfg in configs:
        print(cfg)

    conn.close()

if __name__ == "__main__":
    check_db()
