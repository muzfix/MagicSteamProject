def identify_card(image_bytes: bytes) -> dict:
    """
    Phase 1 (now):   Returns stub — image is accepted and validated.
    Phase 2 (next):  Add perceptual hash (imagehash library) comparison
                     against pre-computed hashes of all Scryfall card images.
    Phase 3 (later): Add OCR with pytesseract + rapidfuzz for card name matching.
    Phase 4 (app):   Android camera sends image to this same endpoint — no changes needed.
    Requires pillow: pip install pillow  (add to requirements.txt when starting Phase 4)
    """
    return {
        "status": "pending_implementation",
        "message": "Image received. Card recognition activates in Phase 4 of the roadmap.",
        "confidence": 0,
        "card_name": None,
        "scryfall_id": None,
    }
