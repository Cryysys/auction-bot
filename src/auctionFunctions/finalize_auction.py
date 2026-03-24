import discord
from src.helperFunctions.formatting_helpers import format_price


async def finalize_auction(bot, auction_or_id, forced=False):
    """
    Finalizes the auction.
    Accepts either an Auction object (preferred) or a channel ID (for fallback).
    """
    # 1. Determine if we were given an object or an ID
    if isinstance(auction_or_id, int):
        auction = bot.auctions.pop(auction_or_id, None)
    else:
        auction = auction_or_id
        # Remove it from the dictionary so no more bids can be placed
        bot.auctions.pop(auction.channel.id, None)

    if not auction:
        return

    # 2. Use the direct references saved in the Auction object
    channel = auction.channel
    seller = auction.seller
    winner = auction.highest_bidder
    price = auction.current_price

    # 3. Prepare the Final Announcement Embed
    end_embed = discord.Embed(
        title=f"🔨 Auction Ended: {auction.item_name}", color=discord.Color.red()
    )

    if winner:
        end_embed.description = (
            f"🎊 **Congratulations to the winner!** 🎊\n\n"
            f"**Winner:** {winner.mention}\n"
            f"**Seller:** {seller.mention}\n"
            f"**Final Price:** {format_price(price, auction.currency_symbol)}"
        )
    else:
        end_embed.description = (
            f"The auction ended with no bids.\n**Seller:** {seller.mention}"
        )

    # Bring back the thumbnail so people see what was just sold
    if auction.image_url:
        end_embed.set_thumbnail(url=auction.image_url)

    # 4. Send to the channel
    try:
        await channel.send(embed=end_embed)
    except Exception as e:
        print(f"[ERROR] Could not send end message to channel {channel.id}: {e}")

    # 5. DM the Seller
    try:
        if winner:
            await seller.send(
                f"Your auction for **{auction.item_name}** ended.\n"
                f"Winner: {winner.display_name} with {format_price(price, auction.currency_symbol)}."
            )
        else:
            await seller.send(
                f"Your auction for **{auction.item_name}** ended with no bids."
            )
    except Exception as e:
        print(f"[ERROR] Could not DM seller {seller.id}: {e}")
