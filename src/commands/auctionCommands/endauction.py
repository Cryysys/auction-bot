import discord

from src.auctionFunctions.finalize_auction import finalize_auction


def register(bot):
    @bot.tree.command(
        name="endauction", description="Force-end the current auction (seller only)."
    )
    async def endauction(interaction: discord.Interaction):
        # Retrieve the auction object for this channel
        auction = bot.auctions.get(interaction.channel_id)

        if not auction:
            await interaction.response.send_message(
                "No auction running in this channel.", ephemeral=True
            )
            return

        # Check if the user is the seller or an admin
        if interaction.user != auction.seller and not (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "Only the seller or an admin can force-end the auction.", ephemeral=True
            )
            return

        # Cancel background tasks immediately to prevent duplicate "End" triggers
        if auction.end_task and not auction.end_task.done():
            auction.end_task.cancel()
        if auction.reminder_task and not auction.reminder_task.done():
            auction.reminder_task.cancel()

        # We pass the WHOLE auction object, ensuring we have the direct channel reference
        await finalize_auction(bot, auction, forced=True)

        # Simple confirmation for the user who ran the command
        await interaction.response.send_message("Auction ended by moderator/seller.")
