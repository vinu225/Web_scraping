"""
Loads a single JSON article object or a JSON array, with schema validation.

Accepts three input shapes:
1. A Python dict already parsed from JSON (e.g. from a FastAPI request body).
2. A raw JSON string (object or array).
3. A path to a `.json` file on disk (object or array).

Every record is validated against `schemas.requests.JSONArticleInput`
before being handed to the pipeline, so malformed input fails fast with a
clear `SchemaValidationError` rather than propagating `None`s downstream.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

from pydantic import ValidationError

from module_2_bias_analysis.schemas.requests import JSONArticleInput
from module_2_bias_analysis.utils.exceptions import SchemaValidationError
from module_2_bias_analysis.utils.logger import get_logger

logger = get_logger(__name__)


def _validate_record(raw: dict, index: int) -> JSONArticleInput:
    try:
        return JSONArticleInput.model_validate(raw)
    except ValidationError as exc:
        raise SchemaValidationError(f"Article at index {index} failed schema validation: {exc}") from exc


def load_json(source: Union[str, dict, list, Path]) -> List[JSONArticleInput]:
    """
    Normalize any of the supported JSON input shapes into a list of
    validated `JSONArticleInput` objects (a single article becomes a
    one-element list, so callers always iterate uniformly).
    """
    payload = _resolve_payload(source)

    if isinstance(payload, dict):
        records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise SchemaValidationError(
            f"JSON input must be an object or array, got {type(payload).__name__}"
        )

    if not records:
        raise SchemaValidationError("JSON input array is empty.")

    validated = [_validate_record(record, i) for i, record in enumerate(records)]
    logger.info("json_loader: loaded %d article(s)", len(validated))
    return validated


def _resolve_payload(source: Union[str, dict, list, Path]):
    """Turn a dict/list/JSON-string/file-path into a parsed JSON object."""
    if isinstance(source, (dict, list)):
        return source

    if isinstance(source, Path) or (isinstance(source, str) and source.strip().endswith(".json") and Path(source).exists()):
        path = Path(source)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(f"File '{path}' is not valid JSON: {exc}") from exc

    if isinstance(source, str):
        try:
            return json.loads(source)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(f"Input string is not valid JSON: {exc}") from exc

    raise SchemaValidationError(f"Unsupported JSON source type: {type(source).__name__}")


__all__ = ["load_json"]
