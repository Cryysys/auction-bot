import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import database
import traceback # Add this at the top of main.py

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

async def auction_end_timer(auction):
    """Wait until the end time and finalize."""
    try:
        now = datetime.now(timezone.utc)
        wait_seconds = (auction.end_time - now).total_seconds()
        
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
            
        # Check if the auction was already ended or replaced
        if auction.channel.id in bot.auctions:
            # IMPORTANT: Pass the auction OBJECT, not just the ID
            await finalize_auction(auction) 
    except Exception as e:
        print(f"!!! CRITICAL ERROR IN TIMER for {auction.item_name} !!!")
        traceback.print_exc()

class AuctionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.auctions = {}
        self.notification_prefs = {}
        self.active_views = []

    async def setup_hook(self):
        await self.tree.sync()
        print(f'Synced commands for {self.user}')

bot = AuctionBot()

# ========== HELPER FUNCTIONS ==========

def parse_duration(duration_str):
    pattern = re.compile(r'((?P<hours>\d+)h)?((?P<minutes>\d+)m)?')
    match = pattern.fullmatch(duration_str)
    if not match:
        return None
    hours = int(match.group('hours')) if match.group('hours') else 0
    minutes = int(match.group('minutes')) if match.group('minutes') else 0
    if hours == 0 and minutes == 0:
        return None
    return timedelta(hours=hours, minutes=minutes)

def parse_amount(amount_str):
    original = amount_str.strip()
    amount_str = original.upper()
    multiplier = 1
    if amount_str.endswith('B'):
        amount_str = amount_str[:-1]
        multiplier = 1_000_000_000
    elif amount_str.endswith('M') or amount_str.endswith('MIL') or amount_str.endswith('MILLION'):
        amount_str = re.sub(r'(M|MIL|MILLION)$', '', amount_str)
        multiplier = 1_000_000
    try:
        value = float(amount_str)
        return int(value * multiplier), ''
    except ValueError:
        return None, None

def format_number(num):
    if num >= 1_000_000_000:
        val = num / 1_000_000_000
        formatted = f"{val:.3f}".rstrip('0').rstrip('.')
        return f"{formatted}B"
    elif num >= 1_000_000:
        val = num / 1_000_000
        formatted = f"{val:.2f}".rstrip('0').rstrip('.')
        return f"{formatted}M"
    elif num >= 1_000:
        val = num / 1_000
        formatted = f"{val:.1f}".rstrip('0').rstrip('.')
        return f"{formatted}K"
    else:
        return str(num)

def format_price(amount, currency):
    return f"{format_number(amount)}"

def plain_time(dt):
    return dt.strftime("%H:%M UTC")

def format_timestamp(dt, style="f"):
    return f"<t:{int(dt.timestamp())}:{style}>"

# ========== AUCTION DATA CLASS ==========

class Auction:
    def __init__(self, channel, seller, item_name, start_price, min_increment, end_time, start_message, currency_symbol):
        self.channel = channel
        self.seller = seller
        self.item_name = item_name
        self.start_price = start_price
        self.min_increment = min_increment
        self.current_price = start_price
        self.end_time = end_time
        self.highest_bidder = None
        self.bidders = set()
        self.start_message = start_message
        self.currency_symbol = currency_symbol
        self.reminder_1h_sent = False
        self.reminder_5m_sent = False
        self.end_task = None
        self.reminder_task = None
        self.last_bid_message = None

# ========== AUCTION TIMER TASKS ==========

async def auction_end_timer(auction):
    """Wait until the end time and finalize."""
    try:
        # We loop and check every 5 seconds so we can react to extensions
        while auction.channel.id in bot.auctions:
            now = datetime.now(timezone.utc)
            wait_seconds = (auction.end_time - now).total_seconds()
            
            if wait_seconds <= 0:
                # Time is up!
                await finalize_auction(auction) # Use the object-based fix from before
                break
            
            # Sleep in small increments so we stay responsive to bids
            await asyncio.sleep(min(wait_seconds, 5)) 
    except asyncio.CancelledError:
        pass

async def auction_reminders(auction):
    """Accurately send 1-hour and 5-minute reminders by checking every 30s."""
    try:
        while auction.channel.id in bot.auctions:
            now = datetime.now(timezone.utc)
            remaining = (auction.end_time - now).total_seconds()

            # 1-hour reminder (3600 seconds)
            if 3540 <= remaining <= 3600 and not auction.reminder_1h_sent:
                await send_reminder_msg(auction, "1 hour")
                auction.reminder_1h_sent = True

            # 5-minute reminder (300 seconds)
            if 270 <= remaining <= 300 and not auction.reminder_5m_sent:
                await send_reminder_msg(auction, "5 minutes")
                auction.reminder_5m_sent = True
            
            # CRITICAL FIX: If a bid extends the auction, reset the sent flags 
            # so the reminder can fire again at the NEW correct time
            if remaining > 3610:
                auction.reminder_1h_sent = False
            if remaining > 310:
                auction.reminder_5m_sent = False

            if remaining <= 0:
                break
                
            await asyncio.sleep(30) # Check the clock every 30 seconds
    except asyncio.CancelledError:
        pass

async def send_reminder_msg(auction, time_label):
    """Helper to handle the logic of who to ping."""
    if auction.bidders:
        mentions = ' '.join(f"<@{uid}>" for uid in auction.bidders)
        await auction.channel.send(f"⏰ **{time_label} left!** {mentions} final bids!")
    else:
        role = discord.utils.get(auction.channel.guild.roles, name="Auction Lover")
        mention = role.mention if role else "No bids yet."
        await auction.channel.send(f"⏰ **{time_label} left!** {mention}")


# ========== SLASH COMMANDS (AUCTIONS) ==========

@bot.tree.command(name="startauction", description="Start a new auction. (Requires Cryysys role)")
@app_commands.describe(
    seller="The member who is selling the item.",
    duration="Auction duration, e.g. 1h30m (max 48h).",
    item="Name of the item being sold.",
    start_price="Starting price (e.g. 100, 10M, 1.5B).",
    min_increment="Minimum bid increment (e.g. 10, 5M)."
)
async def startauction(
    interaction: discord.Interaction,
    seller: discord.Member,
    duration: str,
    item: str,
    start_price: str,
    min_increment: str
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to start an auction.", ephemeral=True)
        return

    if interaction.channel_id in bot.auctions:
        await interaction.response.send_message("An auction is already running in this channel!", ephemeral=True)
        return

    # Check bot permissions
    perms = interaction.channel.permissions_for(interaction.guild.me)
    if not perms.send_messages:
        await interaction.response.send_message("I need `Send Messages` permission in this channel.", ephemeral=True)
        return

    delta = parse_duration(duration)
    if delta is None:
        await interaction.response.send_message("Invalid duration format. Use e.g. `1h30m` or `30m`. Max 48 hours.", ephemeral=True)
        return
    if delta > timedelta(hours=48):
        await interaction.response.send_message("Duration cannot exceed 48 hours.", ephemeral=True)
        return

    start_val, currency = parse_amount(start_price)
    min_inc_val, _ = parse_amount(min_increment)
    if start_val is None or min_inc_val is None:
        await interaction.response.send_message("Invalid price or increment format. Use numbers, optionally with M or B suffix.", ephemeral=True)
        return

    end_time = datetime.now(timezone.utc) + delta

    embed = discord.Embed(
        title="Auction Started!",
        description=(
            f"**Item:** {item}\n"
            f"**Seller:** {seller.mention}\n"
            f"**Starting Price:** {format_price(start_val, currency)}\n"
            f"**Min Increment:** {format_price(min_inc_val, currency)}\n"
            f"**Ends:** {format_timestamp(end_time, 'R')}"
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)
    start_message = await interaction.original_response()

    auction = Auction(
        channel=interaction.channel,
        seller=seller,
        item_name=item,
        start_price=start_val,
        min_increment=min_inc_val,
        end_time=end_time,
        start_message=start_message,
        currency_symbol=currency
    )
    bot.auctions[interaction.channel_id] = auction

    auction.end_task = asyncio.create_task(auction_end_timer(auction))
    auction.reminder_task = asyncio.create_task(auction_reminders(auction))

@bot.tree.command(name="bid", description="Place a bid on the current auction.")
@app_commands.describe(amount="Your bid amount (e.g. 150, 5M, 1.2B).")
async def bid(interaction: discord.Interaction, amount: str):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message("No auction is running in this channel.", ephemeral=True)
        return

    bid_val, _ = parse_amount(amount)
    if bid_val is None:
        await interaction.response.send_message("Invalid bid format. Use numbers, optionally with M or B suffix.", ephemeral=True)
        return

    if datetime.now(timezone.utc) >= auction.end_time:
        await interaction.response.send_message("This auction has already ended.", ephemeral=True)
        return

    if bid_val < auction.current_price + auction.min_increment:
        await interaction.response.send_message(
            f"Bid must be at least **{format_price(auction.current_price + auction.min_increment, auction.currency_symbol)}** (current price + min increment).",
            ephemeral=True
        )
        return

    old_highest = auction.highest_bidder
    await interaction.response.defer()

    try:
        auction.current_price = bid_val
        auction.highest_bidder = interaction.user
        auction.bidders.add(interaction.user.id)

        now = datetime.now(timezone.utc)
        time_left = (auction.end_time - now).total_seconds()
        extended = False
        if time_left <= 120:
            auction.end_time += timedelta(minutes=1)
            extended = True
            # Cancel old end task and start new one
            if auction.end_task and not auction.end_task.done():
                auction.end_task.cancel()
            auction.end_task = asyncio.create_task(auction_end_timer(auction))

        extend_msg = "⏰ **Anti‑sniping activated!** Auction extended by 1 minute." if extended else ""
        embed_bid = discord.Embed(
            title="New Bid!",
            description=(
                f"**Item:** {auction.item_name}\n"
                f"**Bidder:** {interaction.user.mention}\n"
                f"**New Price:** {format_price(bid_val, auction.currency_symbol)}\n"
                f"{extend_msg}\n\n"
                f"🔔 Click the bell on this message to get notified if you're outbid!\n"
                f"**Auction ends at:** {plain_time(auction.end_time)}"
            ),
            color=discord.Color.blue()
        )
        bid_message = await interaction.followup.send(embed=embed_bid)

        # Try to add reaction; if fails, ignore
        try:
            await bid_message.add_reaction("🔔")
            auction.last_bid_message = bid_message
        except discord.Forbidden:
            print(f"Could not add reaction to bid message in {interaction.channel.name}")
            auction.last_bid_message = None

        if old_highest and old_highest != interaction.user:
            pref_key = (interaction.channel_id, old_highest.id)
            if bot.notification_prefs.get(pref_key, False):
                try:
                    channel_link = auction.channel.mention
                    await old_highest.send(
                        f"You've been outbid in the auction for **{auction.item_name}** in {channel_link}!\n"
                        f"New highest bid: {format_price(bid_val, auction.currency_symbol)} by {interaction.user.name}"
                    )
                except:
                    pass

    except Exception as e:
        print(f"Error in bid command: {e}")
        import traceback
        traceback.print_exc()
        await interaction.followup.send("An error occurred while processing your bid. Please try again.", ephemeral=True)

@bot.tree.command(name="quickbid", description="Bid the minimum increment automatically.")
async def quickbid(interaction: discord.Interaction):
    auction = bot.auctions.get(interaction.channel_id)
    
    if not auction:
        await interaction.response.send_message("No active auction in this channel.", ephemeral=True)
        return

    if interaction.user == auction.seller:
        await interaction.response.send_message("You cannot bid on your own auction.", ephemeral=True)
        return

    # Calculate the next bid
    new_price = auction.current_price + auction.min_increment
    
    # Update auction state
    auction.current_price = new_price
    auction.highest_bidder = interaction.user
    auction.bidders.add(interaction.user.id)

    # Anti-sniping: If bid is in last 2 minutes, extend by 1 minute
    now = datetime.now(timezone.utc)
    time_left = (auction.end_time - now).total_seconds()
    extended = False
    if time_left <= 120:
        auction.end_time += timedelta(minutes=1)
        extended = True
        # Restart the end timer for the new time
        if auction.end_task:
            auction.end_task.cancel()
        auction.end_task = asyncio.create_task(auction_end_timer(auction))

    # Response
    ext_msg = " **Auction extended by 1m!**" if extended else ""
    await interaction.response.send_message(
        f"Quick bid accepted! **{interaction.user.display_name}** is now leading with "
        f"**{format_price(new_price, auction.currency_symbol)}**.{ext_msg}"
    )

    # Alert other bidders
    for uid in auction.bidders:
        if uid != interaction.user.id and (interaction.channel_id, uid) in bot.notification_prefs:
            try:
                user = await bot.fetch_user(uid)
                await user.send(f"You've been outbid for **{auction.item_name}**! New price: {format_price(new_price, auction.currency_symbol)}")
            except:
                pass

@bot.tree.command(name="status", description="Show current auction status.")
async def status(interaction: discord.Interaction):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message("No auction running in this channel.", ephemeral=True)
        return

    highest = auction.highest_bidder.mention if auction.highest_bidder else "None"
    embed = discord.Embed(
        title=f"Auction: {auction.item_name}",
        description=(
            f"**Current Price:** {format_price(auction.current_price, auction.currency_symbol)}\n"
            f"**Highest Bidder:** {highest}\n"
            f"**Ends:** {format_timestamp(auction.end_time, 'R')}"
        ),
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="endauction", description="Force-end the current auction (seller only).")
async def endauction(interaction: discord.Interaction):
    # Retrieve the auction object for this channel
    auction = bot.auctions.get(interaction.channel_id)
    
    if not auction:
        await interaction.response.send_message("No auction running in this channel.", ephemeral=True)
        return

    # Check if the user is the seller or an admin
    if interaction.user != auction.seller and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only the seller or an admin can force-end the auction.", ephemeral=True)
        return

    # Cancel background tasks immediately to prevent duplicate "End" triggers
    if auction.end_task and not auction.end_task.done():
        auction.end_task.cancel()
    if auction.reminder_task and not auction.reminder_task.done():
        auction.reminder_task.cancel()

    # We pass the WHOLE auction object, ensuring we have the direct channel reference
    await finalize_auction(auction, forced=True)
    
    # Simple confirmation for the user who ran the command
    await interaction.response.send_message("Auction ended by moderator/seller.")

# ========== REACTION HANDLER ==========

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != "🔔":
        return

    auction = bot.auctions.get(payload.channel_id)
    if not auction:
        return
    if not auction.last_bid_message or auction.last_bid_message.id != payload.message_id:
        return

    pref_key = (payload.channel_id, payload.user_id)
    current = bot.notification_prefs.get(pref_key, False)
    bot.notification_prefs[pref_key] = not current

    channel = bot.get_channel(payload.channel_id)
    if channel:
        try:
            message = await channel.fetch_message(payload.message_id)
            if not current:
                await message.channel.send(f"<@{payload.user_id}> will now be DM'd if outbid!", delete_after=5)
            else:
                await message.channel.send(f"<@{payload.user_id}> will no longer receive outbid notifications.", delete_after=5)
        except:
            pass

# ========== FINALIZE AUCTION ==========

async def finalize_auction(auction_or_id, forced=False):
    """
    Finalizes the auction. 
    Accepts either an Auction object (preferred) or a channel ID (for fallback).
    """
    # 1. Determine if we were given an object or an ID
    if isinstance(auction_or_id, int):
        auction = bot.auctions.pop(auction_or_id, None)
    else:
        auction = auction_or_id
        # Remove it from the dictionary so no more bids can be placed
        bot.auctions.pop(auction.channel.id, None)

    if not auction:
        return

    # 2. Use the direct references saved in the Auction object
    channel = auction.channel 
    seller = auction.seller
    winner = auction.highest_bidder
    price = auction.current_price

    # 3. Prepare the announcement message
    if winner:
        message = (
            f"🎊 **Auction ended for {auction.item_name}** 🎊\n"
            f"**Seller:** {seller.mention}\n"
            f"**Winner:** {winner.mention}\n"
            f"**Final amount:** {format_price(price, auction.currency_symbol)}"
        )
    else:
        message = f"Auction for **{auction.item_name}** ended with no bids."

    # 4. Send to the channel (using the reliable direct reference)
    try:
        await channel.send(message)
    except Exception as e:
        print(f"[ERROR] Could not send end message to channel {channel.id}: {e}")

    # 5. DM the Seller
    try:
        if winner:
            await seller.send(
                f"Your auction for **{auction.item_name}** ended.\n"
                f"Winner: {winner} with {format_price(price, auction.currency_symbol)}."
            )
        else:
            await seller.send(f"Your auction for **{auction.item_name}** ended with no bids.")
    except Exception as e:
        print(f"[ERROR] Could not DM seller {seller.id}: {e}")

# ========== MYSTERY CRATE DROPDOWN VIEW ==========

class ItemDropdownView(View):
    def __init__(self, items, user_id):
        super().__init__(timeout=60)
        self.items = items
        self.user_id = user_id
        self.message = None

        options = []
        for i, (item_id, name, url) in enumerate(items[:25]):
            options.append(discord.SelectOption(
                label=f"{name[:50]}",
                value=str(i),
                description=f"Item #{item_id}"
            ))

        self.select = discord.ui.Select(
            placeholder="Select an item to view...",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        bot.active_views.append(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu.", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(self.select.values[0])
        item_id, name, url = self.items[idx]

        embed = discord.Embed(
            title=name,
            color=discord.Color.blue()
        )
        if url:
            embed.set_image(url=url)
        embed.set_footer(text=f"Item {idx+1} of {len(self.items)}")

        await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)
        if self in bot.active_views:
            bot.active_views.remove(self)

# ========== MYSTERY CRATE COMMANDS ==========

@bot.tree.command(name="additem", description="Add an item to the mystery crate pool")
@app_commands.describe(
    name="Item name",
    image="Upload an image (optional)",
    image_url="Or provide an image URL (optional)"
)
async def additem(
    interaction: discord.Interaction,
    name: str,
    image: discord.Attachment = None,
    image_url: str = None
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to add items.", ephemeral=True)
        return

    if image and image_url:
        await interaction.response.send_message("Please provide either an uploaded image or a URL, not both.", ephemeral=True)
        return

    if not image and not image_url:
        await interaction.response.send_message("You must provide either an image upload or an image URL.", ephemeral=True)
        return

    final_url = image.url if image else image_url
    item_id = database.add_item(name, final_url)
    await interaction.response.send_message(f"✅ Item added with ID #{item_id}: {name}")

@bot.tree.command(name="removeitem", description="Remove an item from the pool by ID")
@app_commands.describe(item_id="The ID of the item to remove")
async def removeitem(interaction: discord.Interaction, item_id: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to remove items.", ephemeral=True)
        return
    if database.remove_item(item_id):
        await interaction.response.send_message(f"✅ Item #{item_id} removed.")
    else:
        await interaction.response.send_message(f"❌ Item #{item_id} not found.", ephemeral=True)

@bot.tree.command(name="addpoints", description="Add points to a user")
@app_commands.describe(user="The user to reward", amount="Number of points")
async def addpoints(interaction: discord.Interaction, user: discord.Member, amount: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to add points.", ephemeral=True)
        return
    database.add_points(user.id, amount)
    await interaction.response.send_message(f"✅ Added {amount} points to {user.mention}.")

@bot.tree.command(name="removepoints", description="Remove points from a user")
@app_commands.describe(user="The user", amount="Number of points")
async def removepoints(interaction: discord.Interaction, user: discord.Member, amount: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to remove points.", ephemeral=True)
        return
    if database.remove_points(user.id, amount):
        await interaction.response.send_message(f"✅ Removed {amount} points from {user.mention}.")
    else:
        await interaction.response.send_message(f"❌ {user.mention} doesn't have enough points.", ephemeral=True)

@bot.tree.command(name="setdrawcost", description="Set the points required per draw")
@app_commands.describe(amount="Points per draw")
async def setdrawcost(interaction: discord.Interaction, amount: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message("You need the **Cryysys** role to set draw cost.", ephemeral=True)
        return
    database.set_setting("draw_cost", str(amount))
    await interaction.response.send_message(f"✅ Draw cost set to {amount} points.")

@bot.tree.command(name="items", description="Browse all items in the mystery crate pool")
async def items(interaction: discord.Interaction):
    items = database.get_all_items()
    if not items:
        await interaction.response.send_message("The pool is empty.")
        return

    if len(items) > 25:
        await interaction.response.send_message(
            f"Too many items ({len(items)}). Max 25. Contact an admin to reduce the pool.",
            ephemeral=True
        )
        return

    view = ItemDropdownView(items, interaction.user.id)

    item_id, name, url = items[0]
    embed = discord.Embed(
        title=name,
        color=discord.Color.blue()
    )
    if url:
        embed.set_image(url=url)
    embed.set_footer(text=f"Item 1 of {len(items)} (use dropdown to change)")

    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

@bot.tree.command(name="points", description="Check your current points")
async def points(interaction: discord.Interaction):
    pts = database.get_points(interaction.user.id)
    await interaction.response.send_message(f"You have **{pts}** points.", ephemeral=True)

@bot.tree.command(name="draw", description="Draw a random item from the pool (costs points)")
async def draw(interaction: discord.Interaction):
    if interaction.channel.name != "mystery-crates":
        await interaction.response.send_message("You can only use `/draw` in #mystery-crates.", ephemeral=True)
        return

    cost = int(database.get_setting("draw_cost", "10"))
    user_id = interaction.user.id
    pts = database.get_points(user_id)

    if pts < cost:
        await interaction.response.send_message(f"You need {cost} points to draw. You have {pts}.", ephemeral=True)
        return

    item = database.draw_random_item()
    if not item:
        await interaction.response.send_message("The pool is empty. Ask an admin to add items!", ephemeral=True)
        return

    database.remove_points(user_id, cost)
    database.record_draw(user_id, item[0])

    embed = discord.Embed(
        title="🎁 Mystery Box",
        description=f"You open the mystery box and get... **{item[1]}**!",
        color=discord.Color.green()
    )
    if item[2]:
        embed.set_image(url=item[2])
    await interaction.response.send_message(embed=embed)

# ========== BOT START ==========

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    database.init_db()
    print("Database initialized.")

if __name__ == "__main__":
    bot.run(TOKEN)
