import sqlite3
import os
from typing import Any

DB_PATH = os.getenv("DATABASE_PATH", "data.db")


def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # 1. Users Table (Updated with cumulative_points)
    c.execute(
        """CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   points INTEGER DEFAULT 0,
                   cumulative_points INTEGER DEFAULT 0)"""
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

    # 7. Collectables Catalog Table
    c.execute(
        """CREATE TABLE IF NOT EXISTS collectables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    rarity TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    release_date TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1)"""
    )

    # 8. User Collectable Inventory
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_collectable_inventory (
                    user_id INTEGER NOT NULL,
                    collectable_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
                    PRIMARY KEY (user_id, collectable_id),
                    FOREIGN KEY (collectable_id) REFERENCES collectables(id))"""
    )

    # 9. User Wishlist
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_wishlist (
                    user_id INTEGER NOT NULL,
                    collectable_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, collectable_id),
                    FOREIGN KEY (collectable_id) REFERENCES collectables(id))"""
    )

    # 10. User Showcase
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_showcase (
                    user_id INTEGER NOT NULL,
                    slot_index INTEGER NOT NULL CHECK(slot_index BETWEEN 1 AND 5),
                    collectable_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, slot_index),
                    FOREIGN KEY (collectable_id) REFERENCES collectables(id))"""
    )

    # 11. User Collectable Drop Progress
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_collectable_progress (
                    user_id INTEGER PRIMARY KEY,
                    last_drop_at TIMESTAMP,
                    messages_since_drop INTEGER NOT NULL DEFAULT 0,
                    last_eligible_msg_at TIMESTAMP)"""
    )

    # 12. User Resources (Diamonds)
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_resources (
                    user_id INTEGER PRIMARY KEY,
                    diamonds INTEGER NOT NULL DEFAULT 0 CHECK(diamonds >= 0))"""
    )

    # Useful indexes for command and drop performance
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_collectables_rarity_active ON collectables(rarity, is_active)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_collectables_category ON collectables(category)"
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_user_quantity ON user_collectable_inventory(user_id, quantity)"
    )

    conn.commit()
    conn.close()


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
    """Admin/Reward logic: Adds to both Current and All-Time totals."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO users (user_id, points, cumulative_points) VALUES (?, ?, ?) 
           ON CONFLICT(user_id) DO UPDATE SET 
           points = points + ?, 
           cumulative_points = cumulative_points + ?""",
        (user_id, amount, amount, amount, amount),
    )
    conn.commit()
    conn.close()


def remove_points(user_id, amount):
    """Admin Punishment logic: Removes from both Current and All-Time totals."""
    conn = get_connection()
    c = conn.cursor()
    # We use MAX(0, ...) to ensure cumulative doesn't go below zero
    c.execute(
        """UPDATE users SET 
           points = points - ?, 
           cumulative_points = MAX(0, cumulative_points - ?) 
           WHERE user_id = ? AND points >= ?""",
        (amount, amount, user_id, amount),
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def spend_points(user_id, amount):
    """User Spend logic: Removes ONLY from current balance (keeps cumulative high score)."""
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
    c.execute(
        "SELECT id, channel_id, seller_id, item_name, duration, start_price, min_increment, image_url, start_time FROM scheduled_auctions ORDER BY start_time ASC"
    )
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
    query = "SELECT id, channel_id, seller_id, item_name, duration, start_price, min_increment, image_url, start_time FROM scheduled_auctions WHERE channel_id = ? ORDER BY start_time ASC"
    if limit:
        query += f" LIMIT {limit}"
    c.execute(query, (channel_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# --- COLLECTABLE CATALOG ---


def upsert_collectable(
    name: str,
    category: str,
    rarity: str,
    description: str | None = None,
    image_url: str | None = None,
    release_date: str | None = None,
    is_active: bool = True,
) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO collectables (name, category, rarity, description, image_url, release_date, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             category = excluded.category,
             rarity = excluded.rarity,
             description = excluded.description,
             image_url = excluded.image_url,
             release_date = excluded.release_date,
             is_active = excluded.is_active""",
        (
            name.strip(),
            category.strip(),
            rarity.strip().lower(),
            (description or "").strip(),
            (image_url or "").strip(),
            (release_date or "").strip(),
            1 if is_active else 0,
        ),
    )
    c.execute("SELECT id FROM collectables WHERE name = ?", (name.strip(),))
    row = c.fetchone()
    conn.commit()
    conn.close()
    if row is None:
        raise RuntimeError(f"Failed to upsert collectable {name}")
    return int(row[0])


def get_collectable_by_name(name: str) -> tuple[Any, ...] | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, name, category, rarity, description, image_url, release_date, is_active
           FROM collectables
           WHERE LOWER(name) = LOWER(?)""",
        (name.strip(),),
    )
    row = c.fetchone()
    conn.close()
    return row


def search_collectables_by_name(query: str, limit: int = 25) -> list[tuple[Any, ...]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, name, category, rarity, description, image_url, release_date
           FROM collectables
           WHERE name LIKE ?
           ORDER BY name ASC
           LIMIT ?""",
        (f"%{query.strip()}%", limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_collectable_by_id(collectable_id: int) -> tuple[Any, ...] | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, name, category, rarity, description, image_url, release_date, is_active
           FROM collectables WHERE id = ?""",
        (collectable_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def get_collectable_categories() -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM collectables ORDER BY category ASC")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def get_collectable_count() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM collectables WHERE is_active = 1")
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def get_collectables_by_rarity(rarity: str) -> list[tuple[Any, ...]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, name, category, rarity, description, image_url, release_date
           FROM collectables
           WHERE rarity = ? AND is_active = 1
           ORDER BY name ASC""",
        (rarity.strip().lower(),),
    )
    rows = c.fetchall()
    conn.close()
    return rows


# --- USER RESOURCES (DIAMONDS) ---


def get_diamonds(user_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT diamonds FROM user_resources WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def add_diamonds(user_id: int, amount: int) -> None:
    if amount < 0:
        raise ValueError("amount must be positive")
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_resources (user_id, diamonds) VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET diamonds = diamonds + excluded.diamonds""",
        (user_id, amount),
    )
    conn.commit()
    conn.close()


def spend_diamonds(user_id: int, amount: int) -> bool:
    if amount < 0:
        raise ValueError("amount must be positive")
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE user_resources
           SET diamonds = diamonds - ?
           WHERE user_id = ? AND diamonds >= ?""",
        (amount, user_id, amount),
    )
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# --- USER INVENTORY ---


def add_collectable_to_inventory(user_id: int, collectable_id: int, quantity: int = 1) -> None:
    if quantity < 1:
        raise ValueError("quantity must be >= 1")
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_collectable_inventory (user_id, collectable_id, quantity)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, collectable_id) DO UPDATE
           SET quantity = quantity + excluded.quantity""",
        (user_id, collectable_id, quantity),
    )
    conn.commit()
    conn.close()


def remove_collectable_from_inventory(
    user_id: int, collectable_id: int, quantity: int = 1
) -> bool:
    if quantity < 1:
        raise ValueError("quantity must be >= 1")
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        c = conn.cursor()
        c.execute(
            """SELECT quantity
               FROM user_collectable_inventory
               WHERE user_id = ? AND collectable_id = ?""",
            (user_id, collectable_id),
        )
        row = c.fetchone()
        if row is None or int(row[0]) < quantity:
            conn.rollback()
            return False
        remaining = int(row[0]) - quantity
        if remaining == 0:
            c.execute(
                "DELETE FROM user_collectable_inventory WHERE user_id = ? AND collectable_id = ?",
                (user_id, collectable_id),
            )
        else:
            c.execute(
                """UPDATE user_collectable_inventory
                   SET quantity = ?
                   WHERE user_id = ? AND collectable_id = ?""",
                (remaining, user_id, collectable_id),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_inventory_item_quantity(user_id: int, collectable_id: int) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT quantity
           FROM user_collectable_inventory
           WHERE user_id = ? AND collectable_id = ?""",
        (user_id, collectable_id),
    )
    row = c.fetchone()
    conn.close()
    return int(row[0]) if row else 0


def get_user_inventory(
    user_id: int,
    category: str | None = None,
    rarity: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[tuple[Any, ...]]:
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT c.id, c.name, c.category, c.rarity, c.description, c.image_url, c.release_date, i.quantity
        FROM user_collectable_inventory i
        JOIN collectables c ON c.id = i.collectable_id
        WHERE i.user_id = ? AND i.quantity > 0 AND c.is_active = 1
    """
    params: list[Any] = [user_id]
    if category:
        query += " AND c.category = ?"
        params.append(category)
    if rarity:
        query += " AND c.rarity = ?"
        params.append(rarity.lower())
    query += " ORDER BY c.category ASC, c.rarity ASC, c.name ASC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    c.execute(query, tuple(params))
    rows = c.fetchall()
    conn.close()
    return rows


# --- WISHLIST ---


def add_wishlist_item(user_id: int, collectable_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO user_wishlist (user_id, collectable_id) VALUES (?, ?)",
            (user_id, collectable_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_wishlist_item(user_id: int, collectable_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM user_wishlist WHERE user_id = ? AND collectable_id = ?",
        (user_id, collectable_id),
    )
    removed = c.rowcount > 0
    conn.commit()
    conn.close()
    return removed


def get_user_wishlist(user_id: int) -> list[tuple[Any, ...]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT c.id, c.name, c.category, c.rarity, c.image_url
           FROM user_wishlist w
           JOIN collectables c ON c.id = w.collectable_id
           WHERE w.user_id = ? AND c.is_active = 1
           ORDER BY c.rarity ASC, c.name ASC""",
        (user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def is_collectable_wished(user_id: int, collectable_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM user_wishlist WHERE user_id = ? AND collectable_id = ?",
        (user_id, collectable_id),
    )
    row = c.fetchone()
    conn.close()
    return row is not None


# --- SHOWCASE ---


def set_showcase_slot(user_id: int, slot_index: int, collectable_id: int) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_showcase (user_id, slot_index, collectable_id)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id, slot_index) DO UPDATE SET
           collectable_id = excluded.collectable_id""",
        (user_id, slot_index, collectable_id),
    )
    conn.commit()
    conn.close()


def get_user_showcase(user_id: int) -> list[tuple[Any, ...]]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT s.slot_index, c.id, c.name, c.category, c.rarity, c.image_url
           FROM user_showcase s
           JOIN collectables c ON c.id = s.collectable_id
           WHERE s.user_id = ?
           ORDER BY s.slot_index ASC""",
        (user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


# --- DROP PROGRESS ---


def get_user_collectable_progress(user_id: int) -> tuple[int, str | None, str | None]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT messages_since_drop, last_drop_at, last_eligible_msg_at
           FROM user_collectable_progress
           WHERE user_id = ?""",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return (0, None, None)
    return (int(row[0]), row[1], row[2])


def update_collectable_progress_no_drop(
    user_id: int, messages_since_drop: int, last_eligible_msg_at_iso: str
) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_collectable_progress
           (user_id, messages_since_drop, last_eligible_msg_at)
           VALUES (?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
           messages_since_drop = excluded.messages_since_drop,
           last_eligible_msg_at = excluded.last_eligible_msg_at""",
        (user_id, messages_since_drop, last_eligible_msg_at_iso),
    )
    conn.commit()
    conn.close()


def reset_collectable_progress_after_drop(user_id: int, now_iso: str) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO user_collectable_progress
           (user_id, messages_since_drop, last_drop_at, last_eligible_msg_at)
           VALUES (?, 0, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
           messages_since_drop = 0,
           last_drop_at = excluded.last_drop_at,
           last_eligible_msg_at = excluded.last_eligible_msg_at""",
        (user_id, now_iso, now_iso),
    )
    conn.commit()
    conn.close()