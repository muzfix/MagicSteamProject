import re

# Matches both [DD/MM/YYYY, HH:MM:SS] and DD/MM/YYYY, HH:MM - formats WhatsApp uses
_LINE = re.compile(
    r'\[?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–]\s*(.+?):\s+(.+)'
)
_PRICE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(OMR|RO|USD|\$)\b', re.IGNORECASE)


def parse_chat(text: str) -> list[dict]:
    """Parse a WhatsApp exported .txt file into a list of message dicts."""
    messages = []
    for line in text.splitlines():
        match = _LINE.match(line.strip())
        if match:
            date, time, sender, message = match.groups()
            messages.append({
                "date": date,
                "time": time,
                "sender": sender.strip(),
                "message": message.strip(),
            })
    return messages


def extract_listing_candidates(messages: list[dict], known_card_names: list[str]) -> list[dict]:
    """
    Find messages that mention a known card name and a price.
    Returns candidates — always show these to the user for review before posting.
    """
    card_names_lower = {name.lower(): name for name in known_card_names}
    candidates = []

    for msg in messages:
        text_lower = msg["message"].lower()
        found = [original for lower, original in card_names_lower.items() if lower in text_lower]
        price_match = _PRICE.search(msg["message"])

        if found and price_match:
            candidates.append({
                "sender": msg["sender"],
                "message": msg["message"],
                "detected_cards": found,
                "price": float(price_match.group(1)),
                "currency": price_match.group(2).upper(),
                "requires_review": True,
            })

    return candidates
