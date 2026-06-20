# 01 — System Overview & Architecture Flowchart

## What Is This System?

The News Scraper is a **modular, production-ready pipeline** that:
1. **Discovers** article URLs from three sources (DuckDuckGo, NewsAPI, direct input)
2. **Collects & deduplicates** URLs into a clean queue
3. **Downloads & parses** each webpage using BeautifulSoup4
4. **Extracts** structured data: title, author, date, body, images, metadata
5. **Cleans & normalises** the text (unicode, whitespace, boilerplate removal)
6. **Validates** the article meets minimum quality requirements
7. **Stores** results as JSON, CSV, and optionally MongoDB

---

## 🗺️ Full System Architecture

```mermaid
graph TD
    CLI["🖥️ run.py<br/>(CLI entry point)"]
    ORCH["🎭 Orchestrator<br/>src/pipeline/orchestrator.py"]
    
    CLI --> ORCH

    ORCH --> DDG["🔍 DuckDuckGoSearcher<br/>src/search/duckduckgo_search.py"]
    ORCH --> NAPI["📰 NewsFetcher<br/>src/newsapi/news_fetcher.py"]
    ORCH --> DIRECT["🔗 Direct URLs<br/>(user supplied)"]

    DDG --> QBuild["⚙️ QueryBuilder<br/>query_builder.py"]
    DDG --> RFilter["🔎 ResultFilter<br/>result_filter.py"]

    NAPI --> NClient["🔑 NewsAPIClient<br/>newsapi_client.py"]
    NAPI --> SMgr["📋 SourceManager<br/>source_manager.py"]

    DDG --> COLL
    NAPI --> COLL
    DIRECT --> COLL

    COLL["📥 URLCollector<br/>src/crawler/url_collector.py"]
    COLL --> UVAL["✅ URLValidator<br/>url_validator.py"]
    COLL --> DEDUP["🔄 DuplicateChecker<br/>duplicate_checker.py"]

    COLL --> PIPE["⚡ ScrapingPipeline<br/>src/pipeline/scraping_pipeline.py<br/>(ThreadPoolExecutor)"]

    PIPE --> EXT["🕷️ BS4Extractor<br/>src/extractors/bs4_extractor.py"]

    EXT --> META["🏷️ MetadataExtractor<br/>metadata_extractor.py"]
    EXT --> CONT["📄 ContentExtractor<br/>content_extractor.py"]
    EXT --> IMG["🖼️ ImageExtractor<br/>image_extractor.py"]
    EXT --> HCLEAN["🧹 HTMLCleaner<br/>src/preprocess/html_cleaner.py"]

    PIPE --> TCLEAN["✍️ TextCleaner<br/>src/preprocess/text_cleaner.py"]
    TCLEAN --> UNORM["🔤 UnicodeNormalizer<br/>unicode_normalizer.py"]
    TCLEAN --> LANG["🌍 LanguageDetector<br/>language_detector.py"]

    PIPE --> VALID["🛡️ Validator<br/>(Pydantic Article model)"]

    VALID -->|"PASS"| STORE["💾 Storage Layer"]
    VALID -->|"FAIL"| FAIL["❌ data/failed/"]

    STORE --> JRAW["📁 JSONWriter (raw)<br/>data/raw/"]
    STORE --> JCLEAN["📁 JSONWriter (cleaned)<br/>data/cleaned/"]
    STORE --> CSV["📊 CSVWriter<br/>data/exports/"]
    STORE --> MONGO["🍃 MongoDBWriter<br/>(optional)"]

    style CLI fill:#4A90D9,color:#fff
    style ORCH fill:#7B68EE,color:#fff
    style PIPE fill:#E67E22,color:#fff
    style STORE fill:#27AE60,color:#fff
    style FAIL fill:#E74C3C,color:#fff
```

---

## 🔁 Data Flow — Step by Step

```mermaid
sequenceDiagram
    participant User
    participant Orchestrator
    participant URLCollector
    participant BS4Extractor
    participant Preprocessors
    participant Storage

    User->>Orchestrator: run(keywords=["AI"], use_duckduckgo=True)
    Orchestrator->>Orchestrator: _collect_from_duckduckgo("AI")
    Orchestrator->>URLCollector: add_many([url1, url2, ...])
    URLCollector->>URLCollector: validate_url() → dedup check
    URLCollector-->>Orchestrator: accepted=12 URLs
    
    Orchestrator->>ScrapingPipeline: run(urls=[...12 URLs...])
    
    loop For each URL (parallel threads)
        ScrapingPipeline->>BS4Extractor: extract(url)
        BS4Extractor->>BS4Extractor: _download(url) → HTML
        BS4Extractor->>BS4Extractor: clean_html(soup)
        BS4Extractor->>BS4Extractor: extract_metadata()
        BS4Extractor->>BS4Extractor: extract_body()
        BS4Extractor->>BS4Extractor: extract_images()
        BS4Extractor-->>ScrapingPipeline: Article(raw)
        
        ScrapingPipeline->>Storage: JSONWriter.write(raw article)
        ScrapingPipeline->>Preprocessors: clean_text(body)
        Preprocessors->>Preprocessors: normalize() → dedup → boilerplate
        Preprocessors-->>ScrapingPipeline: clean body text
        
        ScrapingPipeline->>ScrapingPipeline: _is_valid(article)
        ScrapingPipeline->>Storage: JSONWriter.write(cleaned article)
    end
    
    ScrapingPipeline->>Storage: CSVWriter.export(all_articles)
    ScrapingPipeline->>Storage: export_jsonl(all_articles)
    Storage-->>User: PipelineStats(successful=10, failed=2)
```

---

## 📦 Module Dependency Map

```mermaid
graph LR
    subgraph "Entry Points"
        CLI["run.py"]
        PY["Python API"]
    end

    subgraph "Orchestration"
        ORCH["orchestrator.py"]
        PIPE["scraping_pipeline.py"]
    end

    subgraph "Discovery"
        DDG["duckduckgo_search.py"]
        NAPI["news_fetcher.py"]
    end

    subgraph "Crawl Management"
        COLL["url_collector.py"]
        VAL["url_validator.py"]
        DEDUP["duplicate_checker.py"]
    end

    subgraph "Extraction"
        BS4["bs4_extractor.py"]
        META["metadata_extractor.py"]
        CONT["content_extractor.py"]
        IMGX["image_extractor.py"]
    end

    subgraph "Preprocessing"
        HTML["html_cleaner.py"]
        TEXT["text_cleaner.py"]
        UNI["unicode_normalizer.py"]
        LANGD["language_detector.py"]
    end

    subgraph "Schemas"
        ART["article_schema.py"]
        RESP["response_schema.py"]
    end

    subgraph "Utils"
        LOG["logger.py"]
        HASH["hash_utils.py"]
        DATE["date_utils.py"]
        HELP["helpers.py"]
    end

    subgraph "Storage"
        JSON["json_writer.py"]
        CSV["csv_writer.py"]
        MONGO["mongodb_writer.py"]
    end

    CLI --> ORCH
    PY --> ORCH
    ORCH --> DDG
    ORCH --> NAPI
    ORCH --> COLL
    ORCH --> PIPE
    DDG --> COLL
    NAPI --> COLL
    COLL --> VAL
    COLL --> DEDUP
    PIPE --> BS4
    PIPE --> TEXT
    PIPE --> JSON
    PIPE --> CSV
    BS4 --> META
    BS4 --> CONT
    BS4 --> IMGX
    BS4 --> HTML
    TEXT --> UNI
    META --> DATE
    DEDUP --> HASH
    COLL --> HASH
```

---

## 🗂️ Directory Layout at Runtime

After a successful run you'll see:

```
news_scraper/
├── data/
│   ├── raw/
│   │   ├── a3f8c1d2...sha256.json   ← One file per article (unprocessed)
│   │   └── b9e4f7a1...sha256.json
│   ├── cleaned/
│   │   └── a3f8c1d2...sha256.json   ← Same article, after cleaning
│   ├── failed/
│   │   └── bad_url_hash.json        ← Failed/rejected articles
│   └── exports/
│       ├── articles_20240315_143022.jsonl  ← Batch JSONL (one line/article)
│       └── articles_20240315_143022.csv    ← Flat CSV for Excel
└── logs/
    ├── scraper.log   ← All log levels (INFO, DEBUG, WARNING, ERROR)
    └── error.log     ← WARNING+ only
```

---

## ⚡ Key Design Decisions

| Decision | Why |
|----------|-----|
| **ThreadPoolExecutor** for extraction | I/O-bound HTTP requests — threads are ideal |
| **SHA-256 URL hash as article_id** | Stable, collision-resistant, dedup-friendly |
| **Pydantic v2 models** | Runtime validation, free JSON serialisation, type safety |
| **Separation of raw/cleaned data** | Can re-run cleaning without re-scraping |
| **Generic `ScraperResponse[T]`** | Consistent error handling across all modules |
| **Rotating log files** | Prevents disk exhaustion on long-running jobs |
| **MongoDB optional** | Works fully without it; just set `MONGODB_URI` to enable |
