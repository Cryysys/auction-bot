from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import asyncio

from src.auctionFunctions.send_reminder_msg import send_reminder_msg

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot
    from src.Auction import Auction


async def auction_reminders(bot: AuctionBot, auction: Auction) -> None:
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

            await asyncio.sleep(30)  # Check the clock every 30 seconds
    except asyncio.CancelledError:
        pass
