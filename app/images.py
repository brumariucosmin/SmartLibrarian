import base64
from typing import Optional

from openai import OpenAI

from app.config import settings, require_api_key

def generate_cover(title: str, style_hint: Optional[str] = None) -> bytes:
    """
    Generează o copertă pentru carte folosind modelul de imagini.
    Returnează bytes PNG/JPEG (în funcție de model).
    """
    require_api_key()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    style = (
        style_hint
        or "minimalist, modern, clean layout, soft color palette, high contrast, readable title"
    )

    # Prompt simplu, stabil: cerem titlul pe copertă și elemente tematice
    prompt = (
        f"Design a book cover for the novel '{title}'. "
        f"Use a {style} style. Include the title text '{title}' on the cover."
    )

    result = client.images.generate(
        model=settings.IMAGE_MODEL,
        prompt=prompt,
        size=settings.IMAGE_SIZE,
        # poți adăuga: quality="high", background="transparent" (dacă suportă)
    )
    b64 = result.data[0].b64_json
    return base64.b64decode(b64)
