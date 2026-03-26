import re


def parse_amount(amount: str) -> int:
    cleaned_amount = amount.strip().upper()

    if cleaned_amount.endswith("B"):
        return int(cleaned_amount[:-1]) * 1_000_000_000

    elif (
        cleaned_amount.endswith("M")
        or cleaned_amount.endswith("MIL")
        or cleaned_amount.endswith("MILLION")
    ):
        return int(re.sub(r"(M|MIL|MILLION)$", "", cleaned_amount)) * 1_000_000
    elif cleaned_amount.endswith("K"):
        return int(cleaned_amount[:-1]) * 1000

    return int(cleaned_amount)
