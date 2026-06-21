"""
src/input/processor.py
=======================
Phase 0 — Input Processor for the Fake News Detection Pipeline.

Accepts user-submitted content (image, plain text, or URL) and resolves it
into either:
  - A direct URL  (fast-path via Gemini RIS)  → hand to BS4Extractor
  - Search keywords (slow-path via Gemini Vision LLM) → hand to Orchestrator

Supports three input modes:
  1. Image bytes / file path → full RIS + Vision LLM pipeline
  2. Plain text / claim string → skip RIS, run keyword extraction directly
  3. URL → returned as-is (fast-path, no Gemini needed)

Both image paths use: gemini-2.5-pro-preview-06-05

Workflow (image mode)
─────────────────────
Image bytes
    │
    ▼
[Step 1] Reverse Image Search  (Gemini grounding / Google Lens)
    │
    ├── Match found  → InputResult(path="fast", url=<source_url>)
    │
    └── No match    → [Step 2] Vision LLM slow-path
                            │
                            ▼
                        OCR + claim understanding + keyword generation
                            │
                            ▼
                        InputResult(path="slow", keywords=[...], claim=<str>)

Workflow (text mode)
────────────────────
Plain text
    │
    ▼
[Step 2 only] Text LLM slow-path
    │
    ▼
InputResult(path="slow", keywords=[...], claim=<str>)

Usage
─────
    from src.input.processor import InputProcessor, InputResult

    processor = InputProcessor(api_key="YOUR_GEMINI_API_KEY")

    # From image file
    result = processor.process(image_path="news_screenshot.jpg")

    # From raw bytes
    result = processor.process(image_bytes=image_bytes, mime_type="image/jpeg")

    # From plain text claim
    result = processor.process_text("PM Modi announces new AI policy in budget 2024")

    # Direct URL (no Gemini needed)
    result = processor.process_url("https://bbc.com/news/article-123")

    if result.path == "fast":
        print("Direct URL:", result.url)
    else:
        print("Claim:", result.claim)
        print("Keywords:", result.keywords)

Environment
───────────
    Set GEMINI_API_KEY in your .env or pass api_key= directly.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_MODEL = "gemini-2.5-pro-preview-06-05"

# How many times to retry a Gemini call on transient errors
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0   # seconds (doubles on each retry)

# Minimum character length of a URL returned by RIS to be considered valid
_MIN_URL_LENGTH = 15

# Supported image MIME types
_SUPPORTED_MIME = {
    "image/jpeg", "image/png", "image/webp",
    "image/gif", "image/bmp", "image/tiff",
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class InputResult:
    """
    The output of InputProcessor.process() / process_text() / process_url().

    Attributes
    ──────────
    path        : "fast"  — RIS succeeded or direct URL was provided
                  "slow"  — RIS failed / text input, Vision LLM generated keywords
    url         : Source article URL (only set when path == "fast")
    keywords    : 3-4 search keywords for the orchestrator
                  (only set when path == "slow")
    claim       : The core news claim extracted from the image/text
                  (only set when path == "slow")
    raw_ocr     : Raw text read from the image by the Vision LLM
                  (only set when path == "slow", image inputs only)
    confidence  : "high" | "medium" | "low" — how confident the LLM is
                  in the extracted claim (only set when path == "slow")
    entities    : Named entities found (people, orgs, locations, dates)
                  useful for narrowing search queries
    error       : Set if a non-fatal error occurred during processing
    input_mode  : "image" | "text" | "url" — how the input was provided
    """

    path:       Literal["fast", "slow"]
    url:        str | None              = None   # fast-path
    keywords:   list[str]               = field(default_factory=list)   # slow-path
    claim:      str | None              = None   # slow-path
    raw_ocr:    str | None              = None   # slow-path, image only
    confidence: str | None              = None   # slow-path
    entities:   dict[str, list[str]]    = field(default_factory=dict)
    error:      str | None              = None
    input_mode: Literal["image", "text", "url"] = "image"

    def __str__(self) -> str:
        if self.path == "fast":
            return f"[FAST-PATH] url={self.url} (mode={self.input_mode})"
        parts = [f"[SLOW-PATH] claim={self.claim!r}"]
        if self.keywords:
            parts.append(f"keywords={self.keywords}")
        if self.confidence:
            parts.append(f"confidence={self.confidence}")
        parts.append(f"mode={self.input_mode}")
        return "  ".join(parts)


# ── Main processor ────────────────────────────────────────────────────────────

class InputProcessor:
    """
    Phase 0 input processor.

    Entry points:
      process(image_path=...) / process(image_bytes=...)  — full image pipeline
      process_text(text)                                   — text-only slow-path
      process_url(url)                                     — direct URL, no Gemini

    Parameters
    ──────────
    api_key : Gemini API key.  Falls back to GEMINI_API_KEY env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "Gemini API key is required.  Pass api_key= or set GEMINI_API_KEY."
            )
        try:
            from google import genai
            from google.genai import types as genai_types
            self._client = genai.Client(api_key=key)
            self._genai_types = genai_types
            logger.info("InputProcessor ready (model=%s, sdk=google-genai)", _MODEL)
        except ImportError:
            raise ImportError(
                "google-genai is not installed. "
                "Run: pip install google-genai"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def process(
        self,
        image_path: str | Path | None = None,
        image_bytes: bytes | None = None,
        mime_type: str | None = None,
    ) -> InputResult:
        """
        Main entry point for image inputs.

        Parameters
        ──────────
        image_path  : Path to the image file on disk.
        image_bytes : Raw image bytes (requires mime_type).
        mime_type   : e.g. "image/jpeg".  Auto-detected from path if omitted.

        Returns
        ───────
        InputResult — see dataclass docstring above.
        """
        raw_bytes, mime = self._load_image(image_path, image_bytes, mime_type)
        logger.info("Processing image (%s, %d bytes)", mime, len(raw_bytes))

        # ── Step 1: Fast-path — Reverse Image Search via Gemini ───────────────
        logger.info("Step 1: Attempting reverse image search (fast-path)...")
        try:
            fast_url = self._reverse_image_search(raw_bytes, mime)
        except Exception as exc:
            logger.warning("RIS step raised an exception: %s — routing to slow-path", exc)
            fast_url = None

        if fast_url:
            logger.info("Fast-path succeeded → %s", fast_url)
            return InputResult(path="fast", url=fast_url, input_mode="image")

        # ── Step 2: Slow-path — Vision LLM ────────────────────────────────────
        logger.info("Step 2: RIS found no match — running Vision LLM (slow-path)...")
        try:
            slow = self._vision_llm_analysis(raw_bytes, mime)
        except Exception as exc:
            logger.error("Vision LLM step failed: %s", exc)
            return InputResult(
                path="slow",
                error=f"Both fast-path and slow-path failed: {exc}",
                input_mode="image",
            )

        slow.input_mode = "image"
        logger.info("Slow-path complete → %s", slow)
        return slow

    def process_text(self, text: str) -> InputResult:
        """
        Text-only slow-path — accepts a plain text news claim / article excerpt.
        Skips RIS entirely and extracts keywords directly via Gemini text LLM.

        Parameters
        ──────────
        text : Raw text — news headline, WhatsApp forward, claim sentence, etc.

        Returns
        ───────
        InputResult with path="slow"
        """
        if not text or not text.strip():
            return InputResult(
                path="slow",
                error="Empty text provided.",
                input_mode="text",
            )

        logger.info("Processing text input (%d chars)", len(text))
        try:
            result = self._text_llm_analysis(text.strip())
        except Exception as exc:
            logger.error("Text LLM analysis failed: %s", exc)
            # Heuristic fallback
            return InputResult(
                path="slow",
                claim=text[:200],
                keywords=_heuristic_keywords(text),
                confidence="low",
                error=f"LLM analysis failed; keywords extracted heuristically: {exc}",
                input_mode="text",
            )
        result.input_mode = "text"
        return result

    @staticmethod
    def process_url(url: str) -> InputResult:
        """
        Direct URL fast-path — no Gemini call needed.
        Validates the URL and returns it immediately.

        Parameters
        ──────────
        url : A direct article URL to scrape.

        Returns
        ───────
        InputResult with path="fast"
        """
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return InputResult(
                path="slow",
                error=f"Invalid URL: {url!r} — must start with http:// or https://",
                input_mode="url",
            )
        logger.info("Direct URL provided → %s", url)
        return InputResult(path="fast", url=url, input_mode="url")

    # ── Step 1: Reverse Image Search ──────────────────────────────────────────

    def _reverse_image_search(self, image_bytes: bytes, mime: str) -> str | None:
        """
        Ask Gemini to identify the original web source of the image.
        Returns the source URL string if found, else None.
        """
        prompt = """
You are a reverse image search engine assistant.

Examine this image carefully. Your goal is to identify if this is a screenshot
or photograph of a real, published news article or web page that exists online.

Instructions:
1. Look for any visible URL, website name, publication logo, or byline in the image.
2. Use your knowledge to identify the original source if recognizable.
3. If this appears to be a screenshot of a specific known article, return ONLY
   the most likely canonical URL of that article — nothing else.
4. If this is a meme, an edited image, a photograph, a social media post crop,
   or you cannot confidently identify a specific source URL, respond with exactly:
   NO_MATCH

CRITICAL: Respond with ONLY a single URL starting with http or https, or the
text NO_MATCH. No explanation, no punctuation, no extra text.
""".strip()

        tools = [{"google_search": {}}]

        response = self._call_gemini(
            prompt=prompt,
            image_bytes=image_bytes,
            mime=mime,
            tools=tools,
            temperature=0.0,
        )

        raw = response.strip()
        logger.debug("RIS raw response: %r", raw)

        if raw == "NO_MATCH" or not raw:
            return None

        url = _extract_first_url(raw)
        if url and len(url) >= _MIN_URL_LENGTH:
            return url

        logger.debug("RIS returned text that isn't a valid URL: %r", raw)
        return None

    # ── Step 2: Vision LLM Slow-Path ─────────────────────────────────────────

    def _vision_llm_analysis(self, image_bytes: bytes, mime: str) -> InputResult:
        """
        Full multimodal analysis: OCR → claim extraction → entities → keywords.
        Returns a populated InputResult with path="slow".
        """
        prompt = _SLOW_PATH_PROMPT
        response = self._call_gemini(
            prompt=prompt,
            image_bytes=image_bytes,
            mime=mime,
            temperature=0.1,
        )
        return _build_slow_result(response)

    # ── Text LLM Slow-Path ────────────────────────────────────────────────────

    def _text_llm_analysis(self, text: str) -> InputResult:
        """
        Text-only variant: given raw text, extract claim + keywords via Gemini.
        """
        prompt = f"""
You are an expert news analyst and fact-checking assistant.

Below is raw text from a news claim, article excerpt, or social media post.
Analyse it and respond ONLY in the exact JSON format specified.

TEXT:
\"\"\"
{text}
\"\"\"

Perform these tasks and respond ONLY with JSON:

TASK 1 — CLAIM: Identify the single core news claim or assertion.
Write it as one clear, specific, factual sentence.

TASK 2 — ENTITIES: Extract named entities:
  - people: names of individuals mentioned
  - organizations: companies, governments, institutions
  - locations: countries, cities, places
  - dates: any specific dates or time references

TASK 3 — KEYWORDS: Generate exactly 3 to 4 search engine keywords that would
find credible news articles about this specific claim. Make them specific.

TASK 4 — CONFIDENCE: Rate your confidence as "high", "medium", or "low".

Respond ONLY with this JSON and nothing else:
{{
  "claim": "<one sentence core claim>",
  "entities": {{
    "people": [],
    "organizations": [],
    "locations": [],
    "dates": []
  }},
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "confidence": "high|medium|low"
}}
""".strip()

        response = self._call_gemini_text(prompt=prompt, temperature=0.1)
        return _build_slow_result(response, include_ocr=False)

    # ── Gemini call wrappers ──────────────────────────────────────────────────

    def _call_gemini(
        self,
        prompt: str,
        image_bytes: bytes,
        mime: str,
        tools: list | None = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Call Gemini with an image + prompt using the google.genai SDK.
        Retries on transient errors. Returns the text response string.
        """
        types = self._genai_types

        # Build the inline image part
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=2048,
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ],
        )

        if tools:
            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=2048,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                safety_settings=config.safety_settings,
            )

        return self._retry_call(
            lambda: self._client.models.generate_content(
                model=_MODEL,
                contents=[prompt, image_part],
                config=config,
            ).text or ""
        )

    def _call_gemini_text(self, prompt: str, temperature: float = 0.1) -> str:
        """
        Call Gemini text-only (no image) using the google.genai SDK.
        Retries on transient errors.
        """
        types = self._genai_types

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=2048,
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ],
        )

        return self._retry_call(
            lambda: self._client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=config,
            ).text or ""
        )

    def _retry_call(self, fn) -> str:
        """Run fn() with exponential-backoff retry on transient Gemini errors."""
        delay = _RETRY_DELAY
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.debug("Gemini call attempt %d/%d", attempt, _MAX_RETRIES)
                return fn()
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if any(k in err_str for k in ("429", "500", "503", "timeout", "rate")):
                    logger.warning(
                        "Transient error on attempt %d: %s — retrying in %.1fs",
                        attempt, exc, delay,
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise  # non-retryable

        raise RuntimeError(
            f"Gemini call failed after {_MAX_RETRIES} attempts: {last_exc}"
        )

    # ── Image loader ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_image(
        image_path: str | Path | None,
        image_bytes: bytes | None,
        mime_type: str | None,
    ) -> tuple[bytes, str]:
        """Load image from path or raw bytes. Returns (bytes, mime_type)."""
        if image_path is not None:
            path = Path(image_path)
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {path}")
            raw = path.read_bytes()
            mime = mime_type or mimetypes.guess_type(str(path))[0] or "image/jpeg"
        elif image_bytes is not None:
            raw = image_bytes
            mime = mime_type or "image/jpeg"
        else:
            raise ValueError("Provide either image_path or image_bytes.")

        if mime not in _SUPPORTED_MIME:
            logger.warning("MIME type %r may not be supported by Gemini", mime)

        return raw, mime


# ── Shared slow-path prompt ───────────────────────────────────────────────────

_SLOW_PATH_PROMPT = """
You are an expert news analyst and fact-checking assistant.

Examine this image. It may be a news article screenshot, a viral social media
post, a meme with a news claim, a WhatsApp forward, or a photograph of a
printed article.

Perform these four tasks and respond ONLY in the exact JSON format below:

TASK 1 — OCR: Read and transcribe ALL visible text in the image exactly as it
appears. Include headlines, body text, captions, watermarks, usernames, dates.

TASK 2 — CLAIM: Identify the single core news claim or assertion this image
is making or showing. Write it as one clear, specific, factual sentence.

TASK 3 — ENTITIES: Extract named entities from the text:
  - people: names of individuals mentioned
  - organizations: companies, governments, institutions
  - locations: countries, cities, places
  - dates: any specific dates or time references

TASK 4 — KEYWORDS: Generate exactly 3 to 4 search engine keywords that would
find credible news articles about this specific claim. Make them specific, not
generic. Prefer named entities + the core action/event.

TASK 5 — CONFIDENCE: Rate your confidence in the extracted claim as one of:
  "high"   — clear text, unambiguous claim
  "medium" — some text readable, claim inferred
  "low"    — image is unclear, heavily edited, or claim is ambiguous

Respond ONLY with this JSON and nothing else:
{
  "ocr_text": "<all visible text transcribed>",
  "claim": "<one sentence core claim>",
  "entities": {
    "people": [],
    "organizations": [],
    "locations": [],
    "dates": []
  },
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "confidence": "high|medium|low"
}
""".strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_slow_result(response: str, include_ocr: bool = True) -> InputResult:
    """Parse Gemini JSON response into an InputResult."""
    logger.debug("Vision/Text LLM raw response: %r", response[:300])
    parsed = _parse_json_response(response)

    if parsed is None:
        logger.warning("JSON parse failed — extracting keywords heuristically")
        return InputResult(
            path="slow",
            raw_ocr=response if include_ocr else None,
            claim=None,
            keywords=_heuristic_keywords(response),
            confidence="low",
            error="JSON parse failed; keywords extracted heuristically",
        )

    return InputResult(
        path="slow",
        raw_ocr=parsed.get("ocr_text") if include_ocr else None,
        claim=parsed.get("claim"),
        keywords=parsed.get("keywords", [])[:4],
        confidence=parsed.get("confidence", "medium"),
        entities=parsed.get("entities", {}),
    )


def _extract_first_url(text: str) -> str | None:
    """Extract the first http/https URL from a string."""
    match = re.search(r"https?://[^\s\"'<>]+", text)
    return match.group(0).rstrip(".,)") if match else None


def _parse_json_response(text: str) -> dict | None:
    """
    Safely parse the JSON block from a Gemini response.
    Handles markdown code fences and leading/trailing noise.
    """
    import json

    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        return None

    json_str = cleaned[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.debug("JSON decode error: %s", exc)
        return None


def _heuristic_keywords(text: str) -> list[str]:
    """
    Last-resort keyword extraction when JSON parsing fails entirely.
    Pulls capitalised phrases and long words as rough keywords.
    """
    phrases = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
    _STOP = {"about", "after", "again", "before", "between", "should", "because"}
    words = [
        w for w in re.findall(r"\b[a-zA-Z]{7,}\b", text)
        if w.lower() not in _STOP
    ]
    combined = list(dict.fromkeys(phrases + words))
    return combined[:4] if combined else ["news", "claim", "fact check"]


# ── CLI for quick testing ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Phase 0 Input Processor — test an image or text claim"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", help="Path to the image file")
    group.add_argument("--text", help="Plain text news claim to process")
    group.add_argument("--url", help="Direct article URL (fast-path)")
    parser.add_argument(
        "--api-key",
        default=os.getenv("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )
    args = parser.parse_args()

    if args.image or args.text:
        if not args.api_key:
            print("ERROR: Set GEMINI_API_KEY or pass --api-key", file=sys.stderr)
            sys.exit(1)
        processor = InputProcessor(api_key=args.api_key)

    if args.image:
        result = processor.process(image_path=args.image)
    elif args.text:
        result = processor.process_text(args.text)
    else:
        result = InputProcessor.process_url(args.url)

    print("\n" + "═" * 60)
    print("RESULT:", result)
    print("═" * 60)

    if result.path == "fast":
        print(f"\n→ Hand this URL to BS4Extractor:\n  {result.url}")
    else:
        print(f"\n→ Claim    : {result.claim}")
        print(f"  Keywords : {result.keywords}")
        print(f"  Entities : {result.entities}")
        print(f"  Confidence: {result.confidence}")
        if result.raw_ocr:
            print(f"\n  OCR text (first 300 chars):\n  {result.raw_ocr[:300]}")
        print(f"\n→ Hand keywords to DuckDuckGoSearcher / NewsAPI")

    if result.error:
        print(f"\n⚠ Non-fatal error: {result.error}")
