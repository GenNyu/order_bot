import re


def parse_duration(text: str) -> int:
    """Đổi chuỗi như "1h30m", "45s", "2h5s" thành số giây; sai định dạng → ValueError."""
    if not text:
        raise ValueError("Empty string")

    pattern = r'^((\d+)h)?((\d+)m)?((\d+)s)?$'
    match = re.fullmatch(pattern, text)

    if not match:
        raise ValueError(f"Invalid duration format: {text}")

    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(4)) if match.group(4) else 0
    seconds = int(match.group(6)) if match.group(6) else 0

    # Must have at least one component
    if hours == 0 and minutes == 0 and seconds == 0:
        raise ValueError(f"Invalid duration format: {text}")

    return hours * 3600 + minutes * 60 + seconds
