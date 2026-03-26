import discord
import database


def register(bot):
    @bot.tree.command(name="points", description="Check your current points")
    async def points(interaction: discord.Interaction):
        pts = database.get_points(interaction.user.id)
        await interaction.response.send_message(
            f"You have **{pts}** points.", ephemeral=True
        )
