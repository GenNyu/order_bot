import re


def parse_duration(text: str) -> int:
    """Đổi chuỗi như "1h30m", "45s", "2h5s" thành số giây; sai định dạng → ValueError."""
    if not text:
        raise ValueError("Empty string")

    text = text.strip()
    pattern = r'^(\d+h)?\s*(\d+m)?\s*(\d+s)?$'
    match = re.fullmatch(pattern, text)

    if not match:
        raise ValueError(f"Invalid duration format: {text}")

    hours = minutes = seconds = 0

    for part in match.groups():
        if part:
            if part.endswith('h'):
                hours = int(part[:-1])
            elif part.endswith('m'):
                minutes = int(part[:-1])
            elif part.endswith('s'):
                seconds = int(part[:-1])

    if hours == 0 and minutes == 0 and seconds == 0:
        raise ValueError(f"Invalid duration format: {text}")

    return hours * 3600 + minutes * 60 + seconds
