"""PPV upsell triggers: chat keyword -> PPV offer draft.

When a fan's message looks like buying intent ("how much", "ppv",
"buy", ...), draft an offer built from HER price menu + payment links.
The draft goes through the normal approval queue -- the PPV engine
never sends anything itself.
"""

from __future__ import annotations

import re
from typing import Any

BUY_KEYWORDS = (
    "ppv", "buy", "price", "how much", "cost", "custom", "purchase",
    "pay for", "send me", "want the video", "want pics",
)
# Word boundaries: "custom" must not fire on "customer", "buy" on "buyer".
BUY_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in BUY_KEYWORDS)
                    + r")\b", re.IGNORECASE)


def _norm_price(raw: object) -> str:
    """Normalize a price to its bare number: '$25.00' -> '25', '25' -> '25'."""
    m = re.search(r"\d+(?:\.\d{1,2})?", str(raw or ""))
    if not m:
        return ""
    return m.group(0).rstrip("0").rstrip(".") or "0"


def looks_like_buying(text: str) -> bool:
    """Heuristic: does this message smell like buying intent?"""
    return BUY_RE.search(text or "") is not None


def ppv_offer_text(*, fan_message: str, price_menu: list[dict[str, Any]],
                   pay_links: dict[str, str],
                   sender: str = "") -> str | None:
    """Build a PPV offer draft, or None if the message isn't buying intent.

    Picks the price-menu item whose label best matches the fan's words
    (simple keyword overlap), preferring an exact price match when the
    fan names an amount ("the $25 one"). Falls back to the first item.
    """
    if not looks_like_buying(fan_message):
        return None
    if not price_menu:
        return None
    # Exact price match wins: "$25" / "25 dollars" in the message vs item prices.
    msg_prices = {_norm_price(m) for m in re.findall(
        r"\$\s*\d+(?:\.\d{1,2})?|\b\d+(?:\.\d{1,2})?\s*(?:dollars|bucks|usd)\b",
        fan_message, re.IGNORECASE)}
    msg_prices.discard("")
    for item in price_menu:
        if _norm_price(item.get("price", "")) in msg_prices:
            best = item
            break
    else:
        words = set(re.findall(r"[a-z]+", fan_message.lower()))
        best, best_score = price_menu[0], 0
        for item in price_menu:
            label_words = set(
                re.findall(r"[a-z]+", str(item.get("label", "")).lower()))
            score = len(words & label_words)
            if score > best_score:
                best, best_score = item, score
    label = best.get("label", "custom content")
    price = best.get("price", "")
    pay = ""
    if pay_links:
        first_label = next(iter(pay_links))
        pay = f" ({first_label}: {pay_links[first_label]})"
    name = f" {sender}" if sender else ""
    offer = (f"Yess{name} I can do that for you -- {label}"
             + (f" is {price}" if price else "") + pay
             + " -- just lmk and I'll send it over right after")
    return offer
