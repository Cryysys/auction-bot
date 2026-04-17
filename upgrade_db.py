import sqlite3
import sys
import os

# This helper forces Ferox to show the text immediately
def print_now(text):
    print(text)
    sys.stdout.flush()

# This must match your actual database filename
DB_FILE = "data.db" 

def run_upgrade():
    print_now("🚀 Diagnostic Script Started...")
    
    # Check if the file even exists
    if not os.path.exists(DB_FILE):
        print_now(f"❌ ERROR: I cannot find '{DB_FILE}' in this folder.")
        print_now(f"Files I see here: {os.listdir('.')}")
        return

    print_now(f"📂 Found '{DB_FILE}'. Connecting...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Let's find out what your table is actually named
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print_now(f"📊 Your database has these tables: {tables}")

    # Determine the correct table (usually 'users' or 'points')
    target_table = None
    if 'users' in tables: target_table = 'users'
    elif 'points' in tables: target_table = 'points'
    
    if not target_table:
        print_now("❌ ERROR: I don't see a 'users' or 'points' table. Please check your database.py.")
        return

    print_now(f"✅ Target confirmed: '{target_table}' table.")

    try:
        print_now("Attempting to add 'cumulative_points' column...")
        cursor.execute(f"ALTER TABLE {target_table} ADD COLUMN cumulative_points INTEGER DEFAULT 0;")
        
        print_now("Syncing current points to all-time points...")
        cursor.execute(f"UPDATE {target_table} SET cumulative_points = points;")
        
        conn.commit()
        print_now("✨ SUCCESS: Database upgraded successfully!")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print_now("ℹ️ NOTICE: The column already exists. You are good to go!")
        else:
            print_now(f"⚠️ SQL ERROR: {e}")
            
    conn.close()
    print_now("🏁 Script finished.")

if __name__ == "__main__":
    run_upgrade()