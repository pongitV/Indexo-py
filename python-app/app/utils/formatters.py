import datetime
from typing import Union

def format_file_size(size_bytes: Union[int, float]) -> str:
    """
    Format a byte count into human-readable representation (B, KB, MB, GB).
    """
    if size_bytes is None:
        return "0 B"
    size = float(size_bytes)
    if size < 1024:
        return f"{int(size)} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

def format_timestamp(ts: Union[float, int], fmt: str = "%d/%m/%Y %H:%M:%S") -> str:
    """
    Format a Unix epoch timestamp into localized date-time string.
    """
    if not ts:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime(fmt)
    except Exception:
        return "-"

def format_percentage(value: float) -> str:
    """
    Format a float ratio (0.0 - 1.0) into a percentage string.
    """
    return f"{value * 100:.0f}%"
