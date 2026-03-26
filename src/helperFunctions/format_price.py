def format_price(num: int) -> str:
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
