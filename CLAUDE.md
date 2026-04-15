# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Required environment variables:
```bash
export GEMINI_API_KEY='your-gemini-api-key'
export IG_SESSION_ID='your-instagram-session-id'  # only needed for Instagram URLs
```

## Running

```bash
.venv/bin/python3 main.py <url>
.venv/bin/python3 main.py <url> --export           # saves SVG to exports/
.venv/bin/python3 main.py <url> --analysis sentiment  # sentiment only (no camps)
.venv/bin/python3 main.py <url> --analysis camps      # camps only (no sentiment bars)
```

Supports Instagram (`/p/`, `/reel/`, `/tv/`) and Reddit (`reddit.com/r/.../comments/...`) URLs.

## Architecture

The tool is a single-pass CLI pipeline:

1. **`main.py`** — parses args, routes to the correct client, calls the summariser, renders results with `rich`
2. **`ig_client.py`** — authenticates with Instagram via a browser `sessionid` cookie injected into `instaloader`, then paginates comments via the Instagram web GraphQL API (not the official API)
3. **`reddit_client.py`** — fetches posts and comments from Reddit's public `.json` endpoint; expands collapsed "more" stubs via `morechildren.json`
4. **`summariser.py`** — builds a text prompt, calls Google Gemini with `response_schema=AnalysisResult` for structured JSON output, retries up to 2 times on failure
5. **`models.py`** — all Pydantic models: input data (`IGPost`, `RedditPost`, `IGComment`, `RedditComment`) and Gemini output schema (`AnalysisResult`, `Theme`, `Camp`, `CommenterSentiment`, `Sentiment`)
6. **`config.py`** — reads all env vars at import time; raises `SystemExit` immediately if required vars are missing

### Key design decisions

- **Structured Gemini output**: Gemini is called with `response_mime_type="application/json"` and `response_schema=AnalysisResult` — the response is validated directly with `AnalysisResult.model_validate_json()`. Do not change the schema without updating the prompt instructions accordingly.
- **Comment sampling**: For analysis, comments are sorted by likes/upvotes descending and capped at `MAX_COMMENTS_FOR_ANALYSIS` (default 100). The fetch cap (`MAX_COMMENTS`, default 500) is separate.
- **Analysis modes**: `--analysis` controls both the Gemini prompt (via `_camps_instruction()`) and what gets displayed. The three modes are `both` (default), `sentiment`, and `camps`.
- **Instagram uses unofficial API**: `ig_client.py` uses hardcoded GraphQL query hashes. These may break if Instagram changes their API.
- **No test suite**: There are currently no automated tests.
