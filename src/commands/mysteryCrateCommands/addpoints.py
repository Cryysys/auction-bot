import discord
from discord import app_commands
import database


def register(bot):
    @bot.tree.command(name="addpoints", description="Add points to a user")
    @app_commands.describe(user="The user to reward", amount="Number of points")
    async def addpoints(
        interaction: discord.Interaction, user: discord.Member, amount: int
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "You need to be in a server to use this command.", ephemeral=True
            )
            return

        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to add points.", ephemeral=True
            )
            return
        database.add_points(user.id, amount)
        await interaction.response.send_message(
            f"✅ Added {amount} points to {user.mention}."
        )
