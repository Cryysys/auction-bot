import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "data.db")


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, image_url TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS draws
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id INTEGER,
                  drawn_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(user_id),
                  FOREIGN KEY(item_id) REFERENCES items(id))"""
    )
    conn.commit()
    conn.close()


def add_item(name, image_url):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO items (name, image_url) VALUES (?, ?)", (name, image_url))
    item_id = c.lastrowid
    conn.commit()
    conn.close()
    return item_id


def remove_item(item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_all_items():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, image_url FROM items ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows


def add_points(user_id, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?",
        (user_id, amount, amount),
    )
    conn.commit()
    conn.close()


def remove_points(user_id, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET points = points - ? WHERE user_id = ? AND points >= ?",
        (amount, user_id, amount),
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_points(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def set_setting(key, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def record_draw(user_id, item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO draws (user_id, item_id) VALUES (?, ?)", (user_id, item_id))
    conn.commit()
    conn.close()


def draw_random_item():
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute("SELECT id, name, image_url FROM items ORDER BY RANDOM() LIMIT 1")
        row = c.fetchone()
        if row is None:
            conn.rollback()
            return None
        item_id, name, url = row
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        return (item_id, name, url)
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
