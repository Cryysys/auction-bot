import discord
import database


def register(bot):
    @bot.tree.command(
        name="draw", description="Draw a random item from the pool (costs points)"
    )
    async def draw(interaction: discord.Interaction):
        if (
            not isinstance(interaction.channel, discord.TextChannel)
            or interaction.channel.name != "mystery-crates"
        ):
            await interaction.response.send_message(
                "You can only use `/draw` in #mystery-crates.", ephemeral=True
            )
            return

        cost = int(database.get_setting("draw_cost", "10"))
        user_id = interaction.user.id
        pts = database.get_points(user_id)

        if pts < cost:
            await interaction.response.send_message(
                f"You need {cost} points to draw. You have {pts}.", ephemeral=True
            )
            return

        item = database.draw_random_item()
        if not item:
            await interaction.response.send_message(
                "The pool is empty. Ask an admin to add items!", ephemeral=True
            )
            return

        database.spend_points(user_id, cost)
        database.record_draw(user_id, item[0])

        embed = discord.Embed(
            title="🎁 Mystery Box",
            description=f"You open the mystery box and get... **{item[1]}**!",
            color=discord.Color.green(),
        )
        if item[2]:
            embed.set_image(url=item[2])
        await interaction.response.send_message(embed=embed)