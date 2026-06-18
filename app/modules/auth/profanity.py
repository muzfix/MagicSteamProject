"""
Guild tag profanity filter.
Blocks obvious slurs and profanity that fit in 2-4 characters.
"""

import re

_BANNED: frozenset[str] = frozenset({
    # Profanity
    "ass", "ars", "fck", "fuc", "fuk", "fux",
    "sht", "shxt", "sex", "xxx",
    "cum", "cuk",
    "cck", "cock", "coc",
    "dic", "dick", "dik",
    "pns", "piss", "pis",
    "prn", "porn",
    "kys",
    "slut", "hoe",
    "cunt", "cun",
    "twat",
    "tits", "tit",
    # Slurs (racial, sexual orientation)
    "fag", "fagg",
    "dyke",
    "nig", "nigg",
    "kike", "kik",
    "spic", "spi",
    "chink", "chi",  # chi alone is probably fine but chink is not
    "gook", "goo",
    "wop",
    "rape", "rap",   # rap music is fine but filter at 3 chars would be bad — keep "rape" only
    # Hate symbols
    "kkk", "nazi", "naz",
    # Self-harm
    "die",           # uncomment if you want to block — may be too aggressive
    "kms",
})

# Also block if the tag contains any of these patterns as a substring
_BANNED_SUBSTRINGS: frozenset[str] = frozenset({
    "fuk", "fck", "fuc", "ass", "cun", "kys", "nig", "kik", "kkk",
})

_TAG_PATTERN = re.compile(r'^[A-Za-z0-9]{2,4}$')


def is_valid_tag(tag: str) -> tuple[bool, str]:
    """Return (is_valid, reason). Valid tags are 2-4 alphanumeric chars, not banned."""
    if not tag:
        return True, ""  # null/empty is allowed (removes the tag)
    if not _TAG_PATTERN.match(tag):
        return False, "Tag must be 2-4 letters or numbers only."
    lower = tag.lower()
    if lower in _BANNED:
        return False, "That tag is not allowed."
    for sub in _BANNED_SUBSTRINGS:
        if sub in lower:
            return False, "That tag is not allowed."
    return True, ""
