import discord
from discord import app_commands
from src.helperFunctions.parse_amount import parse_amount
from src.helperFunctions.format_price import format_price
from src.auctionFunctions.process_bid import process_bid

def register(bot):
    @bot.tree.command(name="maxbid", description="Set a secret maximum bid. The bot auto-bids for you.")
    @app_commands.describe(amount="The absolute maximum amount you are willing to pay.")
    async def maxbid(interaction: discord.Interaction, amount: str):
        auction = bot.auctions.get(interaction.channel_id)
        if not auction:
            await interaction.response.send_message("No auction is running here.", ephemeral=True)
            return

        if interaction.user == auction.seller:
            await interaction.response.send_message("You cannot bid on your own auction.", ephemeral=True)
            return

        # FIXED: Removed the tuple unpacking to match your parse_amount function
        try:
            val = parse_amount(amount)
        except ValueError:
            await interaction.response.send_message("Invalid bid format. Example: 150, 5M", ephemeral=True)
            return

        needed_bid = auction.current_price + auction.min_increment
        if auction.highest_bidder is None:
            needed_bid = auction.current_price

        if val < needed_bid:
            await interaction.response.send_message(f"Max bid must be at least **{format_price(needed_bid)}** to enter the auction.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        async with auction.bid_lock:
            # Register the proxy
            auction.max_bids[interaction.user.id] = val
            auction.bidders.add(interaction.user.id) 

            # If they aren't currently leading, trigger the proxy engine to assert their dominance
            if getattr(auction.highest_bidder, "id", None) != interaction.user.id:
                try:
                    await process_bid(bot, interaction, auction, needed_bid, "Proxy Auto-Bid!")
                    # process_bid handles its own followup, so we return here to avoid double-sending
                    return 
                except Exception as e:
                    print(f"Error in maxbid process: {e}")
                    await interaction.followup.send("An error occurred while setting your max bid.", ephemeral=True)
                    return

            await interaction.followup.send(f"✅ Your secret Max Bid of **{format_price(val)}** is set. The bot will defend your position!", ephemeral=True)
