import discord
from discord import app_commands
from typing import Literal

import database
from src.collectables_economy import get_wishlist_bonus, get_wishlist_cap
from src.commands.mysteryCrateCommands.collectable_autocomplete import (
    collectable_name_autocomplete,
)


def register(bot):
    @bot.tree.command(name="wishlist", description="Manage your collectable wishlist")
    @app_commands.describe(
        action="Choose add/remove/list",
        collectable="Collectable name for add/remove",
        user="Whose wishlist to show for list",
    )
    @app_commands.autocomplete(collectable=collectable_name_autocomplete)
    async def wishlist(
        interaction: discord.Interaction,
        action: Literal["add", "remove", "list"],
        collectable: str | None = None,
        user: discord.Member | None = None,
    ):
        if action == "list":
            target = user or interaction.user
            rows = database.get_user_wishlist(target.id)
            if not rows:
                await interaction.response.send_message(
                    f"{target.display_name} has no wished collectables yet.", ephemeral=True
                )
                return

            lines = [f"**{row[1]}** - `{row[3]}` ({row[2]})" for row in rows]
            embed = discord.Embed(
                title=f"{target.display_name}'s Wishlist",
                description="\n".join(lines),
                color=discord.Color.fuchsia(),
            )
            embed.add_field(
                name="Bonus Chances",
                value=(
                    f"Natural drop wishlist bias: **{int(get_wishlist_bonus('natural') * 100)}%**\n"
                    f"Craft wishlist bias: **{int(get_wishlist_bonus('craft') * 100)}%**"
                ),
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not collectable:
            await interaction.response.send_message(
                "Please provide a collectable name for add/remove.", ephemeral=True
            )
            return

        target_collectable = database.get_collectable_by_name(collectable)
        if target_collectable is None:
            await interaction.response.send_message(
                f"Collectable not found: `{collectable}`", ephemeral=True
            )
            return
        collectable_id = target_collectable[0]

        if action == "add":
            current = database.get_user_wishlist(interaction.user.id)
            max_items = get_wishlist_cap()
            if len(current) >= max_items:
                await interaction.response.send_message(
                    f"Wishlist full ({max_items}/{max_items}). Remove one first.",
                    ephemeral=True,
                )
                return
            added = database.add_wishlist_item(interaction.user.id, collectable_id)
            if not added:
                await interaction.response.send_message(
                    "That collectable is already on your wishlist.", ephemeral=True
                )
                return
            await interaction.response.send_message(
                f"Added **{target_collectable[1]}** to your wishlist.", ephemeral=True
            )
            return

        removed = database.remove_wishlist_item(interaction.user.id, collectable_id)
        if not removed:
            await interaction.response.send_message(
                "That collectable is not on your wishlist.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Removed **{target_collectable[1]}** from your wishlist.", ephemeral=True
        )
