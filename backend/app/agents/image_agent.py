"""
image_agent node — extracts text from an HMI screenshot via OCR.
Gracefully degrades: if OCR fails, the pipeline continues without image context.
"""

import base64
import io

from app.agents.state import AgentState


def _ocr_from_base64(image_b64: str) -> str:
    """Attempt OCR on a base64-encoded image; return empty string on failure."""
    try:
        import pytesseract
        from PIL import Image

        image_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        return text.strip()
    except Exception:
        # OCR is best-effort; never block the pipeline
        return ""


async def image_agent_node(state: AgentState) -> dict:
    image_b64 = state.get("image_base64", "")
    if not image_b64:
        return {"ocr_text": None}

    ocr_text = _ocr_from_base64(image_b64)
    return {"ocr_text": ocr_text or None}
