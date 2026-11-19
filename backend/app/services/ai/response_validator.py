"""Response validation - the gate between "what the model said" and
what the application accepts.

WHAT THIS FILE DOES
    1. extract_json_object()  - robustly turns raw model output into a
       dict (handles ```json fences and stray commentary)
    2. validate_analysis()    - runs the result through the existing
       Pydantic AIAnalysis schema

WHY IT EXISTS
    Every provider must pass the SAME validation. When a model returns
    garbage, this raises InvalidResponseError, which the provider
    manager treats as fallback-eligible: the next provider gets the
    same request instead of the user seeing a broken page.

HOW IT CONNECTS
    provider_interface.py -> extract_json_object() / validate_analysis()
    ai_service.py         -> keeps _validate() as the legacy entry point
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.ai import AIAnalysis, parse_ai_response
from app.services.ai.ai_exceptions import InvalidResponseError

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```$", re.DOTALL)


def extract_json_object(raw: Any) -> dict:
    """Return a dict from raw model output.

    Accepts: dict (as-is), JSON string, ```json fenced string, or a
    string with commentary around the JSON object.

    Raises InvalidResponseError when no JSON object can be recovered.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        raise InvalidResponseError("The provider returned a JSON array, expected an object.")
    if not isinstance(raw, str):
        raise InvalidResponseError("The provider returned an unusable response type.")

    text = raw.strip()
    if not text:
        raise InvalidResponseError("The provider returned an empty response.")

    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.startswith("```"):
        # Fences without a clean closing marker.
        text = text.strip("`").lstrip("json").strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: slice from the first { to the final }.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise InvalidResponseError("The provider response contained no JSON object.")
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise InvalidResponseError("The provider returned malformed JSON.") from exc

    if not isinstance(payload, dict):
        raise InvalidResponseError("The provider JSON was not an object.")
    return payload


def validate_analysis(payload: Any) -> AIAnalysis:
    """Validate an analysis payload against the existing AIAnalysis schema.

    Raises InvalidResponseError (fallback-eligible) on any schema breach.
    """
    try:
        return parse_ai_response(payload)
    except (ValidationError, ValueError) as exc:
        raise InvalidResponseError("The AI response failed schema validation.") from exc


def validate_answer(raw: Any) -> str:
    """Validate a free-text answer: non-empty, trimmed, bounded."""
    if raw is None:
        raise InvalidResponseError("The provider returned no answer.")
    answer = str(raw).strip()
    if not answer:
        raise InvalidResponseError("The provider returned an empty answer.")
    return answer[:8000]
