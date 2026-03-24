from discord.ext import commands


class AuctionBot(commands.Bot):
    def __init__(self, intents):
        super().__init__(command_prefix="!", intents=intents)
        self.auctions = {}
        self.notification_prefs = {}
        self.active_views = []

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced commands for {self.user}")
