from discord import TextChannel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.AuctionBot import AuctionBot


async def get_text_channel(bot: AuctionBot, channel_id: int) -> TextChannel:
    """
    Get a text channel (try cached, then API), raises Exception when the channel is a different type.
    Lets discord exceptions fall through.
    """
    channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    if not isinstance(channel, TextChannel):
        raise Exception(
            f"Channel with id {channel_id} is not of type discord.TextChannel"
        )
    return channel
