# Merrill Edge Daily Monitor

Python 3.11+ monitoring agent for new Merrill Edge mentions, accolades, rankings, reviews, Reddit discussions, and forum themes. It uses Google Custom Search JSON API for web results, Reddit's official API via PRAW for Reddit, SQLite for deduplication, and SMTP or Gmail API for email delivery.

## What It Does

- Searches configurable web, forum, and Reddit sources daily.
- Deduplicates results by normalized URL against `seen_results` in SQLite.
- Classifies new items into accolade, competitor, complaint, feature, cash yield, ACAT, fees, app/website, service, or other categories.
- Uses optional LLM classification when configured, with a rule-based fallback.
- Sends a concise plain-text email digest with executive summary, accolades, forum themes, risk items, recommended actions, and source links.
- Runs locally or on GitHub Actions cron.

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

Remove `--dry-run` after email configuration is working.

## Required API Setup

### Google Custom Search JSON API

Create a Google API key with Custom Search JSON API access and a Programmable Search Engine ID. Set:

```text
GOOGLE_CSE_API_KEY=...
GOOGLE_CSE_ID=...
```

The monitor calls the JSON API endpoint only. It does not scrape result pages.

### Reddit API

Create a Reddit app and use PRAW credentials:

```text
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=merrill-edge-monitor/0.1 by your-reddit-username
```

The monitor searches Reddit through the official API client.

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
OPENAI_MODEL=...
```

If the LLM call fails, the monitor logs the error and uses rule-based classification.

## Configuration

`queries.yaml` stores query groups. Add, remove, or edit searches there without changing Python code.

`sources.yaml` stores source definitions. Supported source types:

- `google_cse`: Google Custom Search JSON API.
- `reddit`: Reddit API via PRAW.

Useful source fields:

- `enabled`: turn a source on or off.
- `query_groups`: list of query groups from `queries.yaml`.
- `result_limit`: maximum results per query.
- `date_restrict`: Google CSE date filter such as `d7` or `d14`.
- `site_restrict`: adds `site:example.com` to Google queries.
- `subreddits`, `sort`, `time_filter`: Reddit search controls.
- `is_forum_discussion`: marks results as forum/theme items in classification and digest sections.

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

The workflow in `.github/workflows/daily-monitor.yml` runs daily at `12:15 UTC` and can also be started manually.

Add these repository secrets as needed:

```text
GOOGLE_CSE_API_KEY
GOOGLE_CSE_ID
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
REDDIT_USER_AGENT
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

The workflow persists `data/monitor.sqlite` through `actions/cache` using a daily cache key with restore keys, so deduplication state carries forward between scheduled runs.

## Local Commands

```powershell
# Create or migrate the SQLite database
merrill-monitor init-db

# Run without sending email
merrill-monitor run --dry-run

# Run with explicit config paths
merrill-monitor run --sources sources.yaml --queries queries.yaml --db data/monitor.sqlite
```

## Compliance Notes

This project intentionally uses APIs and configurable source definitions. Do not add sources that require scraping in violation of site terms. Prefer official APIs, RSS feeds, or pages made available through Google Custom Search.

## Development Checks

```powershell
python -m compileall src
python -m pytest
```
