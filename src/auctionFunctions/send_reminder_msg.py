from __future__ import annotations
from typing import TYPE_CHECKING
import discord

if TYPE_CHECKING:
    from src.Auction import Auction


async def send_reminder_msg(auction: Auction, time_label: str) -> None:
    """Helper to handle the logic of who to ping."""
    if auction.bidders:
        mentions = " ".join(f"<@{uid}>" for uid in auction.bidders)
        await auction.channel.send(f"⏰ **{time_label} left!** {mentions} final bids!")
    else:
        role = discord.utils.get(auction.channel.guild.roles, name="Auction Lover")
        mention = role.mention if role else "No bids yet."
        await auction.channel.send(f"⏰ **{time_label} left!** {mention}")
