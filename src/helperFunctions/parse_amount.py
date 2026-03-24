import re


def parse_amount(amount_str):
    original = amount_str.strip()
    amount_str = original.upper()
    multiplier = 1
    if amount_str.endswith("B"):
        amount_str = amount_str[:-1]
        multiplier = 1_000_000_000
    elif (
        amount_str.endswith("M")
        or amount_str.endswith("MIL")
        or amount_str.endswith("MILLION")
    ):
        amount_str = re.sub(r"(M|MIL|MILLION)$", "", amount_str)
        multiplier = 1_000_000
    try:
        value = float(amount_str)
        return int(value * multiplier), ""
    except ValueError:
        return None, None
