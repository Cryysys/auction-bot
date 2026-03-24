from datetime import datetime, timezone
import asyncio
from src.auctionFunctions.finalize_auction import finalize_auction


async def auction_end_timer(bot, auction):
    """Wait until the end time and finalize."""
    try:
        # We loop and check every 5 seconds so we can react to extensions
        while auction.channel.id in bot.auctions:
            now = datetime.now(timezone.utc)
            wait_seconds = (auction.end_time - now).total_seconds()

            if wait_seconds <= 0:
                # Time is up!
                await finalize_auction(
                    bot, auction
                )  # Use the object-based fix from before
                break

            # Sleep in small increments so we stay responsive to bids
            await asyncio.sleep(min(wait_seconds, 5))
    except asyncio.CancelledError:
        pass
