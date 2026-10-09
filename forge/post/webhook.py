"""Generic webhook poster: for anything with an incoming-webhook URL.

Use for Discord webhooks, Telegram bots, Zapier/Make catch hooks, or your
own server endpoint. POSTs JSON; never pretends to be a platform API.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


class WebhookError(Exception):
    """Raised when the webhook call fails."""


def post_webhook(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    """POST ``payload`` as JSON to ``url``. Returns status + response body."""
    if not url.startswith(("https://", "http://")):
        raise WebhookError(f"Refusing to post to non-HTTP URL: {url!r}")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return {"status": resp.status, "body": body[:2000]}
    except urllib.error.HTTPError as e:
        raise WebhookError(
            f"Webhook returned HTTP {e.code}: {e.read()[:500]!r}") from e
    except Exception as e:  # network errors etc.
        raise WebhookError(f"Webhook call failed: {e}") from e
