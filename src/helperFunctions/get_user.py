from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot


async def get_user(bot: AuctionBot, user_id: int):
    """
    Get a discord user (try cached, then API).
    Lets discord exceptions fall through.
    """
    return bot.get_user(user_id) or await bot.fetch_user(user_id)
