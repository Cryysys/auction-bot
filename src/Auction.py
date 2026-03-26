from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord
    from datetime import datetime
    from discord import Member, User


class Auction:
    def __init__(
        self,
        channel: discord.TextChannel,
        seller: discord.Member,
        item_name: str,
        start_price: int,
        min_increment: int,
        end_time: datetime,
        start_message: discord.Message,
        start_time: datetime | None = None,
    ):
        self.channel = channel
        self.seller = seller
        self.item_name = item_name
        self.start_price = start_price
        self.min_increment = min_increment
        self.current_price = start_price
        self.end_time = end_time
        self.highest_bidder: Member | User | None = None
        self.bidders: set[int] = set()
        self.start_message = start_message
        self.reminder_1h_sent = False
        self.reminder_5m_sent = False
        self.end_task: asyncio.Task | None = None
        self.reminder_task: asyncio.Task | None = None
        self.last_bid_message: discord.Message | None = None
        self.message: discord.Message | None = None
        self.image_url: str | None = None
        self.bid_lock: asyncio.Lock = asyncio.Lock()
        self.start_time = start_time
        self.status = "ACTIVE" if start_time is None else "SCHEDULED"
        self.start_message = start_message
