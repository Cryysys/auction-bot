from datetime import timedelta
import re


def parse_duration(duration_str: str) -> timedelta | None:
    pattern = re.compile(r"((?P<hours>\d+)h)?((?P<minutes>\d+)m)?")
    match = pattern.fullmatch(duration_str)
    if not match:
        return None
    hours = int(match.group("hours")) if match.group("hours") else 0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    if hours == 0 and minutes == 0:
        return None
    return timedelta(hours=hours, minutes=minutes)
