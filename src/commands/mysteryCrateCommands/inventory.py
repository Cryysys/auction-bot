import discord
from discord import app_commands

import database


class InventoryView(discord.ui.View):
    def __init__(self, owner_id: int, rows, title: str, diamonds: int):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.rows = rows
        self.title = title
        self.diamonds = diamonds
        self.page = 0
        self.per_page = 8
        self.update_buttons()

    def update_buttons(self):
        total_pages = max(1, (len(self.rows) - 1) // self.per_page + 1)
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= total_pages - 1

    def create_embed(self) -> discord.Embed:
        total_pages = max(1, (len(self.rows) - 1) // self.per_page + 1)
        start = self.page * self.per_page
        end = start + self.per_page
        slice_rows = self.rows[start:end]

        embed = discord.Embed(title=self.title, color=discord.Color.blurple())
        if not slice_rows:
            embed.description = "No collectables found."
        else:
            lines = []
            for row in slice_rows:
                _, name, category, rarity, _, _, _, quantity = row
                lines.append(f"**{name}** x{quantity} - `{rarity}` ({category})")
            embed.description = "\n".join(lines)
        embed.set_footer(
            text=f"Page {self.page + 1}/{total_pages} | {len(self.rows)} total | Diamonds: {self.diamonds}"
        )
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the command user can paginate.", ephemeral=True)
            return
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Only the command user can paginate.", ephemeral=True)
            return
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


def register(bot):
    @bot.tree.command(name="inventory", description="View your collectable inventory")
    @app_commands.describe(
        user="Whose inventory to view",
        category="Optional category filter",
        rarity="Optional rarity filter",
    )
    async def inventory(
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        category: str | None = None,
        rarity: str | None = None,
    ):
        target = user or interaction.user
        rows = database.get_user_inventory(
            target.id, category=category, rarity=rarity.lower() if rarity else None
        )
        diamonds = database.get_diamonds(target.id)
        title = f"{target.display_name}'s Collection"
        view = InventoryView(interaction.user.id, rows, title, diamonds)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
