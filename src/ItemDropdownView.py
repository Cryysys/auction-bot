import discord
from discord.ui import View


# ========== MYSTERY CRATE DROPDOWN VIEW ==========
class ItemDropdownView(View):
    def __init__(self, bot, items, user_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.items = items
        self.user_id = user_id
        self.message: discord.InteractionMessage | None = None

        options = []
        for i, (item_id, name, url) in enumerate(items[:25]):
            options.append(
                discord.SelectOption(
                    label=f"{name[:50]}", value=str(i), description=f"Item #{item_id}"
                )
            )

        self.select = discord.ui.Select(
            placeholder="Select an item to view...", options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.bot.active_views.append(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your menu.", ephemeral=True)
            return False
        return True

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        idx = int(self.select.values[0])
        item_id, name, url = self.items[idx]

        embed = discord.Embed(title=name, color=discord.Color.blue())
        if url:
            embed.set_image(url=url)
        embed.set_footer(text=f"Item {idx+1} of {len(self.items)}")

        await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)
        if self in self.bot.active_views:
            self.bot.active_views.remove(self)
