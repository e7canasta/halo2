"""Entity extractors and text-to-number conversion."""

import re
from .entities import NUMBER_TEXT


def text_to_number(text: str) -> int | None:
    """Convert Spanish number words to integers.

    Examples:
        "veintidos" -> 22
        "cincuenta" -> 50

    Args:
        text: Spanish number word

    Returns:
        int or None if not found
    """
    text_lower = text.lower().strip()
    return NUMBER_TEXT.get(text_lower)


def extract_number_from_text(text: str) -> int | float | None:
    """Extract number from text (digit or word).

    Tries in order:
    1. Digit with optional decimal (22, 22.5)
    2. Spanish number word (veintidos)

    Args:
        text: Text containing number

    Returns:
        int, float, or None
    """
    # Try digit first
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        num_str = match.group(1)
        return float(num_str) if "." in num_str else int(num_str)

    # Try Spanish number words
    for word in text.lower().split():
        number = text_to_number(word)
        if number is not None:
            return number

    return None
