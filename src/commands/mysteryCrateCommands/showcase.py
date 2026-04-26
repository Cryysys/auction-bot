import discord
from discord import app_commands
from typing import Literal

import database
from src.commands.mysteryCrateCommands.collectable_autocomplete import (
    collectable_name_autocomplete,
)


def _build_showcase_embed(member: discord.abc.User, rows):
    embed = discord.Embed(
        title=f"{member.display_name}'s Showcase",
        color=discord.Color.gold(),
    )
    if not rows:
        embed.description = "No showcase items set yet."
        return embed
    for slot, _, name, category, rarity, _ in rows:
        embed.add_field(
            name=f"Slot {slot}",
            value=f"**{name}**\n`{rarity}` ({category})",
            inline=False,
        )
    return embed


def register(bot):
    @bot.tree.command(name="showcase", description="Set or view showcase slots")
    @app_commands.describe(
        action="Choose set/view",
        slot="Showcase slot to set (1-5)",
        collectable="Collectable name to place in slot",
        user="Whose showcase to view",
    )
    @app_commands.autocomplete(collectable=collectable_name_autocomplete)
    async def showcase(
        interaction: discord.Interaction,
        action: Literal["set", "view"],
        slot: app_commands.Range[int, 1, 5] | None = None,
        collectable: str | None = None,
        user: discord.Member | None = None,
    ):
        if action == "view":
            target = user or interaction.user
            rows = database.get_user_showcase(target.id)
            await interaction.response.send_message(
                embed=_build_showcase_embed(target, rows), ephemeral=True
            )
            return

        if slot is None or not collectable:
            await interaction.response.send_message(
                "For `set`, provide both slot (1-5) and collectable name.",
                ephemeral=True,
            )
            return

        target_collectable = database.get_collectable_by_name(collectable)
        if target_collectable is None:
            await interaction.response.send_message(
                f"Collectable not found: `{collectable}`", ephemeral=True
            )
            return
        collectable_id = target_collectable[0]
        owned_qty = database.get_inventory_item_quantity(interaction.user.id, collectable_id)
        if owned_qty <= 0:
            await interaction.response.send_message(
                "You can only showcase collectables you own.", ephemeral=True
            )
            return

        database.set_showcase_slot(interaction.user.id, slot, collectable_id)
        rows = database.get_user_showcase(interaction.user.id)
        await interaction.response.send_message(
            content=f"Set slot {slot} to **{target_collectable[1]}**.",
            embed=_build_showcase_embed(interaction.user, rows),
            ephemeral=True,
        )
