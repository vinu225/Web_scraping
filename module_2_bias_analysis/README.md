# Module 2 — Semantic Bias Analysis (RoBERTa)

Analyzes articles (from JSON, HTML, or directly from Module 1's scraper
output) and predicts a bias score between 0 and 1 using a RoBERTa
transformer, combined with engineered linguistic features.

## Folder guide

| Folder           | Responsibility                                                |
|------------------|------------------------------------------------------------------|
| `config/`        | Settings (model name/path, device, chunking, thresholds)        |
| `schemas/`       | `BiasAnalysisResult` output schema + API request schemas         |
| `loaders/`       | `json_loader`, `html_loader`, `article_loader` (Module 1 bridge) |
| `preprocessing/` | Text cleaning, normalization, deduplication, chunking            |
| `model/`         | Tokenizer, RoBERTa classifier, model loading, sliding-window inference |
| `features/`      | Subjectivity, emotional intensity, sensationalism, lexical diversity, complexity |
| `scoring/`       | Combines model + features into final bias score & label          |
| `pipeline/`      | Orchestrates the full end-to-end pipeline                        |
| `api/`           | FastAPI app: `/analyze-json`, `/analyze-html`, `/analyze-article` |
| `utils/`         | Logging (stage timings), custom exceptions                       |
| `tests/`         | Unit + integration tests, sample inputs/outputs                  |

## Pipeline order

```
Input → Loader → Preprocessing → Chunking → RoBERTa Inference →
Feature Engineering → Score Aggregation → Result Generation
```

## Output schema

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

## Bias score bands

| Range       | Label          |
|-------------|----------------|
| 0.00 – 0.25 | Low Bias       |
| 0.26 – 0.50 | Moderate Bias  |
| 0.51 – 0.75 | High Bias      |
| 0.76 – 1.00 | Extreme Bias   |

## Status

Scaffold only — see each file's module docstring for what to implement.
