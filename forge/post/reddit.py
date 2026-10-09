"""Reddit posting via the official API (PRAW).

Reddit is the one platform here with a real, supported posting API.
You need a Reddit app (https://www.reddit.com/prefs/apps) to get a
client_id/client_secret, then put them in forge.yaml under
``platforms.reddit``.

Dry-run is the DEFAULT: nothing is submitted unless ``dry_run=False``
is passed explicitly. Always test in your own test subreddit first.
Follow each subreddit's rules -- spam gets accounts banned, API or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forge.config import ForgeConfig


class RedditNotConfiguredError(Exception):
    """Raised when Reddit credentials are missing."""


@dataclass
class RedditPost:
    kind: str  # 'text' | 'image' | 'video'
    subreddit: str
    title: str
    body: str = ""
    media_path: str = ""
    flair_id: str = ""
    dry_run: bool = True


def _require_praw():  # pragma: no cover - import guard
    try:
        import praw
    except ImportError as e:
        raise RuntimeError(
            "praw is not installed. Run: pip install creator-forge "
            "(praw is a default dependency)."
        ) from e
    return praw


def reddit_client(config: ForgeConfig):
    """Build an authenticated PRAW Reddit instance."""
    praw = _require_praw()
    section = config.get_path("platforms.reddit", {}) or {}
    needed = ["client_id", "client_secret", "username", "password"]
    missing = [k for k in needed if not section.get(k)]
    if missing:
        raise RedditNotConfiguredError(
            "Reddit not configured. Missing platforms.reddit fields: "
            + ", ".join(missing) + ".\n"
            "1. Create an app at https://www.reddit.com/prefs/apps (type: script).\n"
            "2. Put client_id, client_secret, username, password in forge.yaml.\n"
            "3. Set a descriptive user_agent, e.g. 'creator-forge/0.1 by u/yourname'."
        )
    return praw.Reddit(
        client_id=section["client_id"],
        client_secret=section["client_secret"],
        username=section["username"],
        password=section["password"],
        user_agent=section.get("user_agent", "creator-forge/0.1"),
    )


def submit(post: RedditPost, config: ForgeConfig) -> dict[str, Any]:
    """Submit a post. Returns a summary dict; in dry-run mode the summary
    describes what WOULD have been posted and nothing is sent."""
    summary = {
        "kind": post.kind,
        "subreddit": post.subreddit,
        "title": post.title,
        "dry_run": post.dry_run,
        "url": None,
    }
    if post.dry_run:
        summary["note"] = (
            "DRY RUN -- nothing was submitted. "
            "Pass dry_run=False to actually post."
        )
        return summary

    reddit = reddit_client(config)
    sub = reddit.subreddit(post.subreddit)
    if post.kind == "text":
        submission = sub.submit(
            post.title, selftext=post.body, flair_id=post.flair_id or None)
    elif post.kind in ("image", "video"):
        if not post.media_path:
            raise ValueError(f"{post.kind} posts need media_path.")
        submission = sub.submit_image(
            post.title, post.media_path, flair_id=post.flair_id or None)
        # NOTE: PRAW submits video via submit_image too (Reddit treats it as
        # a media post); use post.kind='video' just for your own bookkeeping.
    else:
        raise ValueError(f"Unknown post kind {post.kind!r}.")
    summary["url"] = f"https://reddit.com{submission.permalink}"
    summary["id"] = submission.id
    return summary
