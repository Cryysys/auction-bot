from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import discord

from src.helperFunctions.format_price import format_price
from src.helperFunctions.format_timestamp import format_timestamp

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot
    from src.Auction import Auction

async def notify_proxy_spent(bot, user_id, auction, jump_url: str = None):
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        link_text = f"\n\n[Click here to jump to the auction]({jump_url})" if jump_url else ""
        
        embed = discord.Embed(
            title="❌ Auto-Bid Outbid",
            description=(
                f"Your Auto-Bid for **{auction.item_name}** in {auction.channel.mention} "
                f"has been outbid!{link_text}"
            ),
            color=discord.Color.red()
        )
        await user.send(embed=embed)
    except Exception:
        pass

async def process_bid(
    bot: AuctionBot,
    interaction: discord.Interaction,
    auction: Auction,
    bid_value: int,
    embed_title: str,
) -> None:
    # --- FIX 1: DEFER IMMEDIATELY ---
    # This stops the "Application did not respond" error by telling Discord we're working on it.
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    now = datetime.now(timezone.utc)
    if now >= auction.end_time:
        await interaction.followup.send("This auction has already ended.", ephemeral=True)
        return

    # 1. Anti-Snipe
    extended = False
    if (auction.end_time - now).total_seconds() < 300:
        auction.end_time = now + timedelta(minutes=5)
        extended = True

    # 2. PROXY RESOLUTION LOGIC
    command_user = interaction.user
    is_maxbid_trigger = (embed_title == "Proxy Auto-Bid!")
    winning_user = command_user
    winning_price = bid_value
    proxy_war_occurred = False
    spent_proxies = []

    while True:
        competitors = {uid: amt for uid, amt in auction.max_bids.items() if uid != winning_user.id}
        if not competitors:
            break
            
        top_uid = max(competitors, key=competitors.get)
        top_val = competitors[top_uid]
        needed_to_beat = winning_price + auction.min_increment
        
        if top_val >= needed_to_beat:
            winning_price = needed_to_beat
            winning_user = bot.get_user(top_uid) or await bot.fetch_user(top_uid)
            proxy_war_occurred = True
        elif top_val > winning_price:
            winning_price = top_val
            winning_user = bot.get_user(top_uid) or await bot.fetch_user(top_uid)
            proxy_war_occurred = True
            spent_proxies.append(top_uid)
            del auction.max_bids[top_uid]
        else:
            spent_proxies.append(top_uid)
            del auction.max_bids[top_uid]

    old_highest = getattr(auction.highest_bidder, "id", None) if auction.highest_bidder else None
    auction.current_price = winning_price
    auction.highest_bidder = winning_user
    auction.bidders.add(winning_user.id)

    # 3. MESSAGE CONSTRUCTION
    display_title = "🔨 New Bid Placed"
    display_color = discord.Color.blue()
    status_msg = ""

    if winning_user.id == command_user.id:
        if is_maxbid_trigger:
            if proxy_war_occurred:
                display_title = "⚔️ Auto-Bid Battle"
                display_color = discord.Color.gold()
                status_msg = f"{command_user.display_name} set a new Auto-Bid and **outmatched** the previous Auto-Bidder!\n\n🚀 **{command_user.display_name} has taken the lead.**"
            else:
                display_title = "🤖 Auto-Bid Activated"
                display_color = discord.Color.green()
                status_msg = f"{command_user.display_name} set a secret max budget and is now leading."
        else:
            status_msg = f"{command_user.display_name} placed a manual bid."
    else:
        if is_maxbid_trigger:
            display_title = "⚔️ Auto-Bid Battle"
            display_color = discord.Color.orange()
            status_msg = f"{command_user.display_name} set a new Auto-Bid, but it was **outmatched** by {winning_user.display_name}'s existing Auto-Bid.\n\n🛡️ **{winning_user.display_name} remains in the lead.**"
        else:
            display_title = "🛡️ Auto-Bid Defended"
            display_color = discord.Color.purple()
            status_msg = f"{command_user.display_name} tried to bid, but was **instantly outbid** by {winning_user.display_name}'s active Auto-Bid."

    # 4. SEND EMBEDS
    # Update Master Embed
    master_embed = discord.Embed(
        title=f"🎨 Auction: {auction.item_name}",
        description=f"**Seller:** {auction.seller.mention}\n**Ends:** {format_timestamp(auction.end_time, 'R')}",
        color=discord.Color.blue(),
    )
    master_embed.add_field(name="Current Bid", value=format_price(auction.current_price), inline=True)
    master_embed.add_field(name="Min Increment", value=format_price(auction.min_increment), inline=True)
    master_embed.add_field(name="Highest Bidder", value=auction.highest_bidder.mention, inline=False)
    if auction.image_url: master_embed.set_thumbnail(url=auction.image_url)
    
    if auction.message: 
        try: await auction.message.edit(embed=master_embed)
        except: pass

    # --- FIX 2: REWRITE DESCRIPTION STRING ---
    # This prevents the 'str' object is not callable SyntaxWarning
    sniping_text = "\n\n⏰ **Anti-sniping!** Timer reset to 5:00." if extended else ""
    
    desc_content = (
        f"**Item:** {auction.item_name}\n"
        f"**Current Lead:** {winning_user.mention}\n"
        f"**Price:** {format_price(winning_price)}\n"
        f"**Ends:** {format_timestamp(auction.end_time, 'R')}\n\n"
        f"{status_msg}{sniping_text}"
    )

    notif_embed = discord.Embed(
        title=display_title,
        description=desc_content,
        color=display_color
    )
    notif_embed.set_footer(text="Want to bid while offline? Use /maxbid [amount]")
    if auction.image_url: notif_embed.set_thumbnail(url=auction.image_url)

    msg = await auction.channel.send(embed=notif_embed)
    await msg.add_reaction("🔔")
    auction.last_bid_message = msg

    # Followup response
    followup_text = "✅ Bid processed!" if winning_user.id == command_user.id else "⚠️ You were immediately outbid by an existing Auto-Bid!"
    await interaction.followup.send(followup_text, ephemeral=True)

    # 5. DM Notifications
    for uid in spent_proxies:
        if is_maxbid_trigger and uid == command_user.id:
            continue
        await notify_proxy_spent(bot, uid, auction, msg.jump_url)

    if old_highest and old_highest != winning_user.id:
        pref_key = (auction.channel.id, old_highest)
        if bot.notification_prefs.get(pref_key, False):
            try:
                old_u = bot.get_user(old_highest) or await bot.fetch_user(old_highest)
                await old_u.send(
                    f"You've been outbid for **{auction.item_name}**! "
                    f"New price: {format_price(winning_price)}.\n"
                    f"Link: {msg.jump_url}"
                )
            except: pass