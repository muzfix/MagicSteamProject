from fastapi import APIRouter, File, HTTPException, UploadFile
from app.modules.scanner.recognizer import identify_card

router = APIRouter()


@router.post("/identify")
async def identify(image: UploadFile = File(...)):
    """
    Accept a card image and return the best match from the local database.
    This endpoint is designed to also accept requests from the Android camera app —
    the contract (multipart POST, JSON response) is intentionally generic.
    """
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if image.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, or WebP images are accepted")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB hard limit
        raise HTTPException(413, "Image too large — maximum 10MB")

    return identify_card(image_bytes)
