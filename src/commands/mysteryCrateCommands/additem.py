import discord
from discord import app_commands
import database


def register(bot):
    @bot.tree.command(
        name="additem", description="Add an item to the mystery crate pool"
    )
    @app_commands.describe(
        name="Item name",
        image="Upload an image (optional)",
        image_url="Or provide an image URL (optional)",
    )
    async def additem(
        interaction: discord.Interaction,
        name: str,
        image: discord.Attachment | None = None,
        image_url: str | None = None,
    ):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "You need to be in a server to use this command.", ephemeral=True
            )
            return

        role = discord.utils.get(interaction.guild.roles, name="Cryysys")
        if role not in interaction.user.roles:
            await interaction.response.send_message(
                "You need the **Cryysys** role to add items.", ephemeral=True
            )
            return

        if image and image_url:
            await interaction.response.send_message(
                "Please provide either an uploaded image or a URL, not both.",
                ephemeral=True,
            )
            return

        if not image and not image_url:
            await interaction.response.send_message(
                "You must provide either an image upload or an image URL.",
                ephemeral=True,
            )
            return

        final_url = image.url if image else image_url or ""
        item_id = database.add_item(name, final_url)
        await interaction.response.send_message(
            f"✅ Item added with ID #{item_id}: {name}"
        )
