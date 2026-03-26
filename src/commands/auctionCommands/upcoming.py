from datetime import datetime, timezone
import database
import discord


def register(bot):
    @bot.tree.command(
        name="upcoming", description="List all scheduled auctions for this channel."
    )
    async def upcoming(interaction: discord.Interaction):
        upcomingAuctions = database.get_channel_upcoming(interaction.channel_id)

        if not upcomingAuctions:
            await interaction.response.send_message(
                "No upcoming auctions scheduled for this channel.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Here are the upcoming auctions for this channel:"
        )

        for upcomingAuction in upcomingAuctions:
            (
                db_id,
                channel_id,
                seller_id,
                item_name,
                duration,
                start_price,
                min_increment,
                image_url,
                start_time,
            ) = upcomingAuction
            unix_start_time = int(
                datetime.fromisoformat(start_time)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )

            embed = discord.Embed(
                title=f"📅 {item_name}",
                description=f"**Starts:** <t:{unix_start_time}:F> (<t:{unix_start_time}:R>)\n**Starting Price:** {start_price}",
                color=discord.Color.dark_gold(),
            )
            if image_url:
                embed.set_thumbnail(url=image_url)

            view = discord.ui.View(timeout=None)
            button: discord.ui.Button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Notify Me",
                emoji="🔔",
                custom_id=f"sched_bell_{db_id}",
            )
            view.add_item(button)

            await interaction.followup.send(embed=embed, view=view)
