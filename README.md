# Fake News Detection Platform — Semantic Bias Analysis

This project contains **Module 2: Semantic Bias Analysis**, a standalone FastAPI service
that analyses news articles and returns a bias score (0–1) powered by a RoBERTa
transformer combined with linguistic feature engineering.

Articles can be supplied as:
- JSON payloads matching the `shared/schemas.py` `Article` schema
- Raw HTML
- In-memory `Article` objects passed directly by a Python caller

---

## Layout

```
fake_news_platform/
├── shared/
│   └── schemas.py              # Article / ArticleImage — canonical input contract
│
├── module_2_bias_analysis/
│   ├── config/settings.py
│   ├── schemas/                # BiasAnalysisResult + API request schemas
│   ├── loaders/                # json_loader, html_loader, article_loader
│   ├── preprocessing/          # text_cleaner, unicode_normalizer, deduplicator, chunker
│   ├── model/                  # tokenizer_manager, roberta_classifier, inference
│   ├── features/feature_engineering.py
│   ├── scoring/scoring_engine.py
│   ├── pipeline/processing_pipeline.py   # full end-to-end orchestrator
│   ├── api/                    # FastAPI app + routes
│   ├── utils/                  # logger, exceptions
│   └── tests/
│
├── docker-compose.yml          # Single bias_analysis FastAPI service
└── .gitignore
```

---

## Pipeline

```
Input → Loader → Preprocessing → Chunking → RoBERTa Inference →
Feature Engineering → Score Aggregation → Result Generation
```

---

## Running the API

```bash
# Install dependencies
pip install -r module_2_bias_analysis/requirements.txt

# Start the server (port 8002)
uvicorn module_2_bias_analysis.api.main:app --reload --port 8002
```

Visit **http://localhost:8002/docs** for the interactive Swagger UI.

---

## Output Schema

```json
{
  "article_id": "",
  "title": "",
  "bias_score": 0.0,
  "subjectivity_score": 0.0,
  "emotional_intensity": 0.0,
  "confidence_score": 0.0,
  "classification": ""
}
```

## Bias Score Bands

| Range       | Label          |
|-------------|----------------|
| 0.00 – 0.25 | Low Bias       |
| 0.26 – 0.50 | Moderate Bias  |
| 0.51 – 0.75 | High Bias      |
| 0.76 – 1.00 | Extreme Bias   |

---

## Running Tests

```bash
pytest
```

All 158 tests pass.
