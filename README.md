# Instagram Comment Summariser

CLI tool that fetches comments from an Instagram post and uses Google Gemini to produce a structured analysis: a discussion summary, recurring themes, and per-commenter sentiment breakdown.

## Quick start

**1. Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Set environment variables**

```bash
export GEMINI_API_KEY='your-gemini-api-key'
export IG_SESSION_ID='your-instagram-session-id'
```

To get your `IG_SESSION_ID`: open Instagram.com in your browser → DevTools (F12) → Application → Cookies → `www.instagram.com` → copy the value of `sessionid`.

**3. Run it**

```bash
.venv/bin/python3 main.py <instagram_post_url>
```

Example:

```bash
.venv/bin/python3 main.py https://www.instagram.com/p/ABC123/
```

Works with `/p/`, `/reel/`, and `/tv/` URLs.

## Output

- **Post header** — caption preview, author, likes, comment count
- **Comment summary** — 3-5 sentence overview of what people are saying
- **Recurring themes** — 2-5 topics that appear frequently across comments
- **Sentiment breakdown** — bar chart of positive/negative/neutral split
- **Per-commenter table** — each commenter's sentiment with a one-line reason

## Configuration

All options are set via environment variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key |
| `IG_SESSION_ID` | Yes | — | Instagram session cookie from your browser |
| `GEMINI_MODEL` | No | `gemini-3-flash-preview` | Gemini model to use |
| `MAX_COMMENTS` | No | `500` | Max comments to fetch from Instagram (0 = all) |
| `MAX_COMMENTS_FOR_ANALYSIS` | No | `100` | Max comments sent to Gemini (top by likes) |
| `MAX_COMMENT_CHARS` | No | `800000` | Character limit for comment text sent to Gemini |

> **Note:** This tool uses the unofficial Instagram API. Use a secondary account, not your main.
