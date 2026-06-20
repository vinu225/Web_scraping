# 08 — Preprocessing

## Files Covered
- [`src/preprocess/html_cleaner.py`](../src/preprocess/html_cleaner.py)
- [`src/preprocess/text_cleaner.py`](../src/preprocess/text_cleaner.py)
- [`src/preprocess/unicode_normalizer.py`](../src/preprocess/unicode_normalizer.py)
- [`src/preprocess/language_detector.py`](../src/preprocess/language_detector.py)

---

## Preprocessing Pipeline

```mermaid
flowchart TD
    RAW_HTML["Raw HTML<br/>(BeautifulSoup object)"] --> HC["html_cleaner.clean_html()"]

    subgraph "HTML Cleaning (removes noise tags)"
        HC --> RT["Remove: script, style, noscript,<br/>iframe, form, button, canvas, svg"]
        RT --> RC["Remove HTML comments"]
        RC --> RS["Remove semantic noise:<br/>nav, header, footer, aside, figure"]
        RS --> RP["Remove div/section/span<br/>matching noise CSS patterns"]
    end

    HC --> CLEAN_SOUP["Cleaned BeautifulSoup"]
    CLEAN_SOUP --> EXTRACT["content_extractor.extract_body()"]
    EXTRACT --> RAW_TEXT["Raw extracted text string"]

    subgraph "Text Cleaning Pipeline"
        RAW_TEXT --> UN["unicode_normalizer.normalize()"]
        UN --> FTFY["1. ftfy.fix_text() — repair mojibake"]
        FTFY --> NFC["2. unicodedata.normalize('NFC')"]
        NFC --> SQ["3. Replace smart quotes '' "" → '' """]
        SQ --> DASH["4. Replace em-dashes — → --"]
        DASH --> ZW["5. Strip zero-width spaces, BOM"]
        ZW --> CTRL["6. Strip C0/C1 control chars"]
    end

    CTRL --> WS["_MULTI_SPACE.sub() — collapse spaces/tabs"]
    WS --> BPLAT["_remove_boilerplate()<br/>Drop: nav labels, share buttons,<br/>subscribe banners, etc."]
    BPLAT --> DEDUP["_dedup_paragraphs()<br/>Remove repeated paragraphs<br/>(case-insensitive key)"]
    DEDUP --> NL["_MULTI_NEWLINE.sub() — max 2 blank lines"]
    NL --> CLEAN_TEXT["Clean article body text ✅"]

    CLEAN_TEXT --> LANG["language_detector.detect_language()<br/>langdetect → ISO 639-1 code"]
    LANG --> |"matches filter"| PASS["✅ Article passes"]
    LANG --> |"wrong language"| DROP["❌ Article dropped"]
```

---

## Noise CSS Patterns (HTML Cleaner)

These class/id patterns trigger full block removal:

| Pattern | Catches |
|---------|---------|
| `\bad(s|vert...)` | Advertisement divs |
| `\bcookie` | Cookie consent banners |
| `\bbanner` | Promotional banners |
| `\bpopup\b`, `\bmodal\b` | Popups/modals |
| `\bnewsletter\b` | Newsletter signup forms |
| `\bsubscribe\b` | Subscribe CTAs |
| `\bsocial.*share` | Social share buttons |
| `\brelated.*article` | Related content blocks |
| `\bcomment` | Comment sections |
| `\bsidebar\b`, `\bwidget\b` | Sidebars |
| `\bnav(igation)?` | Navigation menus |
| `\bheader\b`, `\bfooter\b` | Page headers/footers |
| `\bbreadcrumb\b` | Breadcrumb trails |
| `\bpagination\b` | Page number widgets |

---

## Boilerplate Line Patterns (Text Cleaner)

| Pattern | Catches |
|---------|---------|
| `share\|tweet\|email\|print\|save\|bookmark` | Social share prompts |
| `advertisement` | Ad labels |
| `continue reading below` | "Read more" prompts |
| `sponsored content` | Ad content labels |
| `follow us on` | Social follow CTAs |
| `click here to` | Generic CTAs |
| `sign up for.*newsletter` | Email signups |
| `subscribe to\|for` | Subscribe prompts |
| `you might also like` | Recommendation blocks |

---

## Function Reference

### `html_cleaner.py`

#### `clean_html(soup: BeautifulSoup) → BeautifulSoup`
Returns a **deep copy** of the soup (original is unmodified) with all noise removed.

#### `_matches_noise(tag) → bool`
Checks `class`, `id`, and `role` attributes against `_NOISE_PATTERNS`.

---

### `unicode_normalizer.py`

#### `normalize(text: str) → str`
Full normalisation pipeline (see flowchart). Gracefully skips `ftfy` if not installed.

**Key replacements:**
| Unicode | Replacement |
|---------|-------------|
| `\u2018` `\u2019` | `'` (straight apostrophe) |
| `\u201C` `\u201D` | `"` (straight quote) |
| `\u2013` | `-` (en-dash) |
| `\u2014` | `--` (em-dash) |
| `\u2026` | `...` (ellipsis) |
| `\u00A0` | ` ` (non-breaking space) |
| `\u200B` `\u200C` `\u200D` | `""` (zero-width chars) |
| `\uFEFF` | `""` (byte order mark) |

---

### `text_cleaner.py`

#### `clean_text(text: str) → str`
Full pipeline: normalize → collapse whitespace → remove boilerplate → dedup paragraphs → collapse blank lines.

#### `clean_title(title: str) → str`
Normalises + removes site-name suffixes:
```
"Breaking News | BBC News"    → "Breaking News"
"AI Report - Reuters"         → "AI Report"
"Story — The Guardian"        → "Story"
```

#### `clean_snippet(snippet: str) → str`
Normalises and truncates to 1000 chars (appends `…` if cut).

#### `_remove_boilerplate(paragraphs) → list`
Drops lines matching boilerplate patterns.
**Important:** Lines ending in `.!?` are **never** dropped by the short-line heuristic
(protects real short sentences like "Scientists confirmed it.").

#### `_dedup_paragraphs(paragraphs) → list`
Preserves **first occurrence** of each paragraph (case-insensitive, whitespace-normalised key).

---

### `language_detector.py`

#### `detect_language(text, min_length=50) → Optional[str]`
Uses `langdetect` (Facebook's `language-detection` port) with `seed=42` for determinism.
Returns `None` if text is shorter than `min_length` or detection fails.

#### `is_english(text) → bool`
Convenience: `detect_language(text) == "en"`.

---

## Manual Testing

### Setup
```powershell
cd c:\LATEST\news_detection\Model_v3\news_scraper
$env:PYTHONPATH = (Get-Location).Path
C:\Users\vinuj\anaconda3\python.exe
```

### Test 1 — HTML cleaner removes noise
```python
from bs4 import BeautifulSoup
from src.preprocess.html_cleaner import clean_html

html = """<html><body>
  <nav id="main-nav"><ul><li>Home</li><li>About</li></ul></nav>
  <header class="site-header"><h1>My News Site</h1></header>
  <script>ga('send', 'pageview');</script>
  <div class="cookie-banner">We use cookies!</div>
  <div class="newsletter-signup">Subscribe to our newsletter</div>
  <article>
    <p>This is the real article content.</p>
    <p>It should be preserved after cleaning.</p>
  </article>
  <aside class="sidebar">Sidebar widget</aside>
  <footer class="site-footer">Copyright 2024</footer>
</body></html>"""

soup = BeautifulSoup(html, "lxml")
clean = clean_html(soup)

# What was removed
print("Scripts remaining:", len(clean.find_all("script")))
print("Nav remaining:", len(clean.find_all("nav")))
print("Footer remaining:", len(clean.find_all("footer")))
print("Header remaining:", len(clean.find_all("header")))

# What was preserved
article = clean.find("article")
print("\nArticle preserved:", article is not None)
print("Paragraphs in article:", len(article.find_all("p")))
```

### Test 2 — Unicode normalisation
```python
from src.preprocess.unicode_normalizer import normalize

tests = [
    "\u201cHello World\u201d",          # Smart double quotes
    "It\u2019s a test",                  # Smart apostrophe
    "Paris\u2014the city of love",       # Em dash
    "Chapter 1\u2026",                   # Ellipsis
    "non\u00A0breaking\u00A0space",      # Non-breaking spaces
    "hel\u200blo\uFEFF",                 # Zero-width + BOM
]

for text in tests:
    result = normalize(text)
    print(f"  Input:  {repr(text)}")
    print(f"  Output: {repr(result)}\n")
```

### Test 3 — Boilerplate removal
```python
from src.preprocess.text_cleaner import clean_text

raw = """Scientists have confirmed the discovery.

Share this article

This represents a major breakthrough in physics research.

Advertisement

The implications for quantum computing are enormous.

Follow us on Twitter and Facebook.

Further experiments will be conducted in 2025.

Subscribe to our newsletter for updates.

This represents a major breakthrough in physics research."""

cleaned = clean_text(raw)
print("=== CLEANED TEXT ===")
print(cleaned)
```

**Expected:** Removes "Share this article", "Advertisement", "Follow us on...", "Subscribe...", and the duplicate paragraph.

### Test 4 — Title cleaning
```python
from src.preprocess.text_cleaner import clean_title

titles = [
    "AI Makes Breakthrough | BBC News",
    "Scientists Discover Planet - Reuters",
    "New Study Released \u2014 The Guardian",
    "Breaking: Major Announcement \u2013 TechCrunch",
    "Simple Title Without Suffix",
    "\u201cQuoted Title\u201d | Source",
]

for title in titles:
    print(f"  Input:  {title}")
    print(f"  Output: {clean_title(title)}\n")
```

### Test 5 — Paragraph deduplication
```python
from src.preprocess.text_cleaner import clean_text

# Simulate scraped text with duplicates (common with infinite-scroll sites)
text = """First unique paragraph with meaningful content.

Second paragraph about the topic at hand.

First unique paragraph with meaningful content.

Third paragraph expanding on the subject matter.

  First Unique Paragraph With Meaningful Content.  

Fourth paragraph providing additional context."""

cleaned = clean_text(text)
print(cleaned)
print(f"\n--- Paragraphs: {len([p for p in cleaned.split(chr(10)) if p.strip()])} ---")
```

### Test 6 — Language detection
```python
from src.preprocess.language_detector import detect_language, is_english

texts = [
    ("English article text. The quick brown fox jumps over the lazy dog.", "en"),
    ("Cet article est en français. La France est un beau pays.", "fr"),
    ("Dies ist ein deutscher Text über Wissenschaft und Technik.", "de"),
    ("Este artículo está escrito en español sobre noticias recientes.", "es"),
    ("Short", None),  # too short, returns None
]

for text, expected in texts:
    detected = detect_language(text)
    match = "✅" if detected == expected else "⚠️"
    print(f"{match} Expected: {expected}, Detected: {detected}")
    print(f"   Is English: {is_english(text)}")
```
