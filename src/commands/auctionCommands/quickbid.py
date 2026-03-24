import discord
from datetime import datetime, timedelta, timezone

from src.helperFunctions.formatting_helpers import (
    format_price,
    format_timestamp,
    plain_time,
)


def register(bot):
    @bot.tree.command(
        name="quickbid", description="Bid the minimum increment automatically."
    )
    async def quickbid(interaction: discord.Interaction):
        auction = bot.auctions.get(interaction.channel_id)
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

        now = datetime.now(timezone.utc)
        if now >= auction.end_time:
            await interaction.response.send_message(
                "This auction has already ended.", ephemeral=True
            )
            return

        await interaction.response.defer()
        old_highest = auction.highest_bidder

        try:
            new_price = auction.current_price + auction.min_increment
            auction.current_price = new_price
            auction.highest_bidder = interaction.user
            auction.bidders.add(interaction.user.id)

            time_left = (auction.end_time - now).total_seconds()
            extended = False
            if time_left <= 120:
                auction.end_time += timedelta(minutes=1)
                extended = True

            # Update Master Message
            master_embed = discord.Embed(
                title=f"🎨 Auction: {auction.item_name}",
                description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
                color=discord.Color.blue(),
            )
            master_embed.add_field(
                name="Current Bid",
                value=format_price(new_price, auction.currency_symbol),
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

            # Create Quick Bid Embed (Matching the /bid style)
            extend_msg = (
                "\n⏰ **Anti‑sniping activated!** Auction extended by 1 minute."
                if extended
                else ""
            )

            embed_bid = discord.Embed(
                title="New Quick Bid!",
                description=(
                    f"**Item:** {auction.item_name}\n"
                    f"**Bidder:** {interaction.user.mention}\n"
                    f"**New Price:** {format_price(new_price, auction.currency_symbol)}\n"
                    f"{extend_msg}\n\n"
                    f"🔔 Click the bell on this message to get notified if you're outbid!\n"
                    f"**Auction ends at:** {plain_time(auction.end_time)}"
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

            if old_highest and old_highest != interaction.user:
                pref_key = (interaction.channel_id, old_highest.id)
                if bot.notification_prefs.get(pref_key, False):
                    try:
                        await old_highest.send(
                            f"You've been outbid for **{auction.item_name}**! New price: {format_price(new_price, auction.currency_symbol)}"
                        )
                    except Exception:
                        pass

        except Exception as e:
            print(f"Error in quickbid: {e}")
