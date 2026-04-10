from __future__ import annotations

import json
import re
import time

import instaloader

import config
from models import IGComment, IGPost

SHORTCODE_PATTERN = re.compile(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)")

# Web GraphQL query hashes used by instaloader's non-iPhone path
_COMMENTS_QUERY_HASH = "97b41c52301f77ce508f55e66d17620e"
_REPLIES_QUERY_HASH = "51fdd02b67508306ad4484ff574a0b62"
_PAGE_SIZE = 50


def _build_loader() -> instaloader.Instaloader:
    """Return an Instaloader instance authenticated via the browser session cookie.

    Injects the sessionid cookie directly into the requests.Session, then calls
    test_login() to validate it — no username/password login needed.
    """
    L = instaloader.Instaloader(iphone_support=False, quiet=True)

    # Inject the session cookie from the user's real browser
    L.context._session.cookies.set(
        "sessionid", config.require_ig_session_id(), domain=".instagram.com"
    )

    # Grab a CSRF token by hitting instagram.com (needed for API calls)
    try:
        L.context._session.get("https://www.instagram.com/", timeout=15)
    except Exception:
        pass

    # Verify the session is valid
    username = L.test_login()
    if not username:
        raise ConnectionError(
            "IG_SESSION_ID is invalid or expired. "
            "Please refresh it from your browser's DevTools."
        )

    L.context.username = username
    return L


def _parse_shortcode(url: str) -> str:
    url = url.strip().rstrip("/")
    match = SHORTCODE_PATTERN.search(url)
    if not match:
        raise ValueError(
            f"Could not parse Instagram post URL: {url}\n"
            "Expected format: https://www.instagram.com/p/<shortcode>/"
        )
    return match.group(1)


def fetch_post(url: str) -> IGPost:
    """Fetch an Instagram post and all its comments.

    Raises:
        ValueError: Bad URL or post not found.
        PermissionError: Private account.
        ConnectionError: Auth or network failure.
    """
    shortcode = _parse_shortcode(url)

    try:
        L = _build_loader()
    except ConnectionError:
        raise
    except Exception as e:
        raise ConnectionError(f"Failed to initialise Instagram session: {e}")

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except instaloader.exceptions.ProfileNotExistsException:
        raise ValueError(f"Instagram post not found: {url}")
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        raise PermissionError(f"Post belongs to a private account: {url}")
    except Exception as e:
        raise ConnectionError(f"Failed to fetch post: {e}")

    caption = post.caption or ""
    author = post.owner_username or "(unknown)"
    like_count = post.likes or 0
    comment_count = post.comments or 0

    comments = _graphql_comments(L.context, shortcode)

    return IGPost(
        url=url,
        shortcode=shortcode,
        caption=caption,
        author=author,
        like_count=like_count,
        comment_count=comment_count,
        comments=comments,
    )


def _graphql_comments(
    context: instaloader.InstaloaderContext,
    shortcode: str,
) -> list[IGComment]:
    """Fetch all comments via the Instagram web GraphQL endpoint."""
    comments: list[IGComment] = []
    seen_ids: set[str] = set()
    cursor: str | None = None
    max_comments = config.MAX_COMMENTS

    while True:
        variables: dict = {"shortcode": shortcode, "first": _PAGE_SIZE}
        if cursor:
            variables["after"] = cursor

        try:
            data = context.get_json(
                "graphql/query/",
                params={
                    "query_hash": _COMMENTS_QUERY_HASH,
                    "variables": json.dumps(variables),
                },
            )
        except Exception as e:
            raise ConnectionError(f"GraphQL comments query failed: {e}")

        edge_data = (
            data.get("data", {})
            .get("shortcode_media", {})
            .get("edge_media_to_parent_comment", {})
        )
        if not edge_data:
            break

        for edge in edge_data.get("edges", []):
            node = edge.get("node", {})
            cid = str(node.get("id", ""))
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)

            owner = node.get("owner", {})
            comments.append(IGComment(
                author=owner.get("username", "(unknown)"),
                text=node.get("text", ""),
                likes_count=node.get("edge_liked_by", {}).get("count", 0),
                comment_id=cid,
            ))

            # Collect embedded replies, paginating if there are more
            threaded = node.get("edge_threaded_comments", {})
            reply_count = threaded.get("count", 0)
            reply_edges = threaded.get("edges", [])
            if reply_count > len(reply_edges):
                reply_edges = _fetch_replies(context, cid) or reply_edges

            for r_edge in reply_edges:
                r_node = r_edge.get("node", {})
                rid = str(r_node.get("id", ""))
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)
                r_owner = r_node.get("owner", {})
                comments.append(IGComment(
                    author=r_owner.get("username", "(unknown)"),
                    text=r_node.get("text", ""),
                    likes_count=r_node.get("edge_liked_by", {}).get("count", 0),
                    comment_id=rid,
                ))

            if max_comments and len(comments) >= max_comments:
                return comments

        page_info = edge_data.get("page_info", {})
        if not page_info.get("has_next_page"):
            break
        cursor = page_info.get("end_cursor")
        if not cursor:
            break

        time.sleep(1.0)

    return comments


def _fetch_replies(
    context: instaloader.InstaloaderContext,
    comment_id: str,
) -> list[dict]:
    """Paginate through all replies for a single comment."""
    all_edges: list[dict] = []
    cursor: str | None = None

    for _ in range(10):
        variables: dict = {"comment_id": comment_id, "first": _PAGE_SIZE}
        if cursor:
            variables["after"] = cursor

        try:
            data = context.get_json(
                "graphql/query/",
                params={
                    "query_hash": _REPLIES_QUERY_HASH,
                    "variables": json.dumps(variables),
                },
            )
        except Exception:
            break

        edge_data = (
            data.get("data", {})
            .get("comment", {})
            .get("edge_threaded_comments", {})
        )
        all_edges.extend(edge_data.get("edges", []))

        page_info = edge_data.get("page_info", {})
        if not page_info.get("has_next_page"):
            break
        cursor = page_info.get("end_cursor")
        if not cursor:
            break
        time.sleep(0.5)

    return all_edges
