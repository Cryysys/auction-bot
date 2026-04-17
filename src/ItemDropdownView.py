import discord
from discord.ui import View

class _ItemSelect(discord.ui.Select):
    def __init__(self, view: "ItemDropdownView", options: list[discord.SelectOption]):
        super().__init__(placeholder="Select an item to view...", options=options)
        self._parent_view = view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        idx = int(self.values[0])
        item_id, name, url = self._parent_view.items[idx]

        embed = discord.Embed(title=name, color=discord.Color.blue())
        if url:
            # Check if URL is valid before setting image
            if url.startswith("http"):
                embed.set_image(url=url)
            else:
                # Handle relative paths from your CSV if necessary
                # e.g., embed.set_image(url=f"https://yourdomain.com{url}")
                pass
                
        embed.set_footer(text=f"Item {idx+1} of {len(self._parent_view.items)}")

        await interaction.edit_original_response(embed=embed, view=self._parent_view)


# ========== MYSTERY CRATE DROPDOWN VIEW ==========
class ItemDropdownView(View):
    def __init__(self, bot, items, user_id):
        super().__init__(timeout=60)
        self.bot = bot
        self.items = items
        self.user_id = user_id
        self.message: discord.InteractionMessage | None = None

        options = []
        # Discord Select Menus are limited to 25 items
        for i, (item_id, name, url) in enumerate(items[:25]):
            options.append(
                discord.SelectOption(
                    label=f"{name[:50]}", 
                    value=str(i), 
                    description=f"Item #{item_id}"
                )
            )

        self.select: discord.ui.Select = _ItemSelect(self, options)
        self.add_item(self.select)

        # Track active views if your bot uses this for cleanup on shutdown
        if hasattr(self.bot, 'active_views'):
            self.bot.active_views.append(self)

    async def on_timeout(self):
        """Called when the 60s timer expires."""
        # --- FIX: ERROR HANDLING ---
        # We wrap this in a try/except because if a user or admin deleted 
        # the message manually, trying to edit it will crash this task.
        try:
            if self.message:
                await self.message.edit(view=None)
        except (discord.NotFound, discord.HTTPException):
            # Message is already gone or unreachable, ignore the error
            pass

        # Clean up from the bot's tracking list
        if hasattr(self.bot, 'active_views') and self in self.bot.active_views:
            self.bot.active_views.remove(self)