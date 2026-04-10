from __future__ import annotations

import re
import time
from typing import Any

import requests

import config
from models import RedditComment, RedditPost

# Match both old and new Reddit URLs
# e.g. reddit.com/r/python/comments/abc123/title/
_POST_PATTERN = re.compile(
    r"reddit\.com/r/[^/]+/comments/([A-Za-z0-9]+)"
)

_HEADERS = {"User-Agent": "reddit-summarizer/1.0 (personal use)"}
_REQUEST_DELAY = 2.0  # seconds between requests to stay within rate limits


def _parse_post_id(url: str) -> str:
    url = url.strip().rstrip("/")
    match = _POST_PATTERN.search(url)
    if not match:
        raise ValueError(
            f"Could not parse Reddit post URL: {url}\n"
            "Expected format: https://www.reddit.com/r/<subreddit>/comments/<id>/<title>/"
        )
    return match.group(1)


def fetch_post(url: str) -> RedditPost:
    """Fetch a Reddit post and all its comments.

    Raises:
        ValueError: Bad URL or post not found.
        PermissionError: Subreddit is private.
        ConnectionError: Network or API failure.
    """
    post_id = _parse_post_id(url)

    json_url = f"https://www.reddit.com/comments/{post_id}.json?limit=500&depth=10"
    try:
        resp = requests.get(json_url, headers=_HEADERS, timeout=15)
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to fetch Reddit post: {e}")

    if resp.status_code == 404:
        raise ValueError(f"Reddit post not found: {url}")
    if resp.status_code == 403:
        raise PermissionError(f"Subreddit is private or quarantined: {url}")
    if not resp.ok:
        raise ConnectionError(f"Reddit returned HTTP {resp.status_code} for: {url}")

    data = resp.json()
    post_listing = data[0]["data"]["children"][0]["data"]
    comment_listing = data[1]["data"]["children"]

    subreddit = post_listing.get("subreddit", "")
    author = post_listing.get("author", "[deleted]")
    title = post_listing.get("title", "")
    selftext = post_listing.get("selftext", "")
    score = post_listing.get("score", 0)
    num_comments = post_listing.get("num_comments", 0)

    comments: list[RedditComment] = []
    more_stubs: list[str] = []  # child IDs to expand

    _collect_comments(comment_listing, comments, more_stubs)

    # Expand "more" stubs until we hit the cap or exhaust them
    if more_stubs and (config.MAX_COMMENTS == 0 or len(comments) < config.MAX_COMMENTS):
        _expand_more(post_id, more_stubs, comments)

    if config.MAX_COMMENTS:
        comments = comments[: config.MAX_COMMENTS]

    return RedditPost(
        url=url,
        post_id=post_id,
        title=title,
        selftext=selftext,
        author=author,
        score=score,
        num_comments=num_comments,
        subreddit=subreddit,
        comments=comments,
    )


def _collect_comments(
    listing: list[dict[str, Any]],
    out: list[RedditComment],
    more_out: list[str],
) -> None:
    """Recursively walk a Reddit comment listing, collecting comments and more-stubs."""
    for item in listing:
        kind = item.get("kind")
        data = item.get("data", {})

        if kind == "more":
            more_out.extend(data.get("children", []))
            continue

        if kind != "t1":
            continue

        author = data.get("author", "[deleted]")
        text = data.get("body", "")
        score = data.get("score", 0)
        comment_id = data.get("id", "")

        # Skip deleted/removed comments
        if text in ("[deleted]", "[removed]", ""):
            continue

        out.append(RedditComment(
            author=author,
            text=text,
            score=score,
            comment_id=comment_id,
        ))

        # Recurse into replies
        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_children = replies.get("data", {}).get("children", [])
            _collect_comments(reply_children, out, more_out)


def _expand_more(
    post_id: str,
    child_ids: list[str],
    out: list[RedditComment],
) -> None:
    """Fetch collapsed comments via the morechildren API, batching up to 100 IDs at a time."""
    link_fullname = f"t3_{post_id}"
    batch_size = 100

    for i in range(0, len(child_ids), batch_size):
        if config.MAX_COMMENTS and len(out) >= config.MAX_COMMENTS:
            break

        batch = child_ids[i : i + batch_size]
        time.sleep(_REQUEST_DELAY)

        try:
            resp = requests.get(
                "https://www.reddit.com/api/morechildren.json",
                headers=_HEADERS,
                params={
                    "link_id": link_fullname,
                    "children": ",".join(batch),
                    "api_type": "json",
                    "limit_children": False,
                },
                timeout=15,
            )
        except requests.RequestException:
            break

        if not resp.ok:
            break

        things = resp.json().get("json", {}).get("data", {}).get("things", [])

        # morechildren returns a flat list — t1 are comments, more are further stubs
        nested_more: list[str] = []
        _collect_comments(things, out, nested_more)

        # Recurse into any further stubs returned in this batch
        if nested_more and (config.MAX_COMMENTS == 0 or len(out) < config.MAX_COMMENTS):
            _expand_more(post_id, nested_more, out)
        break  # only recurse one level; avoid unbounded depth
