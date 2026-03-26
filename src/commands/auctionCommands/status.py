import discord

from src.helperFunctions.formatting_helpers import format_price, format_timestamp


def register(bot):
    @bot.tree.command(name="status", description="Show current auction status.")
    async def status(interaction: discord.Interaction):
        auction = bot.auctions.get(interaction.channel_id)
        if not auction:
            await interaction.response.send_message(
                "No auction running in this channel.", ephemeral=True
            )
            return

        highest = auction.highest_bidder.mention if auction.highest_bidder else "None"
        embed = discord.Embed(
            title=f"Auction: {auction.item_name}",
            description=(
                f"**Current Price:** {format_price(auction.current_price, auction.currency_symbol)}\n"
                f"**Highest Bidder:** {highest}\n"
                f"**Ends:** {format_timestamp(auction.end_time, 'R')}"
            ),
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed)
