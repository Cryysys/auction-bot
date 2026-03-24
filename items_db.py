import sqlite3
import os

DB_PATH = os.getenv(
    "ITEMS_DB_PATH", "items.db"
)  # separate environment variable for Railway


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    # raw_items table – structure as per the game's data
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_items (
            id INTEGER PRIMARY KEY,
            type TEXT,
            image_url TEXT,
            description TEXT,
            equipable INTEGER,
            level INTEGER,
            rarity TEXT,
            value INTEGER,
            stat1 TEXT,
            stat1modifier INTEGER,
            stat2 TEXT,
            stat2modifier INTEGER,
            stat3 TEXT,
            stat3modifier INTEGER,
            custom_item INTEGER,
            tradable INTEGER,
            locked INTEGER,
            circulation INTEGER,
            market_low INTEGER,
            market_high INTEGER
        )
    """
    )
    # active items (just links to raw_items)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS active_items (
            raw_item_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(raw_item_id) REFERENCES raw_items(id)
        )
    """
    )
    # full‑text search virtual table
    c.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_raw USING fts5(
            name, content=raw_items, content_rowid=id
        )
    """
    )
    # triggers to keep fts in sync with raw_items
    c.execute(
        """
        CREATE TRIGGER IF NOT EXISTS raw_items_ai AFTER INSERT ON raw_items BEGIN
            INSERT INTO fts_raw(rowid, name) VALUES (new.id, new.name);
        END
    """
    )
    c.execute(
        """
        CREATE TRIGGER IF NOT EXISTS raw_items_ad AFTER DELETE ON raw_items BEGIN
            INSERT INTO fts_raw(fts_raw, rowid, name) VALUES ('delete', old.id, old.name);
        END
    """
    )
    c.execute(
        """
        CREATE TRIGGER IF NOT EXISTS raw_items_au AFTER UPDATE ON raw_items BEGIN
            INSERT INTO fts_raw(fts_raw, rowid, name) VALUES ('delete', old.id, old.name);
            INSERT INTO fts_raw(rowid, name) VALUES (new.id, new.name);
        END
    """
    )
    conn.commit()
    conn.close()


def import_raw_items(sql_text):
    """
    Import the SQL dump into raw_items.
    Assumes the dump contains a table named 'items' with the exact columns we need.
    We'll rename that table to 'raw_items' during import.
    """
    import re

    # Replace table name 'items' with 'raw_items' (case‑insensitive word boundaries)
    # Be careful to not replace inside strings – but the dump likely uses the table name as an identifier.
    modified_sql = re.sub(r"\bitems\b", "raw_items", sql_text, flags=re.IGNORECASE)
    conn = get_connection()
    c = conn.cursor()
    # Begin transaction
    c.execute("BEGIN TRANSACTION")
    try:
        c.executescript(modified_sql)
        conn.commit()
        # Count imported rows
        c.execute("SELECT COUNT(*) FROM raw_items")
        count = c.fetchone()[0]
        # Also add names to FTS (already done via triggers)
        return count
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def add_active_item(raw_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO active_items (raw_item_id) VALUES (?)", (raw_id,))
    conn.commit()
    conn.close()
    return c.rowcount > 0


def remove_active_item(raw_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM active_items WHERE raw_item_id = ?", (raw_id,))
    conn.commit()
    conn.close()
    return c.rowcount > 0


def get_active_items(offset=0, limit=20):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT r.id, r.name, r.type, r.rarity, r.level
        FROM raw_items r
        JOIN active_items a ON r.id = a.raw_item_id
        ORDER BY r.name
        LIMIT ? OFFSET ?
    """,
        (limit, offset),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def count_active_items():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM active_items")
    count = c.fetchone()[0]
    conn.close()
    return count


def search_raw_items(query, limit=10):
    conn = get_connection()
    c = conn.cursor()
    # Use FTS for fast search
    c.execute(
        """
        SELECT r.id, r.name, r.type, r.rarity
        FROM raw_items r
        JOIN fts_raw f ON r.id = f.rowid
        WHERE f.name MATCH ?
        ORDER BY rank
        LIMIT ?
    """,
        (query, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_item_details(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM raw_items WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    if row:
        # Convert to dict for easy access
        cols = [desc[0] for desc in c.description]
        return dict(zip(cols, row))
    return None
