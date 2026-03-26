from __future__ import annotations
from datetime import datetime, timezone
from discord.ext import commands, tasks
from typing import TYPE_CHECKING
import database
import discord

from src.auctionFunctions.trigger_auction import trigger_auction
from src.helperFunctions.get_guild_member import get_guild_member
from src.helperFunctions.get_text_channel import get_text_channel
from src.helperFunctions.get_user import get_user
from src.helperFunctions.parse_amount import parse_amount
from src.helperFunctions.parse_duration import parse_duration

if TYPE_CHECKING:
    from src.Auction import Auction
    from src.ItemDropdownView import ItemDropdownView


class AuctionBot(commands.Bot):
    def __init__(self, intents):
        super().__init__(command_prefix="!", intents=intents)
        self.auctions: dict[int, Auction] = {}
        self.notification_prefs: dict[tuple[int, int], bool] = {}
        self.active_views: list[ItemDropdownView] = []

    async def setup_hook(self):
        self.check_scheduled_auctions.start()
        await self.tree.sync()
        print(f"Synced commands for {self.user}")

    # --- CATCH BUTTON CLICKS FOR NOTIFICATIONS ---
    async def on_interaction(self, interaction: discord.Interaction):
        if (
            interaction.type == discord.InteractionType.component
            and interaction.data is not None
        ):
            custom_id: str = str(interaction.data.get("custom_id", ""))
            if custom_id.startswith("sched_bell_"):
                auction_id = int(custom_id.split("_")[2])
                item_name = database.get_scheduled_auction_item_name(auction_id)
                if database.toggle_scheduled_notif(auction_id, interaction.user.id):
                    await interaction.response.send_message(
                        f"✅ You will get a DM when the auction for **{item_name}** starts!",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "🔕 You will no longer be notified when the auction for **{item_name}** starts.",
                        ephemeral=True,
                    )

    # --- BACKGROUND LOOP ---
    @tasks.loop(seconds=60)
    async def check_scheduled_auctions(self):
        for pendingAuction in database.get_pending_auctions():
            (
                db_id,
                channel_id,
                seller_id,
                item_name,
                duration,
                start_price,
                min_increment,
                image_url,
                start_time,
            ) = pendingAuction
            if datetime.now(timezone.utc) >= datetime.fromisoformat(start_time).replace(
                tzinfo=timezone.utc
            ):
                if channel_id not in self.auctions:
                    try:
                        # --- SEND DMs TO SUBSCRIBERS ---
                        for subscriber_id in database.get_scheduled_notifs(db_id):
                            try:
                                user = await get_user(self, subscriber_id)
                                await user.send(
                                    f"🔔 **The auction for {item_name} is starting NOW!**\nJump in here: <#{channel_id}>"
                                )
                            except Exception:
                                # TODO: Only ignore exact exception and log error otherwise (e.g. something like discord.DMsBlockedException - if exists)
                                pass  # Ignore if they have DMs blocked

                        channel = await get_text_channel(self, channel_id)
                        seller = await get_guild_member(channel, seller_id)

                        await trigger_auction(
                            bot=self,
                            channel=channel,
                            seller=seller,
                            item_name=item_name,
                            delta=parse_duration(duration),
                            start_val=parse_amount(start_price),
                            min_inc_val=parse_amount(min_increment),
                            image_url=image_url,
                        )

                        # Remove from database so it doesn't start twice
                        database.remove_scheduled_auction(db_id)

                    except Exception as exception:
                        print(
                            f"Failed to auto-start scheduled auction for {item_name}: {exception}"
                        )
                else:
                    print(
                        f"Channel {channel_id} is busy. Waiting to start scheduled auction: {item_name}"
                    )
