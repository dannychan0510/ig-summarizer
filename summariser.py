from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types

logging.getLogger("google_genai.types").setLevel(logging.ERROR)

import config
from models import AnalysisResult, IGComment, IGPost, RedditComment, RedditPost

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2


def _sample_comments(comments: list[IGComment]) -> list[IGComment]:
    """Return up to MAX_COMMENTS_FOR_ANALYSIS comments, sorted by likes descending.

    The most-engaged comments are the most representative of the discussion.
    """
    sorted_comments = sorted(comments, key=lambda c: c.likes_count, reverse=True)
    return sorted_comments[: config.MAX_COMMENTS_FOR_ANALYSIS]


def _truncate_to_char_limit(comments: list[IGComment]) -> tuple[list[IGComment], bool]:
    """Drop comments from the end until the total text fits within MAX_COMMENT_CHARS."""
    kept: list[IGComment] = []
    total = 0
    for c in comments:
        chunk = len(c.author) + len(c.text) + 50
        if total + chunk > config.MAX_COMMENT_CHARS:
            return kept, True
        kept.append(c)
        total += chunk
    return kept, False


def _build_prompt(post: IGPost, mode: str = "both") -> str:
    """Build the Gemini analysis prompt from post data."""
    sampled = _sample_comments(post.comments)
    sampled, was_truncated = _truncate_to_char_limit(sampled)

    note = ""
    if len(post.comments) > config.MAX_COMMENTS_FOR_ANALYSIS:
        note = f" (top {len(sampled)} by likes shown out of {post.comment_count} total)"
    elif was_truncated:
        note = f" ({len(sampled)} shown, truncated to fit context limit)"

    formatted: list[str] = []
    for c in sampled:
        likes_label = f" | {c.likes_count} likes" if c.likes_count else ""
        formatted.append(f"[@{c.author}{likes_label}]\n{c.text}")

    comments_text = "\n\n".join(formatted) if formatted else "(No comments)"

    return f"""You are an expert at analysing social media discussions.

Analyse the comments on the following Instagram post.

=== POST ===
URL: {post.url}
Author: @{post.author}
Likes: {post.like_count:,}
Caption:
{post.caption or '(no caption)'}

=== COMMENTS ({len(sampled)} total{note}) ===
{comments_text}

Based on the comments above:
1. Write a 3-5 sentence summary of what people are saying overall.
2. Identify 2-5 recurring themes or topics across the comments.
{_camps_instruction(mode, len(sampled))}"""


def _camps_instruction(mode: str, n: int) -> str:
    if mode == "sentiment":
        return (
            f"3. For EVERY SINGLE commenter listed above, classify their sentiment as positive, negative, or neutral "
            f"with a brief reason. Do not skip anyone — analyse all {n} commenters."
        )
    return (
        f"3. If the discussion has a clear split — where commenters are debating opposing viewpoints — identify 2-3 camps "
        f'with short labels (e.g. "Pro-change", "Anti-change"). If there is no meaningful divide, leave camps empty.\n'
        f"4. For EVERY SINGLE commenter listed above, classify their sentiment (positive/negative/neutral) and, if camps "
        f"were identified, assign them to the camp that best matches their view (use the exact camp label, or null if they "
        f"don't clearly align). Do not skip anyone — analyse all {n} commenters."
    )


def _build_reddit_prompt(post: RedditPost, mode: str = "both") -> str:
    """Build the Gemini analysis prompt from a Reddit post."""
    sampled = sorted(post.comments, key=lambda c: c.score, reverse=True)
    sampled = sampled[: config.MAX_COMMENTS_FOR_ANALYSIS]

    kept: list[RedditComment] = []
    total_chars = 0
    was_truncated = False
    for c in sampled:
        chunk = len(c.author) + len(c.text) + 50
        if total_chars + chunk > config.MAX_COMMENT_CHARS:
            was_truncated = True
            break
        kept.append(c)
        total_chars += chunk

    note = ""
    if len(post.comments) > config.MAX_COMMENTS_FOR_ANALYSIS:
        note = f" (top {len(kept)} by upvotes shown out of {post.num_comments} total)"
    elif was_truncated:
        note = f" ({len(kept)} shown, truncated to fit context limit)"

    formatted: list[str] = []
    for c in kept:
        score_label = f" | {c.score} upvotes" if c.score else ""
        formatted.append(f"[@{c.author}{score_label}]\n{c.text}")

    comments_text = "\n\n".join(formatted) if formatted else "(No comments)"

    body = f"Title: {post.title}"
    if post.selftext:
        body += f"\n{post.selftext[:500]}"
        if len(post.selftext) > 500:
            body += "…"

    return f"""You are an expert at analysing social media discussions.

Analyse the comments on the following Reddit post.

=== POST ===
URL: {post.url}
Subreddit: r/{post.subreddit}
Author: u/{post.author}
Upvotes: {post.score:,}
{body}

=== COMMENTS ({len(kept)} total{note}) ===
{comments_text}

Based on the comments above:
1. Write a 3-5 sentence summary of what people are saying overall.
2. Identify 2-5 recurring themes or topics across the comments.
{_camps_instruction(mode, len(kept))}"""


def analyse_reddit_post(post: RedditPost, mode: str = "both") -> AnalysisResult:
    """Send Reddit post comments to Gemini and return structured analysis.

    Raises:
        RuntimeError: If Gemini API fails after retries.
    """
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _build_reddit_prompt(post, mode)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AnalysisResult,
                ),
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty response")
            return AnalysisResult.model_validate_json(response.text)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Gemini API failed after {MAX_RETRIES + 1} attempts: {last_error}")


def analyse_post(post: IGPost, mode: str = "both") -> AnalysisResult:
    """Send post comments to Gemini and return structured analysis.

    Raises:
        RuntimeError: If Gemini API fails after retries.
    """
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _build_prompt(post, mode)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AnalysisResult,
                ),
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty response")
            return AnalysisResult.model_validate_json(response.text)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Gemini API failed after {MAX_RETRIES + 1} attempts: {last_error}")
