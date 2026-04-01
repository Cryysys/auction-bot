from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import discord

from src.helperFunctions.format_price import format_price
from src.helperFunctions.format_timestamp import format_timestamp

if TYPE_CHECKING:
    from src.Auction import Auction
    from src.AuctionBot import AuctionBot

async def notify_proxy_spent(bot, user_id, auction):
    """Sends a DM to a user when their max bid is outmatched."""
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        await user.send(f"❌ Your Max Bid for **{auction.item_name}** in {auction.channel.mention} has been outbid!")
    except Exception:
        pass

async def process_bid(
    bot: AuctionBot,
    interaction: discord.Interaction,
    auction: Auction,
    bid_value: int,
    embed_title: str,
) -> None:
    now = datetime.now(timezone.utc)
    if now >= auction.end_time:
        if not interaction.response.is_done():
            await interaction.followup.send("This auction has already ended.", ephemeral=True)
        return

    # 1. NEW ANTI-SNIPE LOGIC (Sets exact remaining time to 5 minutes)
    time_left = (auction.end_time - now).total_seconds()
    extended = False
    if time_left < 300: # 5 minutes
        auction.end_time = now + timedelta(minutes=5)
        extended = True

    # 2. PROXY BID RESOLUTION ENGINE
    winning_user = interaction.user
    winning_price = bid_value
    
    # We resolve proxy wars until no proxy can outbid the current winning_price + min_inc
    while True:
        # Get all proxies EXCEPT the current leader
        competitors = {uid: amt for uid, amt in auction.max_bids.items() if uid != getattr(winning_user, "id", winning_user)}
        if not competitors:
            break
            
        top_uid = max(competitors, key=competitors.get)
        top_val = competitors[top_uid]
        needed_to_beat = winning_price + auction.min_increment
        
        if top_val >= needed_to_beat:
            # Proxy outbids the current lead
            winning_price = needed_to_beat
            winning_user = bot.get_user(top_uid) or await bot.fetch_user(top_uid)
            embed_title = "Auto-Bid Placed!"
        elif top_val > winning_price:
            # Proxy is higher, but doesn't have a full increment left. Proxy wins exactly at its max.
            winning_price = top_val
            winning_user = bot.get_user(top_uid) or await bot.fetch_user(top_uid)
            embed_title = "Auto-Bid Placed!"
            # Proxy is now spent
            await notify_proxy_spent(bot, top_uid, auction)
            del auction.max_bids[top_uid]
        else:
            # The current winning_price beats the highest proxy!
            await notify_proxy_spent(bot, top_uid, auction)
            del auction.max_bids[top_uid]

    old_highest = auction.highest_bidder

    # 3. Update State
    auction.current_price = winning_price
    auction.highest_bidder = winning_user
    auction.bidders.add(getattr(winning_user, "id", winning_user))

    # 4. Update master message
    master_embed = discord.Embed(
        title=f"🎨 Auction: {auction.item_name}",
        description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
        color=discord.Color.blue(),
    )
    master_embed.add_field(name="Current Bid", value=format_price(auction.current_price), inline=True)
    master_embed.add_field(name="Min Increment", value=format_price(auction.min_increment), inline=True)
    master_embed.add_field(name="Highest Bidder", value=auction.highest_bidder.mention, inline=False)
    
    if auction.image_url:
        master_embed.set_thumbnail(url=auction.image_url)

    if auction.message:
        try: await auction.message.edit(embed=master_embed)
        except Exception: pass

    # 5. Send bid embed
    extend_msg = "\n⏰ **Anti-sniping!** Timer reset to 5:00." if extended else ""
    
    embed_bid = discord.Embed(
        title=embed_title,
        description=(
            f"**Item:** {auction.item_name}\n"
            f"**Bidder:** {auction.highest_bidder.mention}\n"
            f"**New Price:** {format_price(winning_price)}\n"
            f"{extend_msg}\n\n"
            f"🔔 Click the bell to get outbid notifications!\n"
            f"**Auction ends** {format_timestamp(auction.end_time, 'R')}"
        ),
        color=discord.Color.blue(),
    )
    if auction.image_url: embed_bid.set_thumbnail(url=auction.image_url)

    if not interaction.response.is_done():
        bid_message = await interaction.followup.send(embed=embed_bid, wait=True)
    else:
        # If maxbid already deferred/responded, send as a new message to the channel
        bid_message = await auction.channel.send(embed=embed_bid)

    try:
        await bid_message.add_reaction("🔔")
        auction.last_bid_message = bid_message
    except Exception:
        auction.last_bid_message = None

    # 6. Outbid notification
    if old_highest and old_highest != auction.highest_bidder and auction.channel.id is not None:
        pref_key = (auction.channel.id, old_highest.id)
        if bot.notification_prefs.get(pref_key, False):
            try:
                await old_highest.send(
                    f"You've been outbid for **{auction.item_name}**! "
                    f"New price: {format_price(winning_price)}. "
                    f"The auction ends {format_timestamp(auction.end_time, 'R')}, "
                    f"jump in here: {auction.channel.mention}"
                )
            except Exception: pass
