from __future__ import annotations

import json
import re
from typing import List

from app.schemas.decisions import DecisionsResponse
from app.services.llm_client import get_client, get_deployment


SYSTEM = (
    "You extract meeting decisions from notes. "
    "Return ONLY valid JSON in the format: {\"decisions\": [\"...\"]}. "
    "Do not invent decisions. If none are explicit, return an empty list."
)

USER_TMPL = """Extract decisions from these meeting notes.

Rules:
- A decision must be an explicit commitment or agreement.
- Examples: lines starting with 'Decision:', 'Decided:', 'Agreed:', 'We decided to', 'We agreed to'.
- If none, return {{"decisions": []}}.
- Keep each decision concise, one per list item.
- Output MUST be valid JSON only.

MEETING NOTES:
{notes}
"""



_DECISION_LINE = re.compile(
    r"^\s*(Decision|Decided|Agreed)\s*:\s*(.+?)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _extract_decisions_locally(notes: str) -> List[str]:
    """Cheap deterministic extraction for obvious 'Decision:' style lines."""
    decisions: List[str] = []
    for m in _DECISION_LINE.finditer(notes or ""):
        txt = (m.group(2) or "").strip()
        if txt:
            decisions.append(txt)
    # de-dup while preserving order
    seen = set()
    out = []
    for d in decisions:
        if d.lower() not in seen:
            out.append(d)
            seen.add(d.lower())
    return out


def extract_decisions(notes: str, request_id: str) -> List[str]:
    if not notes or not notes.strip():
        return []

    # 1) Local extract-first (saves cost for common formats)
    local = _extract_decisions_locally(notes)
    if local:
        return local

    # 2) LLM fallback (JSON-in-text, then parse)
    client = get_client()
    deployment = get_deployment()

    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TMPL.format(notes=notes)},
        ],
        temperature=0,
    )

    raw = (resp.choices[0].message.content or "").strip()

    # Parse JSON safely
    try:
        data = json.loads(raw)
        parsed = DecisionsResponse.model_validate(data)
        return parsed.decisions
    except Exception:
        # Safe fallback (no decisions rather than hallucinating)
        return []
