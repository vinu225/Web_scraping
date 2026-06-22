"""
Loads canonical `Article` objects produced directly by Module 1's
scraping pipeline.

This is the dedicated integration point between the two modules: it
accepts in-memory `shared.schemas.Article` instances, raw dicts matching
that schema, or a path to a JSON file written by Module 1's
`storage/json_storage.py` (single article or an array of articles).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

from pydantic import ValidationError

from module_2_bias_analysis.utils.exceptions import SchemaValidationError
from module_2_bias_analysis.utils.logger import get_logger
from shared.schemas import Article

logger = get_logger(__name__)


def _validate_record(raw: dict, index: int) -> Article:
    try:
        return Article.model_validate(raw)
    except ValidationError as exc:
        raise SchemaValidationError(
            f"Article at index {index} does not match the shared Article schema: {exc}"
        ) from exc


def load_article(source: Union[Article, dict, list, str, Path]) -> List[Article]:
    """
    Normalize any supported input shape into a list of validated `Article`
    objects (single article becomes a one-element list).
    """
    if isinstance(source, Article):
        logger.info("article_loader: received single in-memory Article (id=%s)", source.article_id)
        return [source]

    if isinstance(source, list) and source and isinstance(source[0], Article):
        logger.info("article_loader: received %d in-memory Article objects", len(source))
        return list(source)

    payload = _resolve_payload(source)

    if isinstance(payload, dict):
        records = [payload]
    elif isinstance(payload, list):
        records = payload
    else:
        raise SchemaValidationError(f"Article input must be an object or array, got {type(payload).__name__}")

    if not records:
        raise SchemaValidationError("Article input is empty.")

    validated = [_validate_record(record, i) for i, record in enumerate(records)]
    logger.info("article_loader: loaded %d article(s) from Module 1 output", len(validated))
    return validated


def _resolve_payload(source: Union[dict, list, str, Path]):
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

    raise SchemaValidationError(f"Unsupported Article source type: {type(source).__name__}")


__all__ = ["load_article"]
