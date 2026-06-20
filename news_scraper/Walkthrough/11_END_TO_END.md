# 11 — End-to-End Manual Testing Guide

This document gives you complete, runnable scenarios for manually testing the
**entire system** from CLI and from the Python REPL — no mocks, all real.

---

## Prerequisites

```powershell
# 1. Navigate to project root
cd c:\LATEST\news_detection\Model_v3\news_scraper

# 2. Set Python path (needed for REPL only, not CLI)
$env:PYTHONPATH = (Get-Location).Path

# 3. Verify setup
C:\Users\vinuj\anaconda3\python.exe -c "from config.settings import settings; print('✅ Setup OK')"
```

---

## Scenario A — Test each module in isolation (no network)

Run these in order to validate every layer works correctly before touching the network.

```powershell
C:\Users\vinuj\anaconda3\python.exe
```

### A1 — Config loads correctly
```python
from config.settings import settings
print("✅ Settings loaded")
print(f"   raw_data_dir exists: {settings.raw_data_dir.exists()}")
print(f"   log_dir exists:      {settings.log_dir.exists()}")
print(f"   max_workers:         {settings.max_workers}")
```

### A2 — Schemas work
```python
from src.schemas.article_schema import Article, ArticleSource
art = Article(
    article_id="test001",
    url="https://bbc.com/news/test",
    title="Test Article",
    snippet="A quick summary.",
    source=ArticleSource.DIRECT,
)
print("✅ Article model OK | domain:", art.domain())
```

### A3 — URL validation
```python
from src.crawler.url_validator import validate_url
good = validate_url("https://bbc.com/news/article-123")
bad  = validate_url("https://example.com/file.pdf")
print(f"✅ Good URL valid: {good[0]}")
print(f"✅ PDF rejected:   {not bad[0]} | reason: {bad[1]}")
```

### A4 — Deduplication
```python
from src.crawler.duplicate_checker import DuplicateChecker
c = DuplicateChecker()
c.mark_seen("https://example.com/a")
print("✅ Dedup working:", c.is_duplicate("https://example.com/a?utm_source=fb"))
```

### A5 — Query builder
```python
from src.search.query_builder import build_query, sanitize_keyword
q = build_query("climate change", site="bbc.com", exclude_terms=["sport"])
print("✅ Query:", q)
```

### A6 — HTML cleaning
```python
from bs4 import BeautifulSoup
from src.preprocess.html_cleaner import clean_html
html = "<html><body><script>bad()</script><nav>Menu</nav><article><p>Good content.</p></article></body></html>"
soup = BeautifulSoup(html, "lxml")
clean = clean_html(soup)
print("✅ Scripts removed:", clean.find("script") is None)
print("✅ Nav removed:    ", clean.find("nav") is None)
print("✅ Article kept:   ", clean.find("article") is not None)
```

### A7 — Text cleaning
```python
from src.preprocess.text_cleaner import clean_text
raw = "Real content.\nShare this article\nMore real content.\nReal content."
cleaned = clean_text(raw)
print("✅ Boilerplate removed:", "Share this article" not in cleaned)
print("✅ Duplicates removed: ", cleaned.count("Real content.") == 1)
print("Cleaned:\n", cleaned)
```

### A8 — JSON storage write/read
```python
import tempfile, json
from pathlib import Path
from src.schemas.article_schema import Article, ArticleSource
from src.storage.json_writer import JSONWriter

with tempfile.TemporaryDirectory() as tmp:
    art = Article(article_id="test", url="https://x.com", title="T", snippet="S", source=ArticleSource.DIRECT)
    path = JSONWriter(Path(tmp)).write(art)
    data = json.loads(path.read_text())
    print("✅ JSON write/read OK | title:", data["title"])
```

### A9 — CSV storage
```python
import tempfile, csv
from pathlib import Path
from src.schemas.article_schema import Article, ArticleSource
from src.storage.csv_writer import CSVWriter

with tempfile.TemporaryDirectory() as tmp:
    arts = [Article(article_id=f"c{i}", url=f"https://x.com/{i}", title=f"T{i}", snippet="S", source=ArticleSource.DIRECT) for i in range(3)]
    path = CSVWriter(Path(tmp)).export(arts)
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"✅ CSV has {len(rows)} rows | columns: {len(rows[0])}")
```

---

## Scenario B — DuckDuckGo live search (requires internet)

```python
from src.search.duckduckgo_search import DuckDuckGoSearcher

searcher = DuckDuckGoSearcher(max_results=5)
resp = searcher.search("latest AI research news 2024")

if resp.success:
    print(f"✅ Got {resp.data.total_found} results in {resp.data.elapsed_ms:.0f}ms\n")
    for r in resp.data.results:
        print(f"  [{r.rank}] {r.title[:60]}")
        print(f"       {r.url}")
else:
    print("❌ Failed:", resp.error)
```

---

## Scenario C — Single URL extraction (requires internet)

```python
from src.extractors.bs4_extractor import BS4Extractor
from src.schemas.article_schema import ArticleSource

# Try a well-structured news page
TEST_URL = "https://www.bbc.com/news/technology"

with BS4Extractor() as ex:
    result = ex.extract(TEST_URL, source=ArticleSource.DIRECT)

if result.success:
    art = result.article
    print("✅ Extraction successful!")
    print(f"   Title:       {art.title}")
    print(f"   Author:      {art.author or 'N/A'}")
    print(f"   Published:   {art.published_at or 'N/A'}")
    print(f"   Body length: {len(art.body or '')} chars")
    print(f"   Images:      {len(art.images)}")
    print(f"   Thumbnail:   {art.thumbnail_url or 'None'}")
    print(f"   Time:        {result.elapsed_ms:.0f}ms")
    print(f"\n   Body preview:\n   {(art.body or '')[:300]}")
else:
    print("❌ Failed:", result.error)
```

---

## Scenario D — Full mini-pipeline (internet required)

This runs the complete pipeline with 3 direct URLs, saves to temp dirs, and shows the results.

```python
import tempfile, json
from pathlib import Path
from src.pipeline.scraping_pipeline import ScrapingPipeline
from src.schemas.article_schema import ArticleSource

# Use stable, well-structured news URLs
URLS = [
    "https://techcrunch.com",
    "https://www.theverge.com",
    "https://arstechnica.com",
]

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp)
    pipeline = ScrapingPipeline(
        raw_dir=p/"raw",
        cleaned_dir=p/"cleaned",
        failed_dir=p/"failed",
        exports_dir=p/"exports",
        max_workers=3,
        language_filter="en",
        min_body_length=100,
    )

    stats = pipeline.run(urls=URLS, source=ArticleSource.DIRECT)

    print("\n=== PIPELINE RESULTS ===")
    print(f"Successful: {stats.successful}/{stats.total_urls}")
    print(f"Failed:     {stats.failed}")
    print(f"Time:       {stats.elapsed_seconds:.1f}s")

    print("\n=== CLEANED ARTICLES ===")
    for f in (p/"cleaned").glob("*.json"):
        data = json.loads(f.read_text())
        print(f"  📰 {data['title'][:60]}")
        print(f"     Words: {data['metadata'].get('word_count', '?')}")

    print("\n=== EXPORT FILES ===")
    for f in (p/"exports").iterdir():
        print(f"  📦 {f.name}: {f.stat().st_size} bytes")
```

---

## Scenario E — CLI usage (run.py)

Open a new PowerShell terminal:

```powershell
cd c:\LATEST\news_detection\Model_v3\news_scraper

# E1: Show help
C:\Users\vinuj\anaconda3\python.exe run.py --help

# E2: Scrape 3 specific URLs
C:\Users\vinuj\anaconda3\python.exe run.py `
    --urls https://techcrunch.com https://www.theverge.com `
    --workers 2

# E3: DuckDuckGo search (5 results per keyword)
C:\Users\vinuj\anaconda3\python.exe run.py `
    --keywords "Python machine learning" `
    --ddg `
    --max-results 5 `
    --lang en

# E4: NewsAPI search (requires key in .env)
C:\Users\vinuj\anaconda3\python.exe run.py `
    --keywords "artificial intelligence" `
    --newsapi `
    --from-date 2024-01-01 `
    --lang en

# E5: Combined (DDG + NewsAPI + direct)
C:\Users\vinuj\anaconda3\python.exe run.py `
    --keywords "OpenAI GPT" `
    --ddg `
    --newsapi `
    --urls https://openai.com/blog `
    --lang en `
    --workers 5 `
    --max-results 10
```

---

## Scenario F — Inspect output after a run

```powershell
# Open PowerShell in the news_scraper folder
cd c:\LATEST\news_detection\Model_v3\news_scraper

# Count saved articles
(Get-ChildItem data\raw -Filter "*.json").Count
(Get-ChildItem data\cleaned -Filter "*.json").Count

# View a cleaned article
Get-Content (Get-ChildItem data\cleaned -Filter "*.json" | Select -First 1).FullName | python -m json.tool | Select -First 40

# List export files
Get-ChildItem data\exports

# Check log for errors
Select-String -Path logs\error.log -Pattern "ERROR|CRITICAL" | Select -Last 20

# Tail the scraper log
Get-Content logs\scraper.log -Tail 30
```

---

## Scenario G — Run the automated test suite

```powershell
cd c:\LATEST\news_detection\Model_v3\news_scraper

# Run all 78 tests
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/ --no-cov -v

# Run only a specific module's tests
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/test_extractor.py -v
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/test_pipeline.py -v
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/test_duckduckgo.py -v
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/test_newsapi.py -v

# Run with coverage report
C:\Users\vinuj\anaconda3\python.exe -m pytest tests/ -v
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Set `$env:PYTHONPATH = (Get-Location).Path` from `news_scraper/` |
| `NewsAPI key required` | Add `NEWSAPI_KEY=your_key` to `.env` |
| `DuckDuckGoSearchException` | Wait 60s and retry — you hit DDG rate limit |
| Empty body extracted | Site uses JavaScript rendering (BS4 can't run JS) |
| `HTTP 403` | Site blocks bots — use a different URL |
| `HTTP 429` | Rate limited — reduce `MAX_WORKERS` and add `RATE_LIMIT_DELAY=2.0` in `.env` |
| MongoDB connection error | Start MongoDB with `mongod` or use Atlas cloud URI |
| `langdetect` not found | Run `pip install langdetect` |
| Articles saved to wrong dir | Check `RAW_DATA_DIR` in `.env` — paths should be absolute or relative to `news_scraper/` |

---

## Quick Reference — All Entry Points

```python
# === Search ===
from src.search.duckduckgo_search import DuckDuckGoSearcher
DuckDuckGoSearcher().search("keyword")

from src.newsapi.news_fetcher import NewsFetcher
from src.newsapi.newsapi_client import NewsAPIClient
with NewsAPIClient() as c: NewsFetcher(c).top_headlines(country="us")

# === Single URL extraction ===
from src.extractors.bs4_extractor import BS4Extractor
with BS4Extractor() as ex: ex.extract("https://url.com")

# === Full pipeline ===
from src.pipeline.orchestrator import Orchestrator
Orchestrator().run(keywords=["AI"], use_duckduckgo=True)

# === Storage ===
from src.storage.json_writer import JSONWriter
from src.storage.csv_writer import CSVWriter
from pathlib import Path
JSONWriter(Path("data/cleaned")).write(article)
CSVWriter(Path("data/exports")).export(articles)
```
