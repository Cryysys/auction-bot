import discord
from discord import app_commands
import database


def register(bot):
    @bot.tree.command(
        name="removeitem", description="Remove an item from the pool by ID"
    )
    @app_commands.describe(item_id="The ID of the item to remove")
    async def removeitem(interaction: discord.Interaction, item_id: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to remove items.", ephemeral=True
            )
            return
        if database.remove_item(item_id):
            await interaction.response.send_message(f"✅ Item #{item_id} removed.")
        else:
            await interaction.response.send_message(
                f"❌ Item #{item_id} not found.", ephemeral=True
            )
