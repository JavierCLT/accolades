# Merrill Edge Daily Monitor

Python 3.11+ monitoring agent for Merrill Edge accolades, rankings, reviews, customer themes, competitor moves, cash-yield signals, app reviews, and regulatory complaint signals. It uses API or feed-based sources where available, SQLite for deduplication, and SMTP or Gmail API for email delivery.

## What It Does

- Searches configurable web, forum, app-review, complaint, and rate-context sources daily.
- Deduplicates results by normalized URL against `seen_results` in SQLite.
- Classifies new items into accolade, competitor, offer/promotion, pricing, complaint, feature, cash yield, ACAT, fees, app/website, service, regulatory, mobile-app, or other categories.
- Uses optional LLM classification when configured, with a rule-based fallback.
- Sends a concise plain-text email digest with executive summary, accolades, forum themes, risk items, recommended actions, and source links.
- Runs locally or on GitHub Actions cron.

## Intelligence Modules

The default configuration includes these monitors:

- Merrill Edge mentions, accolades, rankings, reviews, and forum themes through Brave Search API.
- Competitor offer and product intelligence through Brave Search API, including promotions, transfer bonuses, pricing, margin rates, and feature gaps.
- Cash yield and money market intelligence through Brave Search API plus optional FRED rate observations.
- App experience monitoring through Apple customer review feeds and Brave Search app-experience queries.
- Regulatory and complaint early-warning through the CFPB Consumer Complaint Database API and Brave regulatory searches.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
```

Edit `.env`, `sources.yaml`, and `queries.yaml`, then initialize the database:

```powershell
merrill-monitor init-db
merrill-monitor run --dry-run
```

`--dry-run` previews the digest without writing SQLite or sending email. Use `--baseline` once when you want to store current results as already seen before normal daily emails begin.

## Required API Setup

### Brave Search API

Create a Brave Search API key from the Brave Search API dashboard. Set:

```text
BRAVE_SEARCH_API_KEY=...
```

The monitor calls Brave's Web Search API endpoint only. It does not scrape result pages.

### Optional FRED API

The `fred_series` source provides interest-rate context for cash sweep and money market positioning. Create a FRED API key from the Federal Reserve Bank of St. Louis and set:

```text
FRED_API_KEY=...
```

If `FRED_API_KEY` is not set, the FRED source logs a warning and skips without failing the run.

### CFPB Complaints

The `cfpb_complaints` source uses the CFPB Consumer Complaint Database API and does not require a key. Configure company names, search terms, date window, and result limit in `sources.yaml`.

### Apple App Store Reviews

The `apple_app_store_reviews` source uses Apple's public customer review feed by app ID and does not require a key. Configure app IDs in `sources.yaml`.

## Email Setup

Use either SMTP or Gmail API.

### SMTP

```text
EMAIL_BACKEND=smtp
EMAIL_FROM=alerts@example.com
EMAIL_TO=you@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=your-app-password
SMTP_STARTTLS=true
```

For Gmail SMTP, use an app password.

### Gmail API

Set:

```text
EMAIL_BACKEND=gmail_api
GMAIL_TOKEN_JSON={...}
```

`GMAIL_TOKEN_JSON` must be an authorized-user token JSON with the `https://www.googleapis.com/auth/gmail.send` scope.

## Optional LLM Classification

By default, classification is rule-based. To enable LLM classification:

```powershell
python -m pip install -e .[llm]
```

Then set:

```text
LLM_CLASSIFIER_ENABLED=true
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=low
```

If the LLM call fails, the monitor logs the error and uses rule-based classification.

## Configuration

`queries.yaml` stores query groups. Add, remove, or edit searches there without changing Python code.

`sources.yaml` stores source definitions. Supported source types:

- `brave_search`: Brave Search API.
- `cfpb_complaints`: CFPB Consumer Complaint Database API.
- `fred_series`: FRED observations API; requires `FRED_API_KEY`.
- `apple_app_store_reviews`: Apple customer review feed by app ID.

Useful `brave_search` fields:

- `enabled`: turn a source on or off.
- `query_groups`: list of query groups from `queries.yaml`.
- `result_limit`: maximum results per query.
- `freshness`: Brave freshness filter such as `pd`, `pw`, `pm`, `py`, or a date range.
- `site_restrict`: adds `site:example.com` to Brave queries.
- `country`, `search_lang`, `safesearch`: Brave search controls.
- `is_forum_discussion`: marks results as forum/theme items in classification and digest sections.
- `dedupe_strategy`: `url` by default, or `url_content` when the same URL should be treated as new if the title/snippet changes.

Useful `cfpb_complaints` fields:

- `companies`: company names to request from CFPB.
- `search_terms`: terms to request from CFPB.
- `date_window_days`: how far back to search.
- `result_limit`: maximum complaints per CFPB request.

Useful `fred_series` fields:

- `series`: list of FRED series IDs and labels.

Useful `apple_app_store_reviews` fields:

- `country`: App Store country code.
- `apps`: list of app IDs and names.
- `result_limit`: maximum recent reviews per app.

## SQLite Schema

The `seen_results` table includes:

- `id`
- `source`
- `url`
- `normalized_url`
- `title`
- `snippet`
- `published_date`
- `first_seen_date`
- `last_seen_date`
- `category`
- `sentiment`
- `relevance_score`
- `is_accolade`
- `is_forum_discussion`
- `action_recommendation`

The implementation also stores `summary`, `last_notified_date`, and `raw_json` for digest quality and auditability.

## GitHub Actions

The workflow in `.github/workflows/daily-monitor.yml` runs the normal daily digest at `12:15 UTC` and can also be started manually. The separate `.github/workflows/baseline-monitor.yml` workflow stores current results as seen without sending an email.

Add these repository secrets as needed:

```text
BRAVE_SEARCH_API_KEY
FRED_API_KEY
EMAIL_BACKEND
EMAIL_FROM
EMAIL_TO
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_STARTTLS
GMAIL_TOKEN_JSON
LLM_CLASSIFIER_ENABLED
OPENAI_API_KEY
OPENAI_MODEL
```

The workflow sets `OPENAI_REASONING_EFFORT=low` directly.

The workflow persists `data/monitor.sqlite` through `actions/cache` using a unique run key with restore keys, so deduplication state carries forward between manual baseline runs and scheduled runs.

## Local Commands

```powershell
# Create or migrate the SQLite database
merrill-monitor init-db

# Run without sending email
merrill-monitor run --dry-run

# First-time baseline: store current results as seen without emailing them
merrill-monitor run --baseline

# Run with explicit config paths
merrill-monitor run --sources sources.yaml --queries queries.yaml --db data/monitor.sqlite
```

## Compliance Notes

This project intentionally uses APIs and configurable source definitions. Do not add sources that require scraping in violation of site terms. Prefer official APIs, RSS feeds, or pages made available through Brave Search API.

## Development Checks

```powershell
python -m compileall src
python -m pytest
```
