import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse the JSON payload of an LLM answer.

    Models often wrap JSON in Markdown fences or add a sentence before or
    after it. Tries, in order: the raw text, fenced blocks, then the first
    decodable object/array found in the text.
    """
    if not text or not text.strip():
        raise ValueError("Empty model output")
    candidate = text.strip().lstrip("﻿")

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    for block in _FENCE_RE.findall(candidate):
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for index, char in enumerate(candidate):
        if char in "{[":
            try:
                value, _ = decoder.raw_decode(candidate, index)
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON object found in model output")
