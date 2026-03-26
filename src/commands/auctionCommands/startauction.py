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
from database import add_scheduled_auction # Import the DB function
from src.auctionFunctions.trigger_auction import trigger_auction # We will create this next!

def register(bot):
    @bot.tree.command(name="startauction", description="Start or schedule an auction.")
    @app_commands.describe(
        seller="The member who is selling the item.",
        duration="Auction duration, e.g. 1h30m (max 48h).",
        item="Name of the item being sold.",
        start_price="Starting price (e.g. 100, 10M, 1.5B).",
        min_increment="Minimum bid increment (e.g. 10, 5M).",
        image_url="Direct link to an image or GIF of the item (optional).",
        start_at="When to start (DD-MM-YYYY HH:MM). Leave empty to start now." # <-- Added optional start time
    )
    async def startauction(
        interaction: discord.Interaction,
        seller: discord.Member,
        duration: str,
        item: str,
        start_price: str,
        min_increment: str,
        image_url: str | None = None,
        start_at: str | None = None # <-- Parameter added
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("You need to be in a server to use this command.", ephemeral=True)
            return

        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message("You need the **Cryysys** role to start an auction.", ephemeral=True)
            return

        if interaction.channel_id in bot.auctions and not start_at:
            await interaction.response.send_message("An auction is already running in this channel!", ephemeral=True)
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            return
        
        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message("I need `Send Messages` permission in this channel.", ephemeral=True)
            return

        # --- PARSE DATE IF SCHEDULED ---
        planned_start = None
        if start_at:
            try:
                # Parse DD-MM-YYYY HH:MM
                planned_start = datetime.strptime(start_at, "%d-%m-%Y %H:%M")
                planned_start = planned_start.replace(tzinfo=timezone.utc)
                if planned_start <= datetime.now(timezone.utc):
                    await interaction.response.send_message("Start time must be in the future!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("Use format: `DD-MM-YYYY HH:MM` (e.g. 06-05-2026 14:00)", ephemeral=True)
                return

        delta = parse_duration(duration)
        if delta is None or delta > timedelta(hours=48):
            await interaction.response.send_message("Invalid duration format or exceeds 48h.", ephemeral=True)
            return

        start_val, currency = parse_amount(start_price)
        min_inc_val, _ = parse_amount(min_increment)
        if start_val is None or min_inc_val is None or currency is None:
            await interaction.response.send_message("Invalid price or increment format.", ephemeral=True)
            return

        # --- BRANCH: SCHEDULE OR START NOW ---
        if planned_start:
            # Save to Database for later
            add_scheduled_auction(
                interaction.channel_id, seller.id, item, duration, 
                start_price, min_increment, image_url, planned_start, currency
            )
            
            embed = discord.Embed(
                title="📅 Auction Scheduled!",
                description=f"**Item:** {item}\n**Starts:** {format_timestamp(planned_start, 'F')}\n**Seller:** {seller.mention}",
                color=discord.Color.gold()
            )
            if image_url: 
                embed.set_thumbnail(url=image_url)
            await interaction.response.send_message(embed=embed)
            
        else:
            # Start immediately using our new shared helper function!
            await interaction.response.defer() # Give bot time to process
            await trigger_auction(
                bot=bot, channel=interaction.channel, seller=seller, item_name=item, 
                delta=delta, start_val=start_val, min_inc_val=min_inc_val, 
                currency=currency, image_url=image_url
            )
            await interaction.followup.send("✅ Auction started successfully!", ephemeral=True)
