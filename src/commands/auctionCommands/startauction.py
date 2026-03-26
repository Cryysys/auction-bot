import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone

from src.Auction import Auction
from src.auctionFunctions.auction_end_timer import auction_end_timer
from src.auctionFunctions.auction_reminders import auction_reminders
from src.helperFunctions.formatting_helpers import format_price, format_timestamp
from src.helperFunctions.parse_amount import parse_amount
from src.helperFunctions.parse_duration import parse_duration


def register(bot):
    @bot.tree.command(
        name="startauction", description="Start a new auction. (Requires Cryysys role)"
    )
    @app_commands.describe(
        seller="The member who is selling the item.",
        duration="Auction duration, e.g. 1h30m (max 48h).",
        item="Name of the item being sold.",
        start_price="Starting price (e.g. 100, 10M, 1.5B).",
        min_increment="Minimum bid increment (e.g. 10, 5M).",
        image_url="Direct link to an image or GIF of the item (optional).",  # <-- Added this
    )
    async def startauction(
        interaction: discord.Interaction,
        seller: discord.Member,
        duration: str,
        item: str,
        start_price: str,
        min_increment: str,
        image_url: str | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "You need to be in a server to use this command.", ephemeral=True
            )
            return

        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to start an auction.", ephemeral=True
            )
            return

        if interaction.channel_id in bot.auctions:
            await interaction.response.send_message(
                "An auction is already running in this channel!", ephemeral=True
            )
            return

        # Check bot permissions
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                "I need `Send Messages` permission in this channel.", ephemeral=True
            )
            return

        delta = parse_duration(duration)
        if delta is None:
            await interaction.response.send_message(
                "Invalid duration format. Use e.g. `1h30m` or `30m`. Max 48 hours.",
                ephemeral=True,
            )
            return
        if delta > timedelta(hours=48):
            await interaction.response.send_message(
                "Duration cannot exceed 48 hours.", ephemeral=True
            )
            return

        start_val, currency = parse_amount(start_price)
        min_inc_val, _ = parse_amount(min_increment)
        if start_val is None or min_inc_val is None or currency is None:
            await interaction.response.send_message(
                "Invalid price or increment format. Use numbers, optionally with M or B suffix.",
                ephemeral=True,
            )
            return

        end_time = datetime.now(timezone.utc) + delta

        # --- NEW EMBED LAYOUT WITH THUMBNAIL ---
        embed = discord.Embed(
            title=f"🎨 Auction Started: {item}",
            description=(
                f"**Seller:** {seller.mention}\n"
                f"**Ends:** {format_timestamp(end_time, 'R')}"
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Current Bid", value=format_price(start_val, currency), inline=True
        )
        embed.add_field(
            name="Min Increment", value=format_price(min_inc_val, currency), inline=True
        )
        embed.add_field(name="Highest Bidder", value="No bids yet", inline=False)

        # Set the small image in the top right corner if a link was provided
        if image_url:
            embed.set_thumbnail(url=image_url)

        await interaction.response.send_message(embed=embed)
        start_message = await interaction.original_response()

        # --- CREATE AUCTION OBJECT ---
        auction = Auction(
            channel=interaction.channel,
            seller=seller,
            item_name=item,
            start_price=start_val,
            min_increment=min_inc_val,
            end_time=end_time,
            start_message=start_message,
            currency_symbol=currency,
        )

        # Store the tracking variables we added to your Auction class
        auction.message = start_message
        auction.image_url = image_url

        bot.auctions[interaction.channel_id] = auction

        auction.end_task = asyncio.create_task(auction_end_timer(bot, auction))
        auction.reminder_task = asyncio.create_task(auction_reminders(bot, auction))
