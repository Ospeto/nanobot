import sqlite3
import os

def migrate():
    db_path = os.path.expanduser("~/.digimon/brain.sqlite")
    if not os.path.exists(db_path):
        db_path = "brain.sqlite" # Fallback local
        if not os.path.exists(db_path):
            print("Database not found. Skipping migration.")
            return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(digimon_roster)")
    columns = [info[1] for info in cursor.fetchall()]
    
    try:
        if "str_stat" not in columns:
            cursor.execute("ALTER TABLE digimon_roster ADD COLUMN str_stat INTEGER DEFAULT 0")
            print("Added str_stat")
        if "agi_stat" not in columns:
            cursor.execute("ALTER TABLE digimon_roster ADD COLUMN agi_stat INTEGER DEFAULT 0")
            print("Added agi_stat")
        if "int_stat" not in columns:
            cursor.execute("ALTER TABLE digimon_roster ADD COLUMN int_stat INTEGER DEFAULT 0")
            print("Added int_stat")
            
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
