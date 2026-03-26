from __future__ import annotations

import discord
from discord import app_commands
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.auctionFunctions.process_bid import process_bid
from src.helperFunctions.formatting_helpers import format_price
from src.helperFunctions.parse_amount import parse_amount

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot


def register(bot: AuctionBot):
    @bot.tree.command(name="bid", description="Place a bid on the current auction.")
    @app_commands.describe(amount="Your bid amount (e.g. 150, 5M, 1.2B).")
    async def bid(interaction: discord.Interaction, amount: str):
        auction = (
            bot.auctions.get(interaction.channel_id)
            if interaction.channel_id is not None
            else None
        )
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

        bid_value, _ = parse_amount(amount)
        if bid_value is None:
            await interaction.response.send_message(
                "Invalid bid format.", ephemeral=True
            )
            return

        # Quick pre-lock checks (best-effort, re-checked inside process_bid when locked)
        now = datetime.now(timezone.utc)
        if now >= auction.end_time:
            await interaction.response.send_message(
                "This auction has already ended.", ephemeral=True
            )
            return

        if bid_value < auction.current_price + auction.min_increment:
            await interaction.response.send_message(
                f"Bid must be at least **{format_price(auction.current_price + auction.min_increment, auction.currency_symbol)}**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        async with auction.bid_lock:
            try:
                await process_bid(bot, interaction, auction, bid_value, "New Bid!")
            except Exception as e:
                print(f"Error in bid: {e}")
