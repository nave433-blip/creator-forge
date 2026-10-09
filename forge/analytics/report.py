"""Plain-English analytics report.

Turns the raw numbers in :class:`AnalyticsStore` into a readable
summary: what earned what, which platforms are working, which posts
did best. No jargon, no fake precision -- it says where each number
came from (manual entry, CSV import, or the Reddit API).
"""

from __future__ import annotations

from forge.analytics.store import AnalyticsStore


def _money(x: float) -> str:
    return f"${x:,.2f}"


def build_report(store: AnalyticsStore, top_n: int = 5) -> str:
    """Return the report as a plain-text string."""
    totals = store.totals()
    by_pm = store.earnings_by_platform_month()
    posts = store.post_stats(limit=top_n * 3)

    lines = ["=== CreatorForge analytics report ===", ""]
    lines.append(f"Total earnings logged: {_money(totals['total_earnings'])}")
    lines.append(f"Posts tracked: {totals['posts_tracked']} "
                 f"({totals['total_views']:,} views, "
                 f"{totals['total_likes']:,} likes, "
                 f"{totals['total_comments']:,} comments)")
    lines.append("")

    if by_pm:
        lines.append("Earnings by platform and month:")
        for row in by_pm:
            lines.append(f"  {row['month']}  {row['platform']:12} "
                         f"{_money(row['total'])} ({row['entries']} entries)")
        lines.append("")
    else:
        lines.append("No earnings logged yet. Add some with:")
        lines.append("  forge analytics log-earning --platform onlyfans "
                     "--amount 120 --kind subs")
        lines.append("")

    # best posts by engagement (likes + comments), simple and honest
    ranked = sorted(posts,
                    key=lambda p: (p["likes"] or 0) + (p["comments"] or 0),
                    reverse=True)[:top_n]
    if ranked:
        lines.append(f"Top {len(ranked)} posts by engagement:")
        for p in ranked:
            label = p["title"] or p["post_ref"]
            lines.append(
                f"  [{p['platform']}] {label}: "
                f"{p['views']:,} views, {p['likes']:,} likes, "
                f"{p['comments']:,} comments")
        lines.append("")

    lines.append("Where these numbers come from:")
    lines.append("  - earnings/post stats: entered by you or imported from "
                 "CSV exports you download from each site")
    lines.append("  - Reddit stats: fetched live from Reddit's official API")
    lines.append("  OnlyFans / Fansly / Snapchat have no stats API, so those "
                 "numbers are only as fresh as your last manual entry.")
    return "\n".join(lines)
