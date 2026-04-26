import discord
from discord import app_commands

import database
from src.collectables_economy import (
    choose_collectable_with_wishlist_bias,
    choose_rarity,
    get_craft_cost,
)


def _roll_collectable(user_id: int):
    for _ in range(10):
        rarity = choose_rarity()
        if rarity is None:
            return None
        collectable = choose_collectable_with_wishlist_bias(user_id, rarity, "craft")
        if collectable is not None:
            return collectable
    return None


def register(bot):
    @bot.tree.command(name="craft", description="Craft random collectables using diamonds")
    @app_commands.describe(amount="How many crafts to run")
    async def craft(
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 20] = 1,
    ):
        cost_per_craft = get_craft_cost()
        total_cost = cost_per_craft * amount
        diamonds = database.get_diamonds(interaction.user.id)
        if diamonds < total_cost:
            await interaction.response.send_message(
                (
                    f"You need **{total_cost}** diamonds for {amount} craft(s), "
                    f"but you only have **{diamonds}**."
                ),
                ephemeral=True,
            )
            return

        if database.get_collectable_count() <= 0:
            await interaction.response.send_message(
                "No collectables are available yet. Import the Excel pool first.",
                ephemeral=True,
            )
            return

        if not database.spend_diamonds(interaction.user.id, total_cost):
            await interaction.response.send_message(
                "Could not spend diamonds. Please try again.", ephemeral=True
            )
            return

        rolled_items = []
        for _ in range(amount):
            collectable = _roll_collectable(interaction.user.id)
            if collectable is None:
                continue
            database.add_collectable_to_inventory(interaction.user.id, collectable[0], 1)
            rolled_items.append(collectable)

        lines = [f"**{row[1]}** - `{row[3]}` ({row[2]})" for row in rolled_items]
        remaining = database.get_diamonds(interaction.user.id)
        if not lines:
            await interaction.response.send_message(
                (
                    f"Spent **{total_cost}** diamonds, but no craftable collectables were found "
                    "for the configured rarity weights."
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Crafting Bench Results",
            description="\n".join(lines[:20]),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Spent {total_cost} diamonds | Remaining {remaining}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
