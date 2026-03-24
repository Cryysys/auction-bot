import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from src.helperFunctions.formatting_helpers import (
    format_price,
    format_timestamp,
    plain_time,
)
from src.helperFunctions.parse_amount import parse_amount


def register(bot):
    @bot.tree.command(name="bid", description="Place a bid on the current auction.")
    @app_commands.describe(amount="Your bid amount (e.g. 150, 5M, 1.2B).")
    async def bid(interaction: discord.Interaction, amount: str):
        auction = bot.auctions.get(interaction.channel_id)
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

        bid_val, _ = parse_amount(amount)
        if bid_val is None:
            await interaction.response.send_message(
                "Invalid bid format.", ephemeral=True
            )
            return

        now = datetime.now(timezone.utc)
        if now >= auction.end_time:
            await interaction.response.send_message(
                "This auction has already ended.", ephemeral=True
            )
            return

        if bid_val < auction.current_price + auction.min_increment:
            await interaction.response.send_message(
                f"Bid must be at least **{format_price(auction.current_price + auction.min_increment, auction.currency_symbol)}**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        old_highest = auction.highest_bidder

        try:
            # 1. Update State
            auction.current_price = bid_val
            auction.highest_bidder = interaction.user
            auction.bidders.add(interaction.user.id)

            # 2. Anti-Sniping
            time_left = (auction.end_time - now).total_seconds()
            extended = False
            if time_left <= 120:
                auction.end_time += timedelta(minutes=1)
                extended = True

            # 3. Update the "Master Message" (The very first message)
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

            # 4. Create the "New Bid" Embed (The one that goes in the chat now)
            extend_msg = (
                "\n⏰ **Anti‑sniping activated!** Auction extended by 1 minute."
                if extended
                else ""
            )

            embed_bid = discord.Embed(
                title="New Bid!",
                description=(
                    f"**Item:** {auction.item_name}\n"
                    f"**Bidder:** {interaction.user.mention}\n"
                    f"**New Price:** {format_price(bid_val, auction.currency_symbol)}\n"
                    f"{extend_msg}\n\n"
                    f"🔔 Click the bell on this message to get notified if you're outbid!\n"
                    f"**Auction ends at:** {plain_time(auction.end_time)}"
                ),
                color=discord.Color.blue(),
            )
            if auction.image_url:
                embed_bid.set_thumbnail(url=auction.image_url)

            bid_message = await interaction.followup.send(embed=embed_bid, wait=True)

            # 5. Add Notification Reaction
            if bid_message:
                try:
                    await bid_message.add_reaction("🔔")
                    auction.last_bid_message = bid_message
                except Exception:
                    auction.last_bid_message = None

            # 6. Outbid Notification
            if old_highest and old_highest != interaction.user:
                pref_key = (interaction.channel_id, old_highest.id)
                if bot.notification_prefs.get(pref_key, False):
                    try:
                        await old_highest.send(
                            f"You've been outbid for **{auction.item_name}**! New price: {format_price(bid_val, auction.currency_symbol)}"
                        )
                    except Exception:
                        pass

        except Exception as e:
            print(f"Error in bid: {e}")
