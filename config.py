import os

from dotenv import load_dotenv

# Load GEMINI_API_KEY from the project-root .env if present, falling back to the
# ambient environment when no .env exists.
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise SystemExit(
        "Error: GEMINI_API_KEY is not set.\n"
        "Add it to a .env file at the project root: GEMINI_API_KEY=your-key\n"
        "or export it in your shell: export GEMINI_API_KEY='your-key'"
    )

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
MAX_COMMENT_CHARS = int(os.getenv("MAX_COMMENT_CHARS", "800000"))

# Max comments to fetch from Instagram — 0 means all (can be slow for viral posts)
MAX_COMMENTS = int(os.getenv("MAX_COMMENTS", "500"))

# Max comments to send to Gemini for analysis (top by likes)
MAX_COMMENTS_FOR_ANALYSIS = int(os.getenv("MAX_COMMENTS_FOR_ANALYSIS", "100"))

# Instagram session ID cookie from your browser.
# How to get it: Instagram.com → DevTools (F12) → Application → Cookies
#   → www.instagram.com → copy the value of 'sessionid'
# Only required when analysing Instagram posts.
IG_SESSION_ID = os.getenv("IG_SESSION_ID")


def require_ig_session_id() -> str:
    """Return IG_SESSION_ID or exit with a helpful message if unset."""
    if not IG_SESSION_ID:
        raise SystemExit(
            "Error: IG_SESSION_ID environment variable must be set.\n"
            "Get it from your browser:\n"
            "  1. Open Instagram.com and log in\n"
            "  2. Open DevTools (F12) → Application → Cookies → www.instagram.com\n"
            "  3. Copy the value of 'sessionid'\n"
            "  4. export IG_SESSION_ID='paste-value-here'"
        )
    return IG_SESSION_ID
