from typing import Optional

def owner_appears_in_text(owner: Optional[str], text: str) -> bool:
    """
    Guardrail: if owner is provided, it must be present in the source text.
    Lenient match: case-insensitive substring check.
    """
    if owner is None:
        return True
    return owner.strip().lower() in text.lower()
