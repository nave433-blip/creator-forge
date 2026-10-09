"""Analytics insights: LTV/ARPU, peak posting times, per-post rankings.

Honest inputs: earnings/post stats she logs or imports (CSV), fan counts
from the CRM, live Reddit stats via PRAW. LTV here = recorded lifetime
spend per fan; ARPU = recorded earnings / fan count. These describe what
SHE recorded -- they are only as complete as her logging.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def ltv_arpu(*, total_earnings: float, fan_count: int,
             fan_spends: list[float] | None = None) -> dict[str, Any]:
    """Lifetime value + average revenue per user from recorded data."""
    fan_count = max(1, fan_count)
    avg_ltv = total_earnings / fan_count
    result: dict[str, Any] = {
        "total_earnings": total_earnings,
        "fan_count": fan_count,
        "arpu": round(total_earnings / fan_count, 2),
        "avg_ltv": round(avg_ltv, 2),
        "method": "recorded earnings / CRM fan count (only as complete "
                  "as her logging)",
    }
    if fan_spends:
        spends = sorted(fan_spends)
        result["median_fan_spend"] = round(
            spends[len(spends) // 2], 2) if spends else 0.0
        result["top_10pct_share"] = round(
            sum(spends[int(len(spends) * 0.9):]) / max(1, sum(spends)), 3)
    return result


def peak_posting_times(post_stats: list[dict[str, Any]],
                       top_n: int = 5) -> list[dict[str, Any]]:
    """Best hours/days to post, from HER recorded post stats.

    Scores each (weekday, hour) bucket by likes+comments per post.
    Needs a decent sample to mean anything -- says so when thin.
    """
    buckets: dict[tuple[str, int], list[float]] = defaultdict(list)
    for p in post_stats:
        try:
            dt = datetime.fromisoformat(str(p.get("recorded_at", "")))
        except ValueError:
            continue
        engagement = (p.get("likes", 0) or 0) + (p.get("comments", 0) or 0)
        buckets[(dt.strftime("%a"), dt.hour)].append(engagement)
    ranked = []
    for (day, hour), vals in buckets.items():
        ranked.append({"weekday": day, "hour": hour,
                       "posts": len(vals),
                       "avg_engagement": round(sum(vals) / len(vals), 1)})
    ranked.sort(key=lambda r: r["avg_engagement"], reverse=True)
    total = sum(r["posts"] for r in ranked)
    note = ("based on recorded post stats" if total >= 20
            else f"thin sample ({total} posts) -- log more for real signal")
    return [{"note": note, **r} for r in ranked[:top_n]]


def per_post_ranking(post_stats: list[dict[str, Any]],
                     limit: int = 20) -> list[dict[str, Any]]:
    """Her posts ranked by recorded earnings, then engagement."""
    def _score(p: dict[str, Any]) -> tuple:
        return (p.get("earnings", 0) or 0,
                (p.get("likes", 0) or 0) + (p.get("comments", 0) or 0))
    ranked = sorted(post_stats, key=_score, reverse=True)[:limit]
    return [{
        "platform": p.get("platform"), "post_ref": p.get("post_ref"),
        "title": p.get("title"), "views": p.get("views"),
        "likes": p.get("likes"), "comments": p.get("comments"),
        "earnings": p.get("earnings"),
    } for p in ranked]


def plain_english_summary(*, totals: dict[str, Any],
                          ltv: dict[str, Any],
                          peaks: list[dict[str, Any]]) -> str:
    """One-paragraph readable summary for the dashboard/CLI."""
    lines = [
        f"Recorded earnings: ${totals.get('total_earnings', 0):,.2f} across "
        f"{totals.get('posts_tracked', 0)} tracked posts.",
        f"ARPU: ${ltv.get('arpu', 0):,.2f} over {ltv.get('fan_count', 0)} "
        f"fans in the CRM.",
    ]
    if peaks:
        p = peaks[0]
        lines.append(
            f"Best posting slot in her data: {p['weekday']}s around "
            f"{p['hour']:02d}:00 (avg engagement {p['avg_engagement']}).")
    lines.append("All figures reflect what she logged -- gaps in logging "
                 "are gaps in the numbers.")
    return " ".join(lines)
