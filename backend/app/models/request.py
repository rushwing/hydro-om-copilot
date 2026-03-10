
from pydantic import BaseModel, Field


class DiagnosisRequest(BaseModel):
    """Incoming diagnosis request from the frontend."""

    session_id: str | None = Field(
        default=None,
        description="Session ID for continuing an existing conversation",
    )
    unit_id: str | None = Field(
        default=None,
        description="Machine unit identifier, e.g. '#1机'",
    )
    query: str = Field(
        description="Free-text symptom description from the operator",
        min_length=2,
        max_length=2000,
    )
    image_base64: str | None = Field(
        default=None,
        description="Base64-encoded HMI screenshot (JPEG/PNG)",
    )


class ImageUploadRequest(BaseModel):
    """Standalone image upload for OCR preprocessing."""

    image_base64: str = Field(description="Base64-encoded image data")
    mime_type: str = Field(default="image/jpeg", description="MIME type of the image")
