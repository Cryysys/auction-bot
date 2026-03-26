import discord
import asyncio
from datetime import datetime, timezone
from src.Auction import Auction
from src.auctionFunctions.auction_end_timer import auction_end_timer
from src.auctionFunctions.auction_reminders import auction_reminders
from src.helperFunctions.formatting_helpers import format_price, format_timestamp

async def trigger_auction(bot, channel, seller, item_name, delta, start_val, min_inc_val, currency, image_url):
    """
    Shared function to actually start the auction, send the embed, and begin tracking.
    Used by BOTH the /startauction command and the background auto-scheduler.
    """
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
    embed.add_field(name="Current Bid", value=format_price(start_val, currency), inline=True)
    embed.add_field(name="Min Increment", value=format_price(min_inc_val, currency), inline=True)
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
        currency_symbol=currency,
    )

    auction.message = start_message
    auction.image_url = image_url

    # Save to the bot's live memory
    bot.auctions[channel.id] = auction

    # Start the countdown tasks
    auction.end_task = asyncio.create_task(auction_end_timer(bot, auction))
    auction.reminder_task = asyncio.create_task(auction_reminders(bot, auction))
