import json
from typing import List, Dict, Any
from pydantic import ValidationError
from openai import OpenAIError

from app.schemas.summarize import ActionItem
from app.services.llm_client import get_client, get_deployment


def parse_actions(payload: Dict[str, Any]) -> List[ActionItem]:
    try:
        raw_actions = payload.get("actions", [])
        return [ActionItem(**a) for a in raw_actions]
    except (ValidationError, TypeError, AttributeError):
        return []


def extract_actions(text: str, request_id: str) -> List[ActionItem]:
    client = get_client()
    deployment = get_deployment()

    print(f"[{request_id}] calling_llm_for_actions chars={len(text)}")

    schema = {
        "name": "action_items",
        "schema": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "owner": {"type": ["string", "null"]},
                            "due_date": {"type": ["string", "null"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["action", "owner", "due_date", "confidence"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["actions"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    try:
        resp = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract meeting action items. "
                        "Only include owner/due_date if explicitly present in the text. "
                        "Return JSON that matches the provided schema."
                    ),
                },
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_schema", "json_schema": schema},
        )

        print(f"[{request_id}] llm_returned")

        content = resp.choices[0].message.content
        print(f"[{request_id}] LLM_RAW: {content}")

        payload = json.loads(content)
        return parse_actions(payload)

    except (OpenAIError, json.JSONDecodeError, Exception) as e:
        print(f"[{request_id}] action_extractor_error: {type(e).__name__}: {e}")
        return []
