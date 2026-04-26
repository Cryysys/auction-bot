import discord
import os
import sqlite3
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
import database

from src.AuctionBot import AuctionBot
from src.collectables_economy import (
    choose_collectable_with_wishlist_bias,
    choose_rarity,
    get_drop_config,
)

from src.commands.auctionCommands import bid
from src.commands.auctionCommands import endauction
from src.commands.auctionCommands import on_raw_reaction_add
from src.commands.auctionCommands import quickbid
from src.commands.auctionCommands import startauction
from src.commands.auctionCommands import status
from src.commands.auctionCommands import upcoming
from src.commands.auctionCommands import maxbid

from src.commands.mysteryCrateCommands import additem
from src.commands.mysteryCrateCommands import addpoints
from src.commands.mysteryCrateCommands import draw
from src.commands.mysteryCrateCommands import items
from src.commands.mysteryCrateCommands import points
from src.commands.mysteryCrateCommands import removeitem
from src.commands.mysteryCrateCommands import removepoints
from src.commands.mysteryCrateCommands import setdrawcost
from src.commands.mysteryCrateCommands import leaderboard
from src.commands.mysteryCrateCommands import inventory
from src.commands.mysteryCrateCommands import craft
from src.commands.mysteryCrateCommands import scrap
from src.commands.mysteryCrateCommands import wishlist
from src.commands.mysteryCrateCommands import showcase

# --- DATABASE UPGRADE LOGIC ---
def upgrade_database():
    db_path = "data.db" # Update this if your file name is different
    if not os.path.exists(db_path):
        print(f"⚠️ {db_path} not found. init_db will create it.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add cumulative_points column if it doesn't exist
        print("Checking for cumulative_points column...")
        cursor.execute("ALTER TABLE users ADD COLUMN cumulative_points INTEGER DEFAULT 0;")
        
        # Sync existing points to the new cumulative column
        print("Syncing historic points...")
        cursor.execute("UPDATE users SET cumulative_points = points;")
        
        conn.commit()
        print("✅ Database successfully upgraded with cumulative points!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ Database already has cumulative_points column.")
        else:
            print(f"❌ SQL Error during upgrade: {e}")
    except Exception as e:
        print(f"❌ Unexpected upgrade error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = AuctionBot(intents)

# ========== SLASH COMMANDS (AUCTIONS) ==========
startauction.register(bot)
bid.register(bot)
quickbid.register(bot)
status.register(bot)
endauction.register(bot)
on_raw_reaction_add.register(bot)
upcoming.register(bot)
maxbid.register(bot)

# ========== MYSTERY CRATE COMMANDS ==========
additem.register(bot)
removeitem.register(bot)
addpoints.register(bot)
removepoints.register(bot)
setdrawcost.register(bot)
items.register(bot)
points.register(bot)
draw.register(bot)
leaderboard.register(bot)
inventory.register(bot)
craft.register(bot)
scrap.register(bot)
wishlist.register(bot)
showcase.register(bot)

# ========== BOT START ==========
@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not message.guild:
        return
    if not message.content or message.content.startswith("/"):
        return

    config = get_drop_config()
    user_id = message.author.id
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    messages_since_drop, _, last_eligible = database.get_user_collectable_progress(user_id)
    if last_eligible:
        try:
            last_dt = datetime.fromisoformat(last_eligible)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed_seconds = (now - last_dt).total_seconds()
        except ValueError:
            elapsed_seconds = config["cooldown_seconds"]
        if elapsed_seconds < config["cooldown_seconds"]:
            return

    effective_chance = float(config["base_chance"]) + min(
        float(config["pity_step"]) * messages_since_drop,
        float(config["pity_cap"]),
    )

    if random.random() > effective_chance:
        database.update_collectable_progress_no_drop(
            user_id, messages_since_drop + 1, now_iso
        )
        return

    rarity = choose_rarity()
    if rarity is None:
        database.update_collectable_progress_no_drop(
            user_id, messages_since_drop + 1, now_iso
        )
        return

    collectable = choose_collectable_with_wishlist_bias(user_id, rarity, "natural")
    if collectable is None:
        database.update_collectable_progress_no_drop(
            user_id, messages_since_drop + 1, now_iso
        )
        return

    database.add_collectable_to_inventory(user_id, collectable[0], 1)
    database.reset_collectable_progress_after_drop(user_id, now_iso)

    try:
        await message.channel.send(
            f"✨ {message.author.mention} found **{collectable[1]}** (`{collectable[3]}`)!"
        )
    except Exception:
        # Ignore permission/channel-send errors to avoid breaking message flow.
        pass

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")

    if TOKEN is None:
        print("DISCORD_TOKEN is required in .env file")
        os._exit(1)

    # 1. Initialize the base database
    database.init_db()
    
    # 2. Upgrade the database structure for the leaderboard
    upgrade_database()
    
    # 3. Start the bot
    bot.run(TOKEN)