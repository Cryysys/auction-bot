from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import discord

from src.auctionFunctions.process_bid import process_bid

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot


def register(bot: AuctionBot):
    @bot.tree.command(
        name="quickbid", description="Bid the minimum increment automatically."
    )
    async def quickbid(interaction: discord.Interaction):
        auction = (
            bot.auctions.get(interaction.channel_id)
            if interaction.channel_id is not None
            else None
        )
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

        # Quick pre-lock check (best-effort, re-checked inside process_bid)
        now = datetime.now(timezone.utc)
        if now >= auction.end_time:
            await interaction.response.send_message(
                "This auction has already ended.", ephemeral=True
            )
            return

        await interaction.response.defer()

        async with auction.bid_lock:
            try:
                bid_value = auction.current_price + auction.min_increment
                await process_bid(
                    bot, interaction, auction, bid_value, "New Quick Bid!"
                )
            except Exception as e:
                print(f"Error in quickbid: {e}")
