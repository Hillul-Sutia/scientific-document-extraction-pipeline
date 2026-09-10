import json
import re


def parse_json_response(response: str):
    """Parse JSON while tolerating Markdown fences occasionally emitted by LLMs."""
    cleaned = response.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)
