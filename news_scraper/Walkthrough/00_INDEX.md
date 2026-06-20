# 📚 News Scraper — Complete Walkthrough

This folder is a step-by-step technical guide to every layer of the system.
Each document explains **how the code works**, the **data flow**, and gives
**exact Python commands** to manually test that layer in isolation.

---

## 📋 Document Index

| # | File | What It Covers |
|---|------|----------------|
| 01 | [System Overview & Flowchart](./01_SYSTEM_OVERVIEW.md) | Full architecture, data flow, all module relationships |
| 02 | [Config & Logging](./02_CONFIG_AND_LOGGING.md) | `settings.py`, `logging_config.py` — how to test config loading |
| 03 | [Pydantic Schemas](./03_SCHEMAS.md) | `Article`, `ScraperResponse`, all models explained |
| 04 | [DuckDuckGo Search](./04_SEARCH_DUCKDUCKGO.md) | `DuckDuckGoSearcher`, `build_query`, `filter_results` |
| 05 | [NewsAPI Module](./05_NEWSAPI.md) | `NewsAPIClient`, `NewsFetcher`, `SourceManager` |
| 06 | [Crawler / URL Management](./06_CRAWLER.md) | `URLValidator`, `DuplicateChecker`, `URLCollector` |
| 07 | [Extractors](./07_EXTRACTORS.md) | `BS4Extractor`, metadata, content, image sub-extractors |
| 08 | [Preprocessing](./08_PREPROCESS.md) | HTML cleaner, text cleaner, unicode normalizer, lang detector |
| 09 | [Storage Backends](./09_STORAGE.md) | JSON writer, CSV writer, MongoDB writer |
| 10 | [Pipeline & Orchestrator](./10_PIPELINE.md) | `ScrapingPipeline`, `Orchestrator` — full end-to-end |
| 11 | [End-to-End Manual Testing](./11_END_TO_END.md) | Full run scenarios from CLI and Python REPL |

---

## 🗺️ Quick Navigation by Task

**"I want to understand the big picture"**
→ Start with [01_SYSTEM_OVERVIEW.md](./01_SYSTEM_OVERVIEW.md)

**"I want to test just the search"**
→ [04_SEARCH_DUCKDUCKGO.md](./04_SEARCH_DUCKDUCKGO.md) or [05_NEWSAPI.md](./05_NEWSAPI.md)

**"I want to scrape a single URL manually"**
→ [07_EXTRACTORS.md](./07_EXTRACTORS.md) → Manual Testing section

**"I want to run the full system"**
→ [11_END_TO_END.md](./11_END_TO_END.md)

---

## ⚙️ Setup Before Testing

All manual tests require the project root on your Python path.
Run this **once** in every new terminal session:

```powershell
# From the news_scraper/ directory
cd c:\LATEST\news_detection\Model_v3\news_scraper
$env:PYTHONPATH = (Get-Location).Path
python --version   # Should be 3.13+
```

Or launch the Python REPL directly:
```powershell
C:\Users\vinuj\anaconda3\python.exe
```
