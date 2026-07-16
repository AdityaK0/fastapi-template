import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "profile"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class LocalAvatarStorage:
    """Local filesystem avatar storage. Replace this class with S3Storage or CloudinaryStorage later."""

    def __init__(self):
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, file: UploadFile) -> str:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Only JPG, PNG and WEBP are allowed")

        contents = file.file.read()
        if len(contents) > MAX_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="File too large. Max 5MB")

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
        filename = f"{uuid.uuid4().hex}.{ext}"
        dest = UPLOAD_DIR / filename
        dest.write_bytes(contents)
        return f"uploads/profile/{filename}"

    def delete(self, path: str) -> None:
        full = Path(__file__).resolve().parent.parent / path
        if full.exists():
            full.unlink(missing_ok=True)

    def get_url(self, path: str, base_url: str = "http://localhost:8001") -> str:
        return f"{base_url}/{path}"


# Singleton — swap implementation here for S3/Cloudinary
avatar_storage = LocalAvatarStorage()
