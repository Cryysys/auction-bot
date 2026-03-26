import discord
import os
from dotenv import load_dotenv
import database

from src.AuctionBot import AuctionBot

from src.commands.auctionCommands import bid
from src.commands.auctionCommands import endauction
from src.commands.auctionCommands import on_raw_reaction_add
from src.commands.auctionCommands import quickbid
from src.commands.auctionCommands import startauction
from src.commands.auctionCommands import status
from src.commands.auctionCommands import upcoming

from src.commands.mysteryCrateCommands import additem
from src.commands.mysteryCrateCommands import addpoints
from src.commands.mysteryCrateCommands import draw
from src.commands.mysteryCrateCommands import items
from src.commands.mysteryCrateCommands import points
from src.commands.mysteryCrateCommands import removeitem
from src.commands.mysteryCrateCommands import removepoints
from src.commands.mysteryCrateCommands import setdrawcost


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = AuctionBot(intents)

# ========== SLASH COMMANDS (AUCTIONS) ==========

startauction.register(bot)
bid.register(bot)
quickbid.register(bot)
status.register(bot)
endauction.register(bot)
on_raw_reaction_add.register(bot)
upcoming.register(bot)

# ========== MYSTERY CRATE COMMANDS ==========

additem.register(bot)
removeitem.register(bot)
addpoints.register(bot)
removepoints.register(bot)
setdrawcost.register(bot)
items.register(bot)
points.register(bot)
draw.register(bot)


# ========== BOT START ==========


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")

    if TOKEN is None:
        print("DISCORD_TOKEN is required in .env file")
        os._exit(1)

    database.init_db()
    bot.run(TOKEN)
