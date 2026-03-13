import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

class AuctionBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.auctions = {}
        self.notification_prefs = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f'Synced commands for {self.user}')

bot = AuctionBot()

# ----- Helper Functions -----
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
    currency = ''
    if original.startswith('€'):
        currency = '€'
    elif original.startswith('$'):
        currency = '$'
    amount_str = amount_str.replace('€', '').replace('$', '')
    multiplier = 1
    if amount_str.endswith('M') or amount_str.endswith('MIL') or amount_str.endswith('MILLION'):
        amount_str = re.sub(r'(M|MIL|MILLION)$', '', amount_str)
        multiplier = 1_000_000
    try:
        value = int(amount_str)
        return value * multiplier, currency
    except ValueError:
        return None, None

def format_number(num):
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B".rstrip('0').rstrip('.')
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M".rstrip('0').rstrip('.')
    elif num >= 1_000:
        return f"{num/1_000:.1f}K".rstrip('0').rstrip('.')
    else:
        return str(num)

def format_price(amount, currency):
    return f"{currency}{format_number(amount)}"

def plain_time(dt):
    return dt.strftime("%H:%M UTC")

def format_timestamp(dt, style="R"):
    return f"<t:{int(dt.timestamp())}:{style}>"

# ----- Auction Data Class -----
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
        self.loop_task = None
        self.last_bid_message = None

# ----- Background Auction Loop (with detailed logging) -----
async def auction_loop(channel_id):
    await bot.wait_until_ready()
    auction = bot.auctions.get(channel_id)
    if not auction:
        print(f"[LOOP] No auction found for {channel_id} at start")
        return

    print(f"[LOOP] Started for {channel_id} – ends at {auction.end_time} UTC")

    while True:
        if channel_id not in bot.auctions:
            print(f"[LOOP] Auction {channel_id} removed from bot.auctions, exiting")
            break

        now = datetime.now(timezone.utc)
        time_left = (auction.end_time - now).total_seconds()

        # In the last 10 seconds, print every second
        if time_left < 10:
            print(f"[LOOP] {channel_id}: time_left = {time_left:.2f}s")
        else:
            # Otherwise print every 10 seconds
            if int(time_left) % 10 == 0:
                print(f"[LOOP] {channel_id}: time_left = {time_left:.1f}s")

        if time_left <= 0:
            print(f"[LOOP] {channel_id}: time_left <= 0 – FINALIZING")
            await finalize_auction(channel_id)
            break

        # 1-hour reminder
        if not auction.reminder_1h_sent and time_left <= 3600 and time_left > 3540:
            try:
                await auction.seller.send(f"Your auction for **{auction.item_name}** ends in 1 hour!")
                auction.reminder_1h_sent = True
            except:
                pass

        # 5-minute reminder
        if not auction.reminder_5m_sent and time_left <= 300 and time_left > 240:
            if auction.bidders:
                mentions = ' '.join(f"<@{uid}>" for uid in auction.bidders)
                await auction.channel.send(f"⏰ **5 minutes left!** {mentions} final bids!")
            else:
                role = discord.utils.get(auction.channel.guild.roles, name="Auction Lover")
                if role:
                    await auction.channel.send(f"⏰ **5 minutes left!** {role.mention} no bids yet!")
                else:
                    await auction.channel.send(f"⏰ **5 minutes left!** No bids yet.")
            auction.reminder_5m_sent = True

        # Update original message every minute
        if int(time_left) % 60 == 0:
            try:
                embed = discord.Embed(
                    title="Auction Started!",
                    description=(
                        f"**Item:** {auction.item_name}\n"
                        f"**Seller:** {auction.seller.mention}\n"
                        f"**Starting Price:** {format_price(auction.start_price, auction.currency_symbol)}\n"
                        f"**Min Increment:** {format_price(auction.min_increment, auction.currency_symbol)}\n"
                        f"**Ends:** {format_timestamp(auction.end_time, 'R')}\n"
                        f"*(Updates every minute)*"
                    ),
                    color=discord.Color.green()
                )
                await auction.start_message.edit(embed=embed)
            except:
                pass

        # Sleep 1 second in the last 10 seconds, otherwise 10 seconds
        if time_left < 10:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(10)

# ----- Slash Commands -----
@bot.tree.command(name="startauction", description="Start a new auction. (Requires Cryysys role)")
@app_commands.describe(
    seller="The member who is selling the item.",
    duration="Auction duration, e.g. 1h30m (max 48h).",
    item="Name of the item being sold.",
    start_price="Starting price (e.g. 100, €50, 10M).",
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
        await interaction.response.send_message("Invalid price or increment format. Use numbers, optionally with €/$ or M/mil suffix.", ephemeral=True)
        return

    end_time = datetime.now(timezone.utc) + delta

    embed = discord.Embed(
        title="Auction Started!",
        description=(
            f"**Item:** {item}\n"
            f"**Seller:** {seller.mention}\n"
            f"**Starting Price:** {format_price(start_val, currency)}\n"
            f"**Min Increment:** {format_price(min_inc_val, currency)}\n"
            f"**Ends:** {format_timestamp(end_time, 'R')}\n"
            f"*(Updates every minute)*"
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

    auction.loop_task = bot.loop.create_task(auction_loop(interaction.channel_id))

@bot.tree.command(name="bid", description="Place a bid on the current auction.")
@app_commands.describe(amount="Your bid amount (e.g. 150, €200, 5M).")
async def bid(interaction: discord.Interaction, amount: str):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message("No auction is running in this channel.", ephemeral=True)
        return

    bid_val, _ = parse_amount(amount)
    if bid_val is None:
        await interaction.response.send_message("Invalid bid format. Use numbers, optionally with €/$ or M/mil suffix.", ephemeral=True)
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

        embed = discord.Embed(
            title="Auction Started!",
            description=(
                f"**Item:** {auction.item_name}\n"
                f"**Seller:** {auction.seller.mention}\n"
                f"**Starting Price:** {format_price(auction.start_price, auction.currency_symbol)}\n"
                f"**Min Increment:** {format_price(auction.min_increment, auction.currency_symbol)}\n"
                f"**Ends:** {format_timestamp(auction.end_time, 'R')}\n"
                f"*(Updates every minute)*"
            ),
            color=discord.Color.green()
        )
        await auction.start_message.edit(embed=embed)

        extend_msg = "⏰ **Anti‑sniping activated!** Auction extended by 1 minute." if extended else ""
        embed_bid = discord.Embed(
            title="New Bid!",
            description=(
                f"**Bidder:** {interaction.user.mention}\n"
                f"**New Price:** {format_price(bid_val, auction.currency_symbol)}\n"
                f"{extend_msg}\n\n"
                f"🔔 Click the bell on this message to get notified if you're outbid!\n"
                f"**Auction ends at:** {plain_time(auction.end_time)}"
            ),
            color=discord.Color.blue()
        )
        bid_message = await interaction.followup.send(embed=embed_bid)

        await bid_message.add_reaction("🔔")
        auction.last_bid_message = bid_message

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
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message("No auction running in this channel.", ephemeral=True)
        return

    if interaction.user != auction.seller and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only the seller or an admin can force-end the auction.", ephemeral=True)
        return

    await finalize_auction(interaction.channel_id, forced=True)
    await interaction.response.send_message("Auction ended by moderator/seller.")

# ----- Reaction Handler -----
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
        message = await channel.fetch_message(payload.message_id)
        if not current:
            await message.channel.send(f"<@{payload.user_id}> will now be DM'd if outbid!", delete_after=5)
        else:
            await message.channel.send(f"<@{payload.user_id}> will no longer receive outbid notifications.", delete_after=5)

# ----- Finalize Auction -----
async def finalize_auction(channel_id, forced=False):
    auction = bot.auctions.pop(channel_id, None)
    if not auction:
        print(f"[FINALIZE] Called but no auction found for {channel_id}")
        return

    print(f"[FINALIZE] Auction ended in {channel_id} - Item: {auction.item_name}")

    keys_to_remove = [k for k in bot.notification_prefs.keys() if k[0] == channel_id]
    for key in keys_to_remove:
        del bot.notification_prefs[key]

    if auction.loop_task and not auction.loop_task.done():
        auction.loop_task.cancel()

    channel = auction.channel
    winner = auction.highest_bidder
    price = auction.current_price

    # Channel message
    try:
        if winner:
            embed = discord.Embed(
                title="Auction Ended!",
                description=(
                    f"**Item:** {auction.item_name}\n"
                    f"**Winner:** {winner.mention}\n"
                    f"**Final Price:** {format_price(price, auction.currency_symbol)}"
                ),
                color=discord.Color.gold()
            )
            await channel.send(embed=embed)
            print(f"[FINALIZE] Channel embed sent for winner {winner}")
        else:
            await channel.send(f"Auction for **{auction.item_name}** ended with no bids.")
            print("[FINALIZE] Channel message sent (no bids)")
    except Exception as e:
        print(f"[FINALIZE] Failed to send channel message: {e}")
        try:
            if winner:
                await channel.send(f"**Auction Ended!**\nItem: {auction.item_name}\nWinner: {winner.mention}\nFinal Price: {format_price(price, auction.currency_symbol)}")
            else:
                await channel.send(f"Auction for **{auction.item_name}** ended with no bids.")
        except Exception as e2:
            print(f"[FINALIZE] Fallback channel message also failed: {e2}")

    # DM seller
    try:
        if winner:
            await auction.seller.send(
                f"Your auction for **{auction.item_name}** ended.\n"
                f"Winner: {winner} with {format_price(price, auction.currency_symbol)}."
            )
            print(f"[FINALIZE] DM sent to seller {auction.seller}")
        else:
            await auction.seller.send(f"Your auction for **{auction.item_name}** ended with no bids.")
            print("[FINALIZE] DM sent to seller (no bids)")
    except Exception as e:
        print(f"[FINALIZE] Failed to DM seller: {e}")

# ----- Run Bot -----
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

if __name__ == "__main__":
    bot.run(TOKEN)