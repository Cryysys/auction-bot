from datetime import timedelta
import re


def parse_duration(duration_str: str) -> timedelta:
    pattern = re.compile(r"((?P<hours>\d+)h)?((?P<minutes>\d+)m)?")
    match = pattern.fullmatch(duration_str)
    if not match:
        return timedelta()
    hours = int(match.group("hours")) if match.group("hours") else 0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    if hours == 0 and minutes == 0:
        return timedelta()
    return timedelta(hours=hours, minutes=minutes)
