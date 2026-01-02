from typing import Optional
from openai import OpenAIError

from app.services.llm_client import get_client, get_deployment


def build_summary_markdown(text: str, meeting_title: Optional[str], request_id: str) -> str:
    client = get_client()
    deployment = get_deployment()

    try:
        resp = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "Summarize meeting notes as short markdown bullets."},
                {"role": "user", "content": f"Title: {meeting_title or ''}\n\nNotes:\n{text}"},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or fallback_summary(text, meeting_title)

    except (OpenAIError, Exception) as e:
        print(f"[{request_id}] summarizer_error: {type(e).__name__}: {e}")
        return fallback_summary(text, meeting_title)


def fallback_summary(text: str, meeting_title: Optional[str]) -> str:
    title = f"# {meeting_title}\n\n" if meeting_title else ""
    snippet = text.strip()
    if len(snippet) > 200:
        snippet = snippet[:200] + "..."
    return f"{title}## Summary\n- {snippet}"
