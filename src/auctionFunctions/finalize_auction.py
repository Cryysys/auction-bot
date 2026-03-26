from __future__ import annotations
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import database
import discord

from src.helperFunctions.format_price import format_price

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot
    from src.Auction import Auction


async def finalize_auction(
    bot: AuctionBot, auction_or_id: Auction | int, forced: bool = False
) -> None:
    if isinstance(auction_or_id, int):
        auction = bot.auctions.pop(auction_or_id, None)
    else:
        auction = auction_or_id
        bot.auctions.pop(auction.channel.id, None)

    if not auction:
        return

    channel = auction.channel
    seller = auction.seller
    winner = auction.highest_bidder
    price = auction.current_price

    # 1. Final Announcement Embed
    end_embed = discord.Embed(
        title=f"🔨 Auction Ended: {auction.item_name}", color=discord.Color.red()
    )

    if winner:
        end_embed.description = (
            f"🎊 **Congratulations to the winner!** 🎊\n\n"
            f"**Winner:** {winner.mention}\n"
            f"**Seller:** {seller.mention}\n"
            f"**Final Price:** {format_price(price)}"
        )
    else:
        end_embed.description = (
            f"The auction ended with no bids.\n**Seller:** {seller.mention}"
        )

    if auction.image_url:
        end_embed.set_thumbnail(url=auction.image_url)

    await channel.send(embed=end_embed)

    # 2. POST-AUCTION RECAP (The new part!)
    upcoming = database.get_channel_upcoming(channel.id, limit=3)
    if upcoming:
        recap_desc = ""
        for row in upcoming:
            # db_id, ch_id, sell_id, item, dur, price, inc, img, start_t_str
            db_id, _, _, item, _, _, _, _, start_t_str = row

            # Convert string from DB to dynamic Discord timestamp
            start_t = datetime.fromisoformat(start_t_str).replace(tzinfo=timezone.utc)
            unix_time = int(start_t.timestamp())
            recap_desc += f"• **{item}** — <t:{unix_time}:R>\n"

        recap_embed = discord.Embed(
            title="📅 Coming Up Next...",
            description=recap_desc,
            color=discord.Color.blue(),
        )
        recap_embed.set_footer(text="Use /upcoming to see details and subscribe!")
        await channel.send(embed=recap_embed)

    # 3. DM the Seller
    try:
        if winner:
            await seller.send(
                f"Your auction for **{auction.item_name}** ended. Winner: {winner.display_name}."
            )
        else:
            await seller.send(
                f"Your auction for **{auction.item_name}** ended with no bids."
            )
    except Exception:
        # TODO: Only silently catch specific exception, log error otherwise
        pass
