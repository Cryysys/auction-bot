import discord
from discord import app_commands
import database

class LeaderboardView(discord.ui.View):
    def __init__(self, bot, data, user_id, user_rank, user_stats, page=0):
        super().__init__(timeout=120)
        self.bot = bot
        self.data = data
        self.invoker_id = user_id
        self.invoker_rank = user_rank
        self.invoker_stats = user_stats
        self.page = page
        self.per_page = 5 # Set to 5 for mobile clarity

    def create_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        current_slice = self.data[start:end]
        
        embed = discord.Embed(
            title="🏆 Points Leaderboard", 
            color=discord.Color.gold(),
            description="Top collectors sorted by all-time points!\n"
        )

        if not current_slice:
            embed.description = "The leaderboard is currently empty."
            return embed

        leaderboard_text = ""
        for i, row in enumerate(current_slice, start=start + 1):
            if i == 1: rank = "🥇"
            elif i == 2: rank = "🥈"
            elif i == 3: rank = "🥉"
            else: rank = f"**#{i}**"

            user = self.bot.get_user(row['user_id'])
            name = user.display_name if user else f"User {row['user_id']}"
            
            # Highlight the user who ran the command in the list
            if row['user_id'] == self.invoker_id:
                name = f"__**{name} (You)**__"
            else:
                name = f"**{name}**"

            leaderboard_text += f"{rank} {name}\nTotal: {row['cumulative_points']:,} | Current: {row['points']:,}\n\n"

        embed.description += f"\n{leaderboard_text}"

        # Personal Rank Section (Separated by a line)
        your_rank_str = "N/A" if self.invoker_rank == 0 else f"#{self.invoker_rank}"
        your_total = self.invoker_stats[1] if self.invoker_stats else 0
        your_curr = self.invoker_stats[0] if self.invoker_stats else 0
        
        embed.add_field(
            name="─── Your Position ───",
            value=f"Rank: **{your_rank_str}** | Total: {your_total:,} | Current: {your_curr:,}",
            inline=False
        )

        # Small subtext at the very bottom
        embed.add_field(
            name="\u200B",
            value="-# Redeem your current points for items in <#1481677762384101497>",
            inline=False
        )

        total_pages = max(1, (len(self.data) - 1) // self.per_page + 1)
        embed.set_footer(text=f"Page {self.page + 1} of {total_pages}")
        return embed

    def update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = (self.page + 1) * self.per_page >= len(self.data)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

def register(bot):
    @bot.tree.command(name="leaderboard", description="View the top point earners!")
    async def leaderboard(interaction: discord.Interaction):
        conn = database.get_connection() 
        cursor = conn.cursor()
        
        # 1. Fetch Top 100 for the list
        cursor.execute("""
            SELECT user_id, points, cumulative_points 
            FROM users 
            ORDER BY cumulative_points DESC 
            LIMIT 100
        """)
        rows = cursor.fetchall()

        # 2. Get Invoker's specific stats and rank
        user_id = interaction.user.id
        cursor.execute("SELECT points, cumulative_points FROM users WHERE user_id = ?", (user_id,))
        user_stats = cursor.fetchone()

        user_rank = 0
        if user_stats:
            # Rank = number of people with more points + 1
            cursor.execute("SELECT COUNT(*) FROM users WHERE cumulative_points > ?", (user_stats[1],))
            user_rank = cursor.fetchone()[0] + 1
        
        conn.close()

        if not rows:
            await interaction.response.send_message("The leaderboard is currently empty!", ephemeral=True)
            return

        data = [{'user_id': row[0], 'points': row[1], 'cumulative_points': row[2]} for row in rows]

        view = LeaderboardView(bot, data, user_id, user_rank, user_stats)
        view.update_buttons()
        await interaction.response.send_message(embed=view.create_embed(), view=view)