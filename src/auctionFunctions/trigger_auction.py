from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import asyncio
import discord

from src.Auction import Auction
from src.auctionFunctions.auction_end_timer import auction_end_timer
from src.auctionFunctions.auction_reminders import auction_reminders
from src.helperFunctions.format_price import format_price
from src.helperFunctions.format_timestamp import format_timestamp

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot

async def trigger_auction(
    bot: AuctionBot,
    channel: discord.TextChannel,
    seller: discord.Member,
    item_name: str,
    delta: timedelta,
    start_val: int,
    min_inc_val: int,
    image_url: str | None,
):
    """
    Shared function to actually start the auction.
    Now includes a Busy Check and a 2-minute buffer for back-to-back auctions.
    """
    
    # 1. BUSY CHECK & BUFFER
    was_busy = False
    while channel.id in bot.auctions:
        was_busy = True
        await asyncio.sleep(10) # Check every 10 seconds

    if was_busy:
        # Wait an extra 2 minutes so the channel 'breathes' after the last auction
        await asyncio.sleep(120)

    # 2. CALCULATION (Done after the wait to ensure full duration)
    end_time = datetime.now(timezone.utc) + delta

    # --- THE EMBED LAYOUT ---
    embed = discord.Embed(
        title=f"🎨 Auction Started: {item_name}",
        description=(
            f"**Seller:** {seller.mention}\n"
            f"**Ends:** {format_timestamp(end_time, 'R')}"
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(name="Current Bid", value=format_price(start_val), inline=True)
    embed.add_field(name="Min Increment", value=format_price(min_inc_val), inline=True)
    embed.add_field(name="Highest Bidder", value="No bids yet", inline=False)

    if image_url:
        embed.set_thumbnail(url=image_url)

    # Send the live card to the channel
    start_message = await channel.send(embed=embed)

    # --- CREATE AUCTION OBJECT ---
    auction = Auction(
        channel=channel,
        seller=seller,
        item_name=item_name,
        start_price=start_val,
        min_increment=min_inc_val,
        end_time=end_time,
        start_message=start_message,
    )

    auction.message = start_message
    auction.image_url = image_url

    # Save to the bot's live memory
    bot.auctions[channel.id] = auction

    # Start the countdown tasks
    auction.end_task = asyncio.create_task(auction_end_timer(bot, auction))
    auction.reminder_task = asyncio.create_task(auction_reminders(bot, auction))
