import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "data.db")


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 1. Users Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)"""
    )

    # 2. Items Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS items
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, image_url TEXT)"""
    )

    # 3. Settings Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)"""
    )

    # 4. Draws Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS draws
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_id INTEGER,
                  drawn_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(user_id),
                  FOREIGN KEY(item_id) REFERENCES items(id))"""
    )

    # 5. Scheduled Auctions Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS scheduled_auctions
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  channel_id INTEGER,
                  seller_id INTEGER,
                  item_name TEXT,
                  duration TEXT,
                  start_price TEXT,
                  min_increment TEXT,
                  image_url TEXT,
                  start_time TIMESTAMP)"""
    )

    # 6. Notifications Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS scheduled_notifs (
                    auction_id INTEGER,
                    user_id INTEGER,
                    UNIQUE(auction_id, user_id))"""
    )

    conn.commit()
    conn.close()  # Now we close it ONLY once at the very end.


# --- ITEM FUNCTIONS ---


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


# --- POINT FUNCTIONS ---


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


# --- SETTINGS & DRAWS ---


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


# --- AUCTION FUNCTIONS ---


def add_scheduled_auction(
    channel_id, seller_id, item, duration, price, inc, img, start_t
):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO scheduled_auctions
                  (channel_id, seller_id, item_name, duration, start_price, min_increment, image_url, start_time)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            channel_id,
            seller_id,
            item,
            duration,
            price,
            inc,
            img,
            start_t.isoformat(),
        ),
    )
    row_id = c.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_pending_auctions():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scheduled_auctions ORDER BY start_time ASC")
    rows = c.fetchall()
    conn.close()
    return rows


def get_scheduled_auction_item_name(auction_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT item_name FROM scheduled_auctions WHERE id = ?", (auction_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def remove_scheduled_auction(row_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM scheduled_auctions WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


def toggle_scheduled_notif(auction_id, user_id):
    """Returns True if added, False if removed"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO scheduled_notifs (auction_id, user_id) VALUES (?, ?)",
            (auction_id, user_id),
        )
        conn.commit()
        added = True
    except sqlite3.IntegrityError:
        c.execute(
            "DELETE FROM scheduled_notifs WHERE auction_id = ? AND user_id = ?",
            (auction_id, user_id),
        )
        conn.commit()
        added = False
    conn.close()
    return added


def get_scheduled_notifs(auction_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM scheduled_notifs WHERE auction_id = ?", (auction_id,)
    )
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def get_channel_upcoming(channel_id, limit=None):
    conn = get_connection()
    c = conn.cursor()
    query = (
        "SELECT * FROM scheduled_auctions WHERE channel_id = ? ORDER BY start_time ASC"
    )
    if limit:
        query += f" LIMIT {limit}"
    c.execute(query, (channel_id,))
    rows = c.fetchall()
    conn.close()
    return rows
