def format_number(num):
    if num >= 1_000_000_000:
        val = num / 1_000_000_000
        formatted = f"{val:.3f}".rstrip("0").rstrip(".")
        return f"{formatted}B"
    elif num >= 1_000_000:
        val = num / 1_000_000
        formatted = f"{val:.2f}".rstrip("0").rstrip(".")
        return f"{formatted}M"
    elif num >= 1_000:
        val = num / 1_000
        formatted = f"{val:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}K"
    else:
        return str(num)


def format_price(amount, currency):
    return f"{format_number(amount)}"


def plain_time(dt):
    return dt.strftime("%H:%M UTC")


def format_timestamp(dt, style="f"):
    return f"<t:{int(dt.timestamp())}:{style}>"
