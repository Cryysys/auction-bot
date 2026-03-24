import discord
from discord import app_commands
import database


def register(bot):
    @bot.tree.command(name="removepoints", description="Remove points from a user")
    @app_commands.describe(user="The user", amount="Number of points")
    async def removepoints(
        interaction: discord.Interaction, user: discord.Member, amount: int
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to remove points.", ephemeral=True
            )
            return
        if database.remove_points(user.id, amount):
            await interaction.response.send_message(
                f"✅ Removed {amount} points from {user.mention}."
            )
        else:
            await interaction.response.send_message(
                f"❌ {user.mention} doesn't have enough points.", ephemeral=True
            )
