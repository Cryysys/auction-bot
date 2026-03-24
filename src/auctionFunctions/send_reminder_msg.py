import discord


async def send_reminder_msg(auction, time_label):
    """Helper to handle the logic of who to ping."""
    if auction.bidders:
        mentions = " ".join(f"<@{uid}>" for uid in auction.bidders)
        await auction.channel.send(f"⏰ **{time_label} left!** {mentions} final bids!")
    else:
        role = discord.utils.get(auction.channel.guild.roles, name="Auction Lover")
        mention = role.mention if role else "No bids yet."
        await auction.channel.send(f"⏰ **{time_label} left!** {mention}")
