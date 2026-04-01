from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import asyncio

from src.auctionFunctions.send_reminder_msg import send_reminder_msg

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot
    from src.Auction import Auction

async def auction_reminders(bot: AuctionBot, auction: Auction) -> None:
    """Accurately send 3-hour, 1-hour, and 5-minute reminders by checking every 30s."""
    try:
        while auction.channel.id in bot.auctions:
            now = datetime.now(timezone.utc)
            remaining = (auction.end_time - now).total_seconds()

            # 3-hour reminder (10800 seconds)
            if 10740 <= remaining <= 10800 and not auction.reminder_3h_sent:
                await send_reminder_msg(auction, "3 hours")
                auction.reminder_3h_sent = True

            # 1-hour reminder (3600 seconds)
            if 3540 <= remaining <= 3600 and not auction.reminder_1h_sent:
                await send_reminder_msg(auction, "1 hour")
                auction.reminder_1h_sent = True

            # 5-minute reminder (300 seconds)
            if 270 <= remaining <= 300 and not auction.reminder_5m_sent:
                await send_reminder_msg(auction, "5 minutes")
                auction.reminder_5m_sent = True

            # Reset flags if a bid extends the auction
            if remaining > 10810:
                auction.reminder_3h_sent = False
            if remaining > 3610:
                auction.reminder_1h_sent = False
            if remaining > 310:
                auction.reminder_5m_sent = False

            if remaining <= 0:
                break

            await asyncio.sleep(30)
    except asyncio.CancelledError:
        pass
