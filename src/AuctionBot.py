from __future__ import annotations
from typing import TYPE_CHECKING

from discord.ext import commands

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
        await self.tree.sync()
        print(f"Synced commands for {self.user}")
