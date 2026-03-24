import discord
from discord import app_commands
import asyncio
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import database


from src.Auction import Auction
from src.AuctionBot import AuctionBot
from src.ItemDropdownView import ItemDropdownView
from src.auctionFunctions.finalize_auction import finalize_auction
from src.auctionFunctions.auction_end_timer import auction_end_timer
from src.helperFunctions.formatting_helpers import (
    format_price,
    format_timestamp,
    plain_time,
)
from src.helperFunctions.parse_amount import parse_amount
from src.helperFunctions.parse_duration import parse_duration

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = AuctionBot(intents)


# ========== SLASH COMMANDS (AUCTIONS) ==========


@bot.tree.command(
    name="startauction", description="Start a new auction. (Requires Cryysys role)"
)
@app_commands.describe(
    seller="The member who is selling the item.",
    duration="Auction duration, e.g. 1h30m (max 48h).",
    item="Name of the item being sold.",
    start_price="Starting price (e.g. 100, 10M, 1.5B).",
    min_increment="Minimum bid increment (e.g. 10, 5M).",
    image_url="Direct link to an image or GIF of the item (optional).",  # <-- Added this
)
async def startauction(
    interaction: discord.Interaction,
    seller: discord.Member,
    duration: str,
    item: str,
    start_price: str,
    min_increment: str,
    image_url: str = None,  # <-- Added this
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to start an auction.", ephemeral=True
        )
        return

    if interaction.channel_id in bot.auctions:
        await interaction.response.send_message(
            "An auction is already running in this channel!", ephemeral=True
        )
        return

    # Check bot permissions
    perms = interaction.channel.permissions_for(interaction.guild.me)
    if not perms.send_messages:
        await interaction.response.send_message(
            "I need `Send Messages` permission in this channel.", ephemeral=True
        )
        return

    delta = parse_duration(duration)
    if delta is None:
        await interaction.response.send_message(
            "Invalid duration format. Use e.g. `1h30m` or `30m`. Max 48 hours.",
            ephemeral=True,
        )
        return
    if delta > timedelta(hours=48):
        await interaction.response.send_message(
            "Duration cannot exceed 48 hours.", ephemeral=True
        )
        return

    start_val, currency = parse_amount(start_price)
    min_inc_val, _ = parse_amount(min_increment)
    if start_val is None or min_inc_val is None:
        await interaction.response.send_message(
            "Invalid price or increment format. Use numbers, optionally with M or B suffix.",
            ephemeral=True,
        )
        return

    end_time = datetime.now(timezone.utc) + delta

    # --- NEW EMBED LAYOUT WITH THUMBNAIL ---
    embed = discord.Embed(
        title=f"🎨 Auction Started: {item}",
        description=(
            f"**Seller:** {seller.mention}\n"
            f"**Ends:** {format_timestamp(end_time, 'R')}"
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="Current Bid", value=format_price(start_val, currency), inline=True
    )
    embed.add_field(
        name="Min Increment", value=format_price(min_inc_val, currency), inline=True
    )
    embed.add_field(name="Highest Bidder", value="No bids yet", inline=False)

    # Set the small image in the top right corner if a link was provided
    if image_url:
        embed.set_thumbnail(url=image_url)

    await interaction.response.send_message(embed=embed)
    start_message = await interaction.original_response()

    # --- CREATE AUCTION OBJECT ---
    auction = Auction(
        channel=interaction.channel,
        seller=seller,
        item_name=item,
        start_price=start_val,
        min_increment=min_inc_val,
        end_time=end_time,
        start_message=start_message,
        currency_symbol=currency,
    )

    # Store the tracking variables we added to your Auction class
    auction.message = start_message
    auction.image_url = image_url

    bot.auctions[interaction.channel_id] = auction

    auction.end_task = asyncio.create_task(auction_end_timer(bot, auction))
    auction.reminder_task = asyncio.create_task(auction_reminders(auction))


@bot.tree.command(name="bid", description="Place a bid on the current auction.")
@app_commands.describe(amount="Your bid amount (e.g. 150, 5M, 1.2B).")
async def bid(interaction: discord.Interaction, amount: str):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message(
            "No auction is running in this channel.", ephemeral=True
        )
        return

    if interaction.user == auction.seller:
        await interaction.response.send_message(
            "You cannot bid on your own auction.", ephemeral=True
        )
        return

    bid_val, _ = parse_amount(amount)
    if bid_val is None:
        await interaction.response.send_message("Invalid bid format.", ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    if now >= auction.end_time:
        await interaction.response.send_message(
            "This auction has already ended.", ephemeral=True
        )
        return

    if bid_val < auction.current_price + auction.min_increment:
        await interaction.response.send_message(
            f"Bid must be at least **{format_price(auction.current_price + auction.min_increment, auction.currency_symbol)}**.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    old_highest = auction.highest_bidder

    try:
        # 1. Update State
        auction.current_price = bid_val
        auction.highest_bidder = interaction.user
        auction.bidders.add(interaction.user.id)

        # 2. Anti-Sniping
        time_left = (auction.end_time - now).total_seconds()
        extended = False
        if time_left <= 120:
            auction.end_time += timedelta(minutes=1)
            extended = True

        # 3. Update the "Master Message" (The very first message)
        master_embed = discord.Embed(
            title=f"🎨 Auction: {auction.item_name}",
            description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
            color=discord.Color.blue(),
        )
        master_embed.add_field(
            name="Current Bid",
            value=format_price(auction.current_price, auction.currency_symbol),
            inline=True,
        )
        master_embed.add_field(
            name="Min Increment",
            value=format_price(auction.min_increment, auction.currency_symbol),
            inline=True,
        )
        master_embed.add_field(
            name="Highest Bidder", value=auction.highest_bidder.mention, inline=False
        )
        if auction.image_url:
            master_embed.set_thumbnail(url=auction.image_url)

        if auction.message:
            try:
                await auction.message.edit(embed=master_embed)
            except:
                pass

        # 4. Create the "New Bid" Embed (The one that goes in the chat now)
        extend_msg = (
            "\n⏰ **Anti‑sniping activated!** Auction extended by 1 minute."
            if extended
            else ""
        )

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
            color=discord.Color.blue(),
        )
        if auction.image_url:
            embed_bid.set_thumbnail(url=auction.image_url)

        bid_message = await interaction.followup.send(embed=embed_bid)

        # 5. Add Notification Reaction
        try:
            await bid_message.add_reaction("🔔")
            auction.last_bid_message = bid_message
        except:
            auction.last_bid_message = None

        # 6. Outbid Notification
        if old_highest and old_highest != interaction.user:
            pref_key = (interaction.channel_id, old_highest.id)
            if bot.notification_prefs.get(pref_key, False):
                try:
                    await old_highest.send(
                        f"You've been outbid for **{auction.item_name}**! New price: {format_price(bid_val, auction.currency_symbol)}"
                    )
                except:
                    pass

    except Exception as e:
        print(f"Error in bid: {e}")


@bot.tree.command(
    name="quickbid", description="Bid the minimum increment automatically."
)
async def quickbid(interaction: discord.Interaction):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message(
            "No active auction here.", ephemeral=True
        )
        return

    if interaction.user == auction.seller:
        await interaction.response.send_message(
            "You cannot bid on your own auction.", ephemeral=True
        )
        return

    now = datetime.now(timezone.utc)
    if now >= auction.end_time:
        await interaction.response.send_message(
            "This auction has already ended.", ephemeral=True
        )
        return

    await interaction.response.defer()
    old_highest = auction.highest_bidder

    try:
        new_price = auction.current_price + auction.min_increment
        auction.current_price = new_price
        auction.highest_bidder = interaction.user
        auction.bidders.add(interaction.user.id)

        time_left = (auction.end_time - now).total_seconds()
        extended = False
        if time_left <= 120:
            auction.end_time += timedelta(minutes=1)
            extended = True

        # Update Master Message
        master_embed = discord.Embed(
            title=f"🎨 Auction: {auction.item_name}",
            description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
            color=discord.Color.blue(),
        )
        master_embed.add_field(
            name="Current Bid",
            value=format_price(new_price, auction.currency_symbol),
            inline=True,
        )
        master_embed.add_field(
            name="Min Increment",
            value=format_price(auction.min_increment, auction.currency_symbol),
            inline=True,
        )
        master_embed.add_field(
            name="Highest Bidder", value=auction.highest_bidder.mention, inline=False
        )
        if auction.image_url:
            master_embed.set_thumbnail(url=auction.image_url)

        if auction.message:
            try:
                await auction.message.edit(embed=master_embed)
            except:
                pass

        # Create Quick Bid Embed (Matching the /bid style)
        extend_msg = (
            "\n⏰ **Anti‑sniping activated!** Auction extended by 1 minute."
            if extended
            else ""
        )

        embed_bid = discord.Embed(
            title="New Quick Bid!",
            description=(
                f"**Item:** {auction.item_name}\n"
                f"**Bidder:** {interaction.user.mention}\n"
                f"**New Price:** {format_price(new_price, auction.currency_symbol)}\n"
                f"{extend_msg}\n\n"
                f"🔔 Click the bell on this message to get notified if you're outbid!\n"
                f"**Auction ends at:** {plain_time(auction.end_time)}"
            ),
            color=discord.Color.blue(),
        )
        if auction.image_url:
            embed_bid.set_thumbnail(url=auction.image_url)

        bid_message = await interaction.followup.send(embed=embed_bid)

        try:
            await bid_message.add_reaction("🔔")
            auction.last_bid_message = bid_message
        except:
            auction.last_bid_message = None

        if old_highest and old_highest != interaction.user:
            pref_key = (interaction.channel_id, old_highest.id)
            if bot.notification_prefs.get(pref_key, False):
                try:
                    await old_highest.send(
                        f"You've been outbid for **{auction.item_name}**! New price: {format_price(new_price, auction.currency_symbol)}"
                    )
                except:
                    pass

    except Exception as e:
        print(f"Error in quickbid: {e}")


@bot.tree.command(name="status", description="Show current auction status.")
async def status(interaction: discord.Interaction):
    auction = bot.auctions.get(interaction.channel_id)
    if not auction:
        await interaction.response.send_message(
            "No auction running in this channel.", ephemeral=True
        )
        return

    highest = auction.highest_bidder.mention if auction.highest_bidder else "None"
    embed = discord.Embed(
        title=f"Auction: {auction.item_name}",
        description=(
            f"**Current Price:** {format_price(auction.current_price, auction.currency_symbol)}\n"
            f"**Highest Bidder:** {highest}\n"
            f"**Ends:** {format_timestamp(auction.end_time, 'R')}"
        ),
        color=discord.Color.purple(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(
    name="endauction", description="Force-end the current auction (seller only)."
)
async def endauction(interaction: discord.Interaction):
    # Retrieve the auction object for this channel
    auction = bot.auctions.get(interaction.channel_id)

    if not auction:
        await interaction.response.send_message(
            "No auction running in this channel.", ephemeral=True
        )
        return

    # Check if the user is the seller or an admin
    if (
        interaction.user != auction.seller
        and not interaction.user.guild_permissions.administrator
    ):
        await interaction.response.send_message(
            "Only the seller or an admin can force-end the auction.", ephemeral=True
        )
        return

    # Cancel background tasks immediately to prevent duplicate "End" triggers
    if auction.end_task and not auction.end_task.done():
        auction.end_task.cancel()
    if auction.reminder_task and not auction.reminder_task.done():
        auction.reminder_task.cancel()

    # We pass the WHOLE auction object, ensuring we have the direct channel reference
    await finalize_auction(bot, auction, forced=True)

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
    if (
        not auction.last_bid_message
        or auction.last_bid_message.id != payload.message_id
    ):
        return

    pref_key = (payload.channel_id, payload.user_id)
    current = bot.notification_prefs.get(pref_key, False)
    bot.notification_prefs[pref_key] = not current

    channel = bot.get_channel(payload.channel_id)
    if channel:
        try:
            message = await channel.fetch_message(payload.message_id)
            if not current:
                await message.channel.send(
                    f"<@{payload.user_id}> will now be DM'd if outbid!", delete_after=5
                )
            else:
                await message.channel.send(
                    f"<@{payload.user_id}> will no longer receive outbid notifications.",
                    delete_after=5,
                )
        except:
            pass


# ========== MYSTERY CRATE COMMANDS ==========


@bot.tree.command(name="additem", description="Add an item to the mystery crate pool")
@app_commands.describe(
    name="Item name",
    image="Upload an image (optional)",
    image_url="Or provide an image URL (optional)",
)
async def additem(
    interaction: discord.Interaction,
    name: str,
    image: discord.Attachment = None,
    image_url: str = None,
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to add items.", ephemeral=True
        )
        return

    if image and image_url:
        await interaction.response.send_message(
            "Please provide either an uploaded image or a URL, not both.",
            ephemeral=True,
        )
        return

    if not image and not image_url:
        await interaction.response.send_message(
            "You must provide either an image upload or an image URL.", ephemeral=True
        )
        return

    final_url = image.url if image else image_url
    item_id = database.add_item(name, final_url)
    await interaction.response.send_message(f"✅ Item added with ID #{item_id}: {name}")


@bot.tree.command(name="removeitem", description="Remove an item from the pool by ID")
@app_commands.describe(item_id="The ID of the item to remove")
async def removeitem(interaction: discord.Interaction, item_id: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to remove items.", ephemeral=True
        )
        return
    if database.remove_item(item_id):
        await interaction.response.send_message(f"✅ Item #{item_id} removed.")
    else:
        await interaction.response.send_message(
            f"❌ Item #{item_id} not found.", ephemeral=True
        )


@bot.tree.command(name="addpoints", description="Add points to a user")
@app_commands.describe(user="The user to reward", amount="Number of points")
async def addpoints(
    interaction: discord.Interaction, user: discord.Member, amount: int
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to add points.", ephemeral=True
        )
        return
    database.add_points(user.id, amount)
    await interaction.response.send_message(
        f"✅ Added {amount} points to {user.mention}."
    )


@bot.tree.command(name="removepoints", description="Remove points from a user")
@app_commands.describe(user="The user", amount="Number of points")
async def removepoints(
    interaction: discord.Interaction, user: discord.Member, amount: int
):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to remove points.", ephemeral=True
        )
        return
    if database.remove_points(user.id, amount):
        await interaction.response.send_message(
            f"✅ Removed {amount} points from {user.mention}."
        )
    else:
        await interaction.response.send_message(
            f"❌ {user.mention} doesn't have enough points.", ephemeral=True
        )


@bot.tree.command(name="setdrawcost", description="Set the points required per draw")
@app_commands.describe(amount="Points per draw")
async def setdrawcost(interaction: discord.Interaction, amount: int):
    role = discord.utils.get(interaction.guild.roles, name="Cryysys")
    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You need the **Cryysys** role to set draw cost.", ephemeral=True
        )
        return
    database.set_setting("draw_cost", str(amount))
    await interaction.response.send_message(f"✅ Draw cost set to {amount} points.")


@bot.tree.command(
    name="items", description="Browse all items in the mystery crate pool"
)
async def items(interaction: discord.Interaction):
    items = database.get_all_items()
    if not items:
        await interaction.response.send_message("The pool is empty.")
        return

    if len(items) > 25:
        await interaction.response.send_message(
            f"Too many items ({len(items)}). Max 25. Contact an admin to reduce the pool.",
            ephemeral=True,
        )
        return

    view = ItemDropdownView(bot, items, interaction.user.id)

    item_id, name, url = items[0]
    embed = discord.Embed(title=name, color=discord.Color.blue())
    if url:
        embed.set_image(url=url)
    embed.set_footer(text=f"Item 1 of {len(items)} (use dropdown to change)")

    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


@bot.tree.command(name="points", description="Check your current points")
async def points(interaction: discord.Interaction):
    pts = database.get_points(interaction.user.id)
    await interaction.response.send_message(
        f"You have **{pts}** points.", ephemeral=True
    )


@bot.tree.command(
    name="draw", description="Draw a random item from the pool (costs points)"
)
async def draw(interaction: discord.Interaction):
    if interaction.channel.name != "mystery-crates":
        await interaction.response.send_message(
            "You can only use `/draw` in #mystery-crates.", ephemeral=True
        )
        return

    cost = int(database.get_setting("draw_cost", "10"))
    user_id = interaction.user.id
    pts = database.get_points(user_id)

    if pts < cost:
        await interaction.response.send_message(
            f"You need {cost} points to draw. You have {pts}.", ephemeral=True
        )
        return

    item = database.draw_random_item()
    if not item:
        await interaction.response.send_message(
            "The pool is empty. Ask an admin to add items!", ephemeral=True
        )
        return

    database.remove_points(user_id, cost)
    database.record_draw(user_id, item[0])

    embed = discord.Embed(
        title="🎁 Mystery Box",
        description=f"You open the mystery box and get... **{item[1]}**!",
        color=discord.Color.green(),
    )
    if item[2]:
        embed.set_image(url=item[2])
    await interaction.response.send_message(embed=embed)


# ========== BOT START ==========


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    database.init_db()
    print("Database initialized.")


if __name__ == "__main__":
    bot.run(TOKEN)
