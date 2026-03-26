from __future__ import annotations

import discord
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.helperFunctions.formatting_helpers import format_price, format_timestamp

if TYPE_CHECKING:
    from src.Auction import Auction
    from src.AuctionBot import AuctionBot


async def process_bid(
    bot: AuctionBot,
    interaction: discord.Interaction,
    auction: Auction,
    bid_value: int,
    embed_title: str,
) -> None:
    """
    Core bid logic. Must be called while holding auction.bid_lock.
    Re-validates the auction state with a fresh timestamp, updates auction state,
    handles anti-sniping, and sends the bid embed + outbid notification.
    """
    now = datetime.now(timezone.utc)
    if now >= auction.end_time:
        await interaction.followup.send(
            "This auction has already ended.", ephemeral=True
        )
        return

    if bid_value < auction.current_price + auction.min_increment:
        await interaction.followup.send(
            f"Bid must be at least **{format_price(auction.current_price + auction.min_increment, auction.currency_symbol)}**.",
            ephemeral=True,
        )
        return

    old_highest = auction.highest_bidder

    # Update state
    auction.current_price = bid_value
    auction.highest_bidder = interaction.user
    auction.bidders.add(interaction.user.id)

    # Anti-sniping
    time_left = (auction.end_time - now).total_seconds()
    extended = False
    if time_left <= 120:
        auction.end_time += timedelta(minutes=1)
        extended = True

    # Update master message
    master_embed = discord.Embed(
        title=f"🎨 Auction: {auction.item_name}",
        description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
        color=discord.Color.blue(),
    )
    master_embed.add_field(
        name="Current Bid",
        value=format_price(auction.current_price, auction.currency_symbol),
        inline=True,
    )
    master_embed.add_field(
        name="Min Increment",
        value=format_price(auction.min_increment, auction.currency_symbol),
        inline=True,
    )
    master_embed.add_field(
        name="Highest Bidder",
        value=auction.highest_bidder.mention,
        inline=False,
    )
    if auction.image_url:
        master_embed.set_thumbnail(url=auction.image_url)

    if auction.message:
        try:
            await auction.message.edit(embed=master_embed)
        except Exception:
            pass

    # Send bid embed
    extend_msg = (
        "\n⏰ **Anti-sniping activated!** Auction extended by 1 minute."
        if extended
        else ""
    )
    embed_bid = discord.Embed(
        title=embed_title,
        description=(
            f"**Item:** {auction.item_name}\n"
            f"**Bidder:** {interaction.user.mention}\n"
            f"**New Price:** {format_price(bid_value, auction.currency_symbol)}\n"
            f"{extend_msg}\n\n"
            f"🔔 Click the bell on this message to get notified if you're outbid!\n"
            f"**Auction ends ** {format_timestamp(auction.end_time, 'R')}"
        ),
        color=discord.Color.blue(),
    )
    if auction.image_url:
        embed_bid.set_thumbnail(url=auction.image_url)

    bid_message = await interaction.followup.send(embed=embed_bid, wait=True)

    try:
        await bid_message.add_reaction("🔔")
        auction.last_bid_message = bid_message
    except Exception:
        auction.last_bid_message = None

    # Outbid notification
    if (
        old_highest
        and old_highest != interaction.user
        and interaction.channel_id is not None
    ):
        pref_key = (interaction.channel_id, old_highest.id)
        if bot.notification_prefs.get(pref_key, False):
            try:
                await old_highest.send(
                    f"You've been outbid for **{auction.item_name}**! New price: {format_price(bid_value, auction.currency_symbol)}"
                )
            except Exception:
                pass
