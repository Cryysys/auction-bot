import discord
from discord import app_commands
import database


def register(bot):
    @bot.tree.command(
        name="setdrawcost", description="Set the points required per draw"
    )
    @app_commands.describe(amount="Points per draw")
    async def setdrawcost(interaction: discord.Interaction, amount: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to set draw cost.", ephemeral=True
            )
            return
        database.set_setting("draw_cost", str(amount))
        await interaction.response.send_message(f"✅ Draw cost set to {amount} points.")
