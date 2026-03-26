import discord
import database

from src.ItemDropdownView import ItemDropdownView


def register(bot):
    @bot.tree.command(
        name="items", description="Browse all items in the mystery crate pool"
    )
    async def items(interaction: discord.Interaction):
        items = database.get_all_items()
        if not items:
            await interaction.response.send_message("The pool is empty.")
            return

        if len(items) > 25:
            await interaction.response.send_message(
                f"Too many items ({len(items)}). Max 25. Contact an admin to reduce the pool.",
                ephemeral=True,
            )
            return

        view = ItemDropdownView(bot, items, interaction.user.id)

        item_id, name, url = items[0]
        embed = discord.Embed(title=name, color=discord.Color.blue())
        if url:
            embed.set_image(url=url)
        embed.set_footer(text=f"Item 1 of {len(items)} (use dropdown to change)")

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
