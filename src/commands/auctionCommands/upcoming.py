import discord
from discord import app_commands
from datetime import datetime, timezone
import database

def register(bot):
    @bot.tree.command(name="upcoming", description="List all scheduled auctions for this channel.")
    async def upcoming(interaction: discord.Interaction):
        auctions = database.get_channel_upcoming(interaction.channel_id)
        
        if not auctions:
            await interaction.response.send_message("No upcoming auctions scheduled for this channel.", ephemeral=True)
            return

        await interaction.response.send_message("Here are the upcoming auctions for this channel:")
        
        for row in auctions:
            db_id, channel_id, seller_id, item, duration, price, inc, img, start_t_str, currency = row
            start_t = datetime.fromisoformat(start_t_str).replace(tzinfo=timezone.utc)
            unix_time = int(start_t.timestamp())

            embed = discord.Embed(
                title=f"📅 {item}",
                description=f"**Starts:** <t:{unix_time}:F> (<t:{unix_time}:R>)\n**Starting Price:** {price}",
                color=discord.Color.dark_gold()
            )
            if img:
                embed.set_thumbnail(url=img)

            view = discord.ui.View(timeout=None)
            button = discord.ui.Button(
                style=discord.ButtonStyle.secondary, 
                label="Notify Me", 
                emoji="🔔", 
                custom_id=f"sched_bell_{db_id}"
            )
            view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)
