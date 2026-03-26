from datetime import datetime


def format_timestamp(dt: datetime, style: str = "f") -> str:
    return f"<t:{int(dt.timestamp())}:{style}>"
