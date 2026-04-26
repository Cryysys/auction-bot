import discord
from discord import app_commands

import database
from src.collectables_economy import get_scrap_value
from src.commands.mysteryCrateCommands.collectable_autocomplete import (
    collectable_name_autocomplete,
)


def register(bot):
    @bot.tree.command(name="scrap", description="Scrap collectables into diamonds")
    @app_commands.describe(
        collectable="Collectable to scrap",
        quantity="How many to scrap",
    )
    @app_commands.autocomplete(collectable=collectable_name_autocomplete)
    async def scrap(
        interaction: discord.Interaction,
        collectable: str,
        quantity: app_commands.Range[int, 1, 999] = 1,
    ):
        target_collectable = database.get_collectable_by_name(collectable)
        if target_collectable is None:
            await interaction.response.send_message(
                f"Collectable not found: `{collectable}`", ephemeral=True
            )
            return
        collectable_id = target_collectable[0]
        rarity = target_collectable[3]

        owned = database.get_inventory_item_quantity(interaction.user.id, collectable_id)
        if owned < quantity:
            await interaction.response.send_message(
                f"You only own **{owned}** of **{target_collectable[1]}**.",
                ephemeral=True,
            )
            return

        removed = database.remove_collectable_from_inventory(
            interaction.user.id, collectable_id, quantity
        )
        if not removed:
            await interaction.response.send_message(
                "Could not scrap item right now. Please try again.", ephemeral=True
            )
            return

        gained = get_scrap_value(rarity) * quantity
        database.add_diamonds(interaction.user.id, gained)
        total = database.get_diamonds(interaction.user.id)
        await interaction.response.send_message(
            (
                f"Scrapped **{quantity}x {target_collectable[1]}** "
                f"for **{gained}** diamonds.\nYou now have **{total}** diamonds."
            ),
            ephemeral=True,
        )
