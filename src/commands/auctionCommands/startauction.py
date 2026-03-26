from datetime import datetime, timedelta, timezone
from discord import app_commands
from zoneinfo import ZoneInfo
import discord

from database import add_scheduled_auction
from src.auctionFunctions.trigger_auction import trigger_auction
from src.helperFunctions.parse_amount import parse_amount
from src.helperFunctions.parse_duration import parse_duration


def register(bot):
    @bot.tree.command(name="startauction", description="Start or schedule an auction.")
    @app_commands.describe(
        seller="The member who is selling the item.",
        duration="Auction duration, e.g. 1h30m (max 48h).",
        item="Name of the item being sold.",
        start_price="Starting price (e.g. 100, 10M, 1.5B).",
        min_increment="Minimum bid increment (e.g. 10, 5M).",
        image_url="Direct link to an image or GIF of the item (optional).",
        start_at="When to start (DD-MM-YYYY HH:MM). Leave empty to start now.",
    )
    async def startauction(
        interaction: discord.Interaction,
        seller: discord.Member,
        duration: str,
        item: str,
        start_price: str,
        min_increment: str,
        image_url: str | None = None,
        start_at: str | None = None,
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

        if interaction.channel_id in bot.auctions and not start_at:
            await interaction.response.send_message(
                "An auction is already running in this channel!", ephemeral=True
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            return

        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                "I need `Send Messages` permission in this channel.", ephemeral=True
            )
            return

        # --- PARSE DATE IF SCHEDULED ---
        planned_start = None
        if start_at:
            try:
                # 1. Parse as European Time (Amsterdam covers CET/CEST)
                local_tz = ZoneInfo("Europe/Amsterdam")
                planned_start = datetime.strptime(start_at, "%d-%m-%Y %H:%M").replace(
                    tzinfo=local_tz
                )

                # 2. Convert to UTC for the bot's internal math
                planned_start = planned_start.astimezone(timezone.utc)

                if planned_start <= datetime.now(timezone.utc):
                    await interaction.response.send_message(
                        "Start time must be in the future!", ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "Use format: `DD-MM-YYYY HH:MM` (e.g. 06-05-2026 14:00)",
                    ephemeral=True,
                )
                return

        delta = parse_duration(duration)
        if delta is None or delta > timedelta(hours=48):
            await interaction.response.send_message(
                "Invalid duration format or exceeds 48h.", ephemeral=True
            )
            return

        start_val = parse_amount(start_price)
        min_inc_val = parse_amount(min_increment)
        if start_val is None or min_inc_val is None:
            await interaction.response.send_message(
                "Invalid price or increment format.", ephemeral=True
            )
            return

        # --- BRANCH: SCHEDULE OR START NOW ---
        if planned_start:
            # Save to Database and GET the Database ID
            db_id = add_scheduled_auction(
                interaction.channel_id,
                seller.id,
                item,
                duration,
                start_price,
                min_increment,
                image_url,
                planned_start,
            )

            # The magic timestamp format for dynamic countdowns!
            unix_time = int(planned_start.timestamp())

            embed = discord.Embed(
                title="📅 Auction Scheduled!",
                description=(
                    f"**Item:** {item}\n"
                    f"**Starts:** <t:{unix_time}:F> (<t:{unix_time}:R>)\n"
                    f"**Seller:** {seller.mention}"
                ),
                color=discord.Color.gold(),
            )
            if image_url:
                embed.set_thumbnail(url=image_url)

            # Create the Bell Button
            view = discord.ui.View(timeout=None)
            button: discord.ui.Button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Notify Me",
                emoji="🔔",
                custom_id=f"sched_bell_{db_id}",
            )
            view.add_item(button)

            await interaction.response.send_message(embed=embed, view=view)

        else:
            await interaction.response.defer()
            await trigger_auction(
                bot=bot,
                channel=interaction.channel,
                seller=seller,
                item_name=item,
                delta=delta,
                start_val=start_val,
                min_inc_val=min_inc_val,
                image_url=image_url,
            )
            await interaction.followup.send(
                "✅ Auction started successfully!", ephemeral=True
            )
