# News Scraper — Production-Ready Python Web Scraping System

A modular, production-quality news article scraping system supporting **DuckDuckGo**, **NewsAPI**, and **direct URL** ingestion. Built with Python 3.12+, Pydantic v2, BeautifulSoup4, and structured logging.

---

## 📁 Project Structure

```
news_scraper/
├── .env                        # API keys & environment configuration
├── requirements.txt            # Python dependencies
├── run.py                      # CLI entry point
├── pytest.ini                  # Test configuration
│
├── config/
│   ├── settings.py             # Pydantic-settings configuration
│   └── logging_config.py       # Rotating file + coloured console logging
│
├── data/
│   ├── raw/                    # Raw extracted articles (JSON)
│   ├── cleaned/                # Cleaned articles (JSON)
│   ├── failed/                 # Failed extraction records
│   └── exports/                # CSV and JSONL batch exports
│
├── src/
│   ├── search/
│   │   ├── duckduckgo_search.py   # DDG paginated search
│   │   ├── query_builder.py       # Query string construction
│   │   └── result_filter.py       # Domain/quality filtering
│   │
│   ├── newsapi/
│   │   ├── newsapi_client.py      # Authenticated HTTP client
│   │   ├── news_fetcher.py        # Headlines + keyword search
│   │   └── source_manager.py      # Source listing/validation
│   │
│   ├── crawler/
│   │   ├── url_collector.py       # URL aggregation queue
│   │   ├── url_validator.py       # Validation + file-type blocking
│   │   └── duplicate_checker.py   # SHA-256 hash deduplication
│   │
│   ├── extractors/
│   │   ├── bs4_extractor.py       # Main extraction orchestrator
│   │   ├── metadata_extractor.py  # OG/JSON-LD/meta tag parsing
│   │   ├── content_extractor.py   # Body text via density scoring
│   │   └── image_extractor.py     # Image extraction + hero image
│   │
│   ├── preprocess/
│   │   ├── html_cleaner.py        # Noise tag removal
│   │   ├── text_cleaner.py        # Whitespace/boilerplate/dedup
│   │   ├── unicode_normalizer.py  # NFC + mojibake repair
│   │   └── language_detector.py   # langdetect wrapper
│   │
│   ├── storage/
│   │   ├── json_writer.py         # Per-article JSON + JSONL export
│   │   ├── csv_writer.py          # CSV export with append mode
│   │   └── mongodb_writer.py      # Optional MongoDB upsert writer
│   │
│   ├── schemas/
│   │   ├── article_schema.py      # Pydantic Article + sub-models
│   │   └── response_schema.py     # Generic ScraperResponse wrapper
│   │
│   ├── utils/
│   │   ├── logger.py              # Child logger factory
│   │   ├── helpers.py             # Retry decorator, Timer, text utils
│   │   ├── date_utils.py          # Timezone-aware date parsing
│   │   └── hash_utils.py          # URL normalisation + SHA-256 hash
│   │
│   └── pipeline/
│       ├── scraping_pipeline.py   # Concurrent per-URL processing
│       └── orchestrator.py        # Top-level entry point
│
├── tests/
│   ├── conftest.py
│   ├── test_duckduckgo.py
│   ├── test_newsapi.py
│   ├── test_extractor.py
│   └── test_pipeline.py
│
└── logs/
    ├── scraper.log               # All levels (rotating, 10 MB)
    └── error.log                 # WARNING+ only (rotating, 10 MB)
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd news_scraper
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env` and add your API key:

```bash
# .env
NEWSAPI_KEY=your_actual_key_here
```

### 3. Run the Scraper

**DuckDuckGo search:**
```bash
python run.py --keywords "artificial intelligence" "climate change" --ddg
```

**NewsAPI search:**
```bash
python run.py --keywords "OpenAI" --newsapi --lang en --from-date 2024-01-01
```

**Direct URLs:**
```bash
python run.py --urls https://bbc.com/news/article1 https://reuters.com/article2
```

**Combined (all sources):**
```bash
python run.py --keywords "AI regulation" --ddg --newsapi --lang en --workers 8 --max-results 30
```

**Full CLI options:**
```
--keywords / -k     Search keywords (one or more)
--urls / -u         Direct article URLs to scrape
--ddg               Enable DuckDuckGo search
--newsapi           Enable NewsAPI search
--newsapi-key       Override .env API key
--sources           NewsAPI source IDs
--lang              ISO language filter (default: en)
--from-date         NewsAPI earliest date (YYYY-MM-DD)
--to-date           NewsAPI latest date (YYYY-MM-DD)
--max-results       DDG results per keyword
--workers           Thread-pool size (default: 5)
--min-body          Min body chars to accept (default: 200)
```

---

## 🐍 Programmatic API

```python
from src.pipeline.orchestrator import Orchestrator

orch = Orchestrator(max_workers=8, language_filter="en")
stats = orch.run(
    keywords=["generative AI", "large language models"],
    use_duckduckgo=True,
    use_newsapi=True,
    newsapi_from_date="2024-01-01",
)
print(f"Saved {stats.articles_saved} articles in {stats.elapsed_seconds:.1f}s")
```

### Individual module usage

```python
# DuckDuckGo search only
from src.search.duckduckgo_search import DuckDuckGoSearcher
searcher = DuckDuckGoSearcher(max_results=20)
resp = searcher.search("quantum computing", site="nature.com")
for result in resp.data.results:
    print(result.title, result.url)

# Extract a single article
from src.extractors.bs4_extractor import BS4Extractor
with BS4Extractor() as ex:
    result = ex.extract("https://example.com/article")
    if result.success:
        print(result.article.title)
        print(result.article.body[:500])
```

---

## 🧪 Running Tests

```bash
# All tests with coverage report
pytest

# Specific module
pytest tests/test_extractor.py -v

# Without coverage (faster)
pytest --no-cov
```

---

## 📦 Data Output

| Format | Location | Description |
|--------|----------|-------------|
| Individual JSON | `data/raw/<id>.json` | One file per article (raw) |
| Individual JSON | `data/cleaned/<id>.json` | One file per article (cleaned) |
| JSONL export | `data/exports/articles_<ts>.jsonl` | All articles, one per line |
| CSV export | `data/exports/articles_<ts>.csv` | Flat CSV, Excel-compatible |
| Failed records | `data/failed/<id>.json` | Failed/rejected article records |

---

## ⚙️ Configuration Reference

All settings can be overridden via environment variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEWSAPI_KEY` | _(required)_ | NewsAPI v2 API key |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout seconds |
| `MAX_RETRIES` | `3` | HTTP retry attempts |
| `RETRY_BACKOFF` | `2.0` | Exponential backoff multiplier |
| `RATE_LIMIT_DELAY` | `1.0` | Seconds between DDG page requests |
| `MAX_WORKERS` | `5` | Thread pool size |
| `DDG_MAX_RESULTS` | `50` | DuckDuckGo max results per query |
| `DDG_REGION` | `wt-wt` | DuckDuckGo region |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |

---

## 🏗️ Architecture

```
Keywords / URLs
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  DuckDuckGo │    │   NewsAPI    │    │  Direct URLs │
│   Searcher  │    │   Fetcher    │    │              │
└──────┬──────┘    └──────┬───────┘    └──────┬───────┘
       │                  │                   │
       └──────────────────┴───────────────────┘
                          │
                   ┌──────▼──────┐
                   │ URLCollector │  ← validate + deduplicate
                   └──────┬──────┘
                          │
              ┌───────────▼───────────┐
              │   ScrapingPipeline    │  ← ThreadPoolExecutor
              │   (concurrent)        │
              └───────────┬───────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
   BS4Extractor    TextCleaner      Validator
   (download +     (unicode +       (Pydantic +
    parse HTML)     boilerplate)     min length)
         │                │                │
         └────────────────┴────────────────┘
                          │
              ┌───────────▼───────────┐
              │       Storage         │
              │  JSON │ CSV │ MongoDB  │
              └───────────────────────┘
```

---

## 📋 Article Schema

```python
Article(
    article_id: str,          # SHA-256(normalized_url)
    url: str,                 # Canonical URL
    title: str,               # Cleaned title
    author: Optional[str],
    published_at: Optional[datetime],
    body: Optional[str],      # Cleaned article body
    snippet: Optional[str],   # Search snippet / OG description
    images: list[ImageMeta],
    thumbnail_url: Optional[str],
    metadata: ArticleMetadata,  # OG, keywords, word_count, etc.
    source: ArticleSource,    # duckduckgo | newsapi | direct
    status: ArticleStatus,    # raw | cleaned | validated | failed
    scraped_at: datetime,
    processing_time_ms: float,
)
```

---

## 🔒 Production Considerations

- **Rate limiting**: Built-in `RATE_LIMIT_DELAY` between DDG page requests
- **Retries**: Exponential backoff on transient HTTP errors (500, 502, 503, 504)
- **Deduplication**: SHA-256 URL hashing with optional file-backed persistence
- **Error isolation**: Failed URLs are stored in `data/failed/` without crashing the pipeline
- **Logging**: Rotating log files (`scraper.log` + `error.log`) with configurable size
- **Thread safety**: Each thread has its own `requests.Session` lifecycle
