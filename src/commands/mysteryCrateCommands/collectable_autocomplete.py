from discord import app_commands

import database


async def collectable_name_autocomplete(_, current: str):
    rows = database.search_collectables_by_name(current, limit=25)
    return [app_commands.Choice(name=row[1], value=row[1]) for row in rows[:25]]
