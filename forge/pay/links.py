"""Payment links + tip menu page.

Builds shareable payment URLs from handles in forge.yaml (``pay.*``).
These are plain links -- no money moves through CreatorForge itself.
"""

from __future__ import annotations

import html
from typing import Any


def _clean(handle: str) -> str:
    return handle.strip().lstrip("@$")


def build_payment_links(config: dict[str, Any]) -> dict[str, str]:
    """Return ``{label: url}`` for every payment handle configured.

    Supported keys under ``pay``: ``venmo``, ``cashapp``, ``paypal_me``,
    ``crypto_btc``, ``crypto_eth``, ``throne``, ``custom`` (dict of
    label -> url). Empty values are skipped.
    """
    pay = config.get("pay", {}) or {}
    links: dict[str, str] = {}
    if pay.get("venmo"):
        links["Venmo"] = f"https://venmo.com/{_clean(str(pay['venmo']))}"
    if pay.get("cashapp"):
        links["Cash App"] = f"https://cash.app/{_clean(str(pay['cashapp']))}"
    if pay.get("paypal_me"):
        links["PayPal"] = f"https://paypal.me/{_clean(str(pay['paypal_me']))}"
    if pay.get("crypto_btc"):
        links["Bitcoin"] = f"bitcoin:{_clean(str(pay['crypto_btc']))}"
    if pay.get("crypto_eth"):
        links["Ethereum"] = f"ethereum:{_clean(str(pay['crypto_eth']))}"
    if pay.get("throne"):
        links["Throne"] = str(pay["throne"]).strip()
    custom = pay.get("custom") or {}
    for label, url in custom.items():
        if url:
            links[str(label)] = str(url).strip()
    return links


def tip_menu_html(
    links: dict[str, str],
    menu_items: list[dict[str, Any]] | None = None,
    *,
    title: str = "Tip Menu",
) -> str:
    """Generate a small standalone HTML tip-menu page.

    ``menu_items``: list of ``{"label": ..., "price": ...}`` dicts.
    All text is HTML-escaped.
    """
    items_html = ""
    for item in menu_items or []:
        label = html.escape(str(item.get("label", "")))
        price = html.escape(str(item.get("price", "")))
        items_html += f"<li><span>{label}</span><strong>{price}</strong></li>\n"
    links_html = ""
    for label, url in links.items():
        links_html += (
            f'<a class="pay" href="{html.escape(url, quote=True)}">'
            f"{html.escape(label)}</a>\n"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:480px;margin:2rem auto;padding:0 1rem}}
.pay{{display:block;margin:.5rem 0;padding:.8rem;background:#111;color:#fff;
text-align:center;border-radius:10px;text-decoration:none}}
li{{display:flex;justify-content:space-between;padding:.4rem 0;
border-bottom:1px solid #eee;list-style:none}}ul{{padding:0}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<ul>{items_html}</ul>
<h2>Pay</h2>
{links_html}
</body></html>
"""
