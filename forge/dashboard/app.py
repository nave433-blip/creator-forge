"""Local dashboard (FastAPI): catalog browser, identity status, chat
approval queue, payment links, posting packets.

Runs on localhost only by default. This is an operator console, not a
public site -- do not expose it to the internet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from forge.catalog.store import CatalogStore
from forge.chat.engine import ApprovalQueue, Draft, Persona, RuleEngine
from forge.config import ForgeConfig, load_config
from forge.identity.pack import (
    InvalidConsentError,
    load_identity_pack,
    validate_identity_pack,
)
from forge.pay.links import build_payment_links

app = FastAPI(title="CreatorForge Dashboard")

_state: dict[str, Any] = {}

bearer = HTTPBearer(auto_error=False)
_PUBLIC_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}


def _require_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    """Optional bearer-token auth.

    If ``dashboard.api_token`` is set in forge.yaml (or the
    ``FORGE_DASHBOARD_API_TOKEN`` env var), every non-public route
    requires ``Authorization: Bearer <token>``. If it is not set, the
    dashboard is open -- fine on localhost, do NOT expose it publicly
    without setting a token.
    """
    if (request.url.path in _PUBLIC_PATHS
            or request.url.path.startswith("/static/")):
        return
    expected = _state.get("config", {}).get_path("dashboard.api_token")
    if not expected:
        return
    if creds is None or creds.scheme.lower() != "bearer" \
            or creds.credentials != expected:
        raise HTTPException(401, "Invalid or missing API token.")


def _engine() -> RuleEngine:
    return _state["engine"]


def _store() -> CatalogStore:
    return _state["store"]


def _config() -> ForgeConfig:
    return _state["config"]


def init_state(config: ForgeConfig, db_path: str | Path,
               persona_config: dict[str, Any] | None = None) -> None:
    _state["config"] = config
    _state["store"] = CatalogStore(db_path)
    pdata = persona_config or config.get_path("persona", {}) or {}
    _state["engine"] = RuleEngine(
        Persona.from_dict(pdata),
        triggers=[],
        queue=ApprovalQueue(),
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CreatorForge</title>
<meta name="theme-color" content="#111111">
<meta name="description" content="CreatorForge local creator-assistant dashboard">
<link rel="manifest" href="/static/manifest.json">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icons/icon-192.png">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
</head><body>
<h1>CreatorForge Dashboard</h1>
<ul>
<li><a href="/catalog">Catalog</a></li>
<li><a href="/identity">Identity / consent status</a></li>
<li><a href="/chat/queue">Chat approval queue</a></li>
<li><a href="/pay">Payment links</a></li>
<li><a href="/schedule">Schedule (due reminders)</a></li>
<li><a href="/analytics">Analytics</a></li>
<li><a href="/skills">Skills</a></li>
<li><a href="/templates">Chat templates</a></li>
<li><a href="/docs">API docs</a></li>
</ul>
<script>
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js').catch(function(e) {
    console.log('SW registration failed:', e);
  });
}
</script>
</body></html>"""


@app.get("/catalog")
def catalog(kind: str | None = None, q: str | None = None,
            limit: int = 100,
            _: None = Depends(_require_token)) -> JSONResponse:
    store = _store()
    items = store.search(q, limit=limit) if q else store.list(kind=kind,
                                                              limit=limit)
    return JSONResponse({"count": store.count(), "items": items})


@app.get("/identity")
def identity_status(_: None = Depends(_require_token)) -> JSONResponse:
    cfg = _config()
    pack_path = cfg.get_path("identity.pack_path")
    if not pack_path:
        return JSONResponse({"status": "missing",
                             "detail": "No identity.pack_path configured."})
    try:
        pack = validate_identity_pack(load_identity_pack(pack_path))
    except InvalidConsentError as e:
        return JSONResponse({"status": "invalid", "detail": str(e)})
    c = pack["consent"]
    return JSONResponse({"status": "valid", "name": pack.get("name"),
                         "signer": c["signer"], "date": c["date"],
                         "scope": c["scope"]})


@app.get("/chat/queue")
def chat_queue(_: None = Depends(_require_token)) -> JSONResponse:
    def d2j(d: Draft) -> dict[str, Any]:
        return {"id": d.id, "platform": d.platform, "sender": d.sender,
                "incoming": d.incoming, "reply": d.reply,
                "trigger": d.trigger, "status": d.status,
                "escalated": d.escalated,
                "escalation_categories": d.escalation_categories}
    return JSONResponse({"pending": [d2j(d) for d in _engine().queue.pending()],
                         "all": [d2j(d) for d in _engine().queue.all()]})


@app.post("/chat/approve/{draft_id}")
def chat_approve(draft_id: int,
                 _: None = Depends(_require_token)) -> JSONResponse:
    try:
        d = _engine().queue.approve(draft_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"id": d.id, "status": d.status})


@app.post("/chat/reject/{draft_id}")
def chat_reject(draft_id: int,
                _: None = Depends(_require_token)) -> JSONResponse:
    try:
        d = _engine().queue.reject(draft_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"id": d.id, "status": d.status})


@app.post("/chat/sent/{draft_id}")
def chat_sent(draft_id: int,
              _: None = Depends(_require_token)) -> JSONResponse:
    """Record that an approved draft was sent (after YOU send it in the app).

    Refuses drafts that were never approved -- approval is the gate.
    """
    try:
        d = _engine().queue.mark_sent(draft_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"id": d.id, "status": d.status})


@app.get("/pay", response_class=HTMLResponse)
def pay_page() -> str:
    from forge.pay.links import tip_menu_html
    links = build_payment_links(_config())
    menu = _config().get_path("pay.tip_menu", [])
    return tip_menu_html(links, menu)


@app.get("/pay/links")
def pay_links_json(_: None = Depends(_require_token)) -> JSONResponse:
    """Payment links as JSON (used by the mobile thin client)."""
    return JSONResponse({"links": build_payment_links(_config())})


@app.get("/post/packets")
def post_packets(_: None = Depends(_require_token)) -> JSONResponse:
    """List manual-assist posting packets (used by the mobile thin client)."""
    import yaml
    packets_dir = Path(_config().get_path("post.packets_dir",
                                           "./forge-data/packets"))
    packets: list[dict[str, Any]] = []
    if packets_dir.is_dir():
        for child in sorted(packets_dir.iterdir()):
            meta_file = child / "packet.yaml"
            if not child.is_dir() or not meta_file.is_file():
                continue
            try:
                with meta_file.open(encoding="utf-8") as fh:
                    meta = yaml.safe_load(fh) or {}
            except Exception:
                meta = {}
            packets.append({
                "dir": child.name,
                "platform": meta.get("platform", "?"),
                "title": meta.get("title", ""),
                "scheduled_for": meta.get("scheduled_for", ""),
                "status": meta.get("status", "ready"),
                "created": meta.get("created", ""),
            })
    return JSONResponse({"packets": packets})


# -- schedule --------------------------------------------------------------
def _scheduler():
    from forge.post.schedule import Scheduler
    return Scheduler(_config().get_path("post.schedule_db",
                                        "./forge-data/schedule.db"))


@app.get("/schedule")
def schedule_list(status: str | None = None,
                  _: None = Depends(_require_token)) -> JSONResponse:
    """Scheduled posts (+ which are due). Reminders, not auto-posting."""
    sched = _scheduler()
    try:
        rows = sched.list(status=status)
        due_ids = {r["id"] for r in sched.due()}
    finally:
        sched.close()
    for r in rows:
        r["is_due"] = r["id"] in due_ids
    return JSONResponse({"scheduled": rows,
                         "due_count": len(due_ids),
                         "note": "Manual-assist only: post these yourself "
                                 "in each app when due."})


@app.post("/schedule/mark/{post_id}")
def schedule_mark(post_id: int, status: str = "done",
                  _: None = Depends(_require_token)) -> JSONResponse:
    sched = _scheduler()
    try:
        row = sched.mark(post_id, status)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    finally:
        sched.close()
    return JSONResponse({"id": row["id"], "status": row["status"]})


# -- analytics ---------------------------------------------------------------
def _analytics():
    from forge.analytics.store import AnalyticsStore
    return AnalyticsStore(_config().get_path("analytics.db_path",
                                             "./forge-data/analytics.db"))


@app.get("/analytics")
def analytics_json(_: None = Depends(_require_token)) -> JSONResponse:
    """Analytics totals + by-platform/month breakdown (mobile client)."""
    store = _analytics()
    try:
        data = {"totals": store.totals(),
                "by_platform_month": store.earnings_by_platform_month(),
                "recent_posts": store.post_stats(limit=10)}
    finally:
        store.close()
    return JSONResponse(data)


@app.get("/analytics/page", response_class=HTMLResponse)
def analytics_page(_: None = Depends(_require_token)) -> str:
    """Server-rendered analytics page with inline SVG bar charts."""
    from forge.analytics.report import build_report
    store = _analytics()
    try:
        rows = store.earnings_by_platform_month()
        report = build_report(store)
    finally:
        store.close()

    # group totals per platform for the bar chart
    per_platform: dict[str, float] = {}
    for r in rows:
        per_platform[r["platform"]] = per_platform.get(r["platform"], 0.0) \
            + float(r["total"] or 0)
    bars = ""
    if per_platform:
        top = max(per_platform.values()) or 1.0
        y = 10
        for plat, total in sorted(per_platform.items(),
                                  key=lambda kv: kv[1], reverse=True):
            w = max(4, int(420 * total / top))
            bars += (
                f'<text x="0" y="{y + 14}" font-size="13">{plat}</text>'
                f'<rect x="150" y="{y}" width="{w}" height="18" rx="4" '
                f'fill="#7c5cff"/>'
                f'<text x="{160 + w}" y="{y + 14}" font-size="13">'
                f'${total:,.2f}</text>\n')
            y += 30
        chart = (f'<svg width="640" height="{y + 10}" '
                 f'role="img" aria-label="earnings by platform">\n{bars}</svg>')
    else:
        chart = ("<p>No earnings logged yet. Use "
                 "<code>forge analytics log-earning</code> or the CLI.</p>")

    import html
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analytics - CreatorForge</title></head>
<body style="font-family:system-ui,sans-serif;max-width:720px;margin:2em auto">
<h1>Analytics</h1>
<h2>Earnings by platform</h2>
{chart}
<h2>Report</h2>
<pre style="background:#f4f4f4;padding:1em;white-space:pre-wrap">{html.escape(report)}</pre>
<p><a href="/">Back to dashboard</a></p>
</body></html>"""


# -- skills ------------------------------------------------------------------
@app.get("/skills")
def skills_list(_: None = Depends(_require_token)) -> JSONResponse:
    """Installed skills (mobile client + dashboard)."""
    from forge.skills import discover_skills
    skills = discover_skills(_config())
    return JSONResponse({"skills": [
        {"name": s.name, "version": s.version,
         "description": s.description, "usage": s.usage}
        for s in (skills[k] for k in sorted(skills))]})


@app.post("/skills/run/{name}")
async def skills_run_endpoint(name: str, request: Request,
                              _: None = Depends(_require_token)) -> JSONResponse:
    """Run a skill with JSON body {"args": [...]}. Returns result text."""
    from forge.skills import SkillError, run_skill
    try:
        body = await request.json()
    except Exception:
        body = {}
    args = body.get("args", []) if isinstance(body, dict) else []
    try:
        result = run_skill(name, [str(a) for a in args], _config())
    except SkillError as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"skill": name, "result": result})


# -- chat templates ------------------------------------------------------------
@app.get("/templates")
def templates_list(_: None = Depends(_require_token)) -> JSONResponse:
    """Canned chat templates (mobile client)."""
    from forge.chat.templates import ensure_defaults, load_templates
    ensure_defaults()
    templates = load_templates()
    return JSONResponse({"templates": [
        {"name": n, "category": t.get("category", "general"),
         "text": t["text"]}
        for n, t in sorted(templates.items())]})


@app.post("/templates/use/{name}")
async def templates_use_endpoint(name: str, request: Request,
                                 _: None = Depends(_require_token)) -> JSONResponse:
    """Draft a template into the approval queue. Body: {platform, sender}."""
    from forge.chat.templates import ensure_defaults, render_template
    ensure_defaults()
    try:
        body = await request.json()
    except Exception:
        body = {}
    platform = (body.get("platform") or "").strip()
    sender = (body.get("sender") or "").strip()
    if not platform or not sender:
        raise HTTPException(400, "Body needs {platform, sender}.")
    try:
        text = render_template(name, sender=sender,
                               persona_name=_engine().persona.name)
    except KeyError as e:
        raise HTTPException(400, str(e))
    draft = _engine().queue.add(platform=platform, sender=sender,
                                incoming=f"(template: {name})", reply=text,
                                trigger=f"template:{name}")
    return JSONResponse({"draft_id": draft.id, "reply": draft.reply})


    return JSONResponse({"draft_id": draft.id, "reply": draft.reply})


# -- spicy chat (consent-gated) + triage ---------------------------------------

def _spicy_engine_or_400():
    """Build the consent-gated spicy engine for dashboard use."""
    from forge.chat.spicy import SpicyEngine, SpicyConsentError
    from forge.identity.pack import resolve_pack_path
    pack_path = resolve_pack_path(None, _config())
    if not pack_path:
        raise HTTPException(400, "No identity pack configured.")
    try:
        return SpicyEngine.from_pack(
            pack_path, queue=_engine().queue, config=_config(),
            heat_path=_config().get_path("chat.spicy_heat_path",
                                         "./forge-data/chat-spicy-heat.json"))
    except SpicyConsentError as e:
        raise HTTPException(403, str(e))


@app.get("/chat/spicy/templates")
def spicy_templates(_: None = Depends(_require_token)) -> JSONResponse:
    """Spicy tier templates (consent-gated)."""
    from forge.chat.spicy import (TIERS, ensure_spicy_defaults,
                                  load_spicy_templates)
    _spicy_engine_or_400()  # consent gate
    ensure_spicy_defaults()
    tiers = load_spicy_templates()
    return JSONResponse({"tiers": [
        {"tier": t, "templates": [
            {"name": n, "text": txt}
            for n, txt in sorted(tiers.get(t, {}).items())]}
        for t in TIERS]})


@app.post("/chat/spicy/draft")
async def spicy_draft_endpoint(request: Request,
                               _: None = Depends(_require_token)
                               ) -> JSONResponse:
    """Draft a spicy reply (consent-gated, always pending approval)."""
    from forge.pay.links import build_payment_links
    spicy = _spicy_engine_or_400()
    try:
        body = await request.json()
    except Exception:
        body = {}
    platform = (body.get("platform") or "").strip()
    sender = (body.get("sender") or "").strip()
    text = (body.get("text") or "").strip()
    if not platform or not sender or not text:
        raise HTTPException(400, "Body needs {platform, sender, text}.")
    cfg = _config()
    draft = spicy.draft(platform=platform, sender=sender, text=text,
                        links=build_payment_links(cfg),
                        menu=cfg.get_path("pay.tip_menu", []) or [])
    return JSONResponse({"draft_id": draft.id, "reply": draft.reply,
                         "trigger": draft.trigger,
                         "tier": spicy.get_tier(platform, sender)})


@app.post("/chat/spicy/tier")
async def spicy_tier_endpoint(request: Request,
                              _: None = Depends(_require_token)
                              ) -> JSONResponse:
    """Set a conversation's spicy tier (her call only)."""
    spicy = _spicy_engine_or_400()
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        spicy.set_tier(body.get("platform", ""), body.get("sender", ""),
                       body.get("tier", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"ok": True})


def _triage_queue():
    from forge.chat.triage import TriageQueue, get_classifier
    cfg = _config()
    name = cfg.get_path("chat.triage.nsfw_classifier", "") or "none"
    return TriageQueue(
        cfg.get_path("chat.triage_db", "./forge-data/triage.db"),
        thumbs_dir=cfg.get_path("chat.triage_thumbs_dir",
                                "./forge-data/triage-thumbs"),
        classifier=get_classifier(name))


@app.get("/chat/triage")
def triage_list(_: None = Depends(_require_token)) -> JSONResponse:
    """Triage items (blurred thumbnails) awaiting her review."""
    q = _triage_queue()
    try:
        items = q.list(status="pending")
    finally:
        q.close()
    return JSONResponse({"pending": [
        {"id": it.id, "platform": it.platform, "sender": it.sender,
         "thumb": it.thumb_path, "nsfw_label": it.nsfw_label,
         "nsfw_score": it.nsfw_score, "note": it.note,
         "created": it.created}
        for it in items]})


@app.post("/chat/triage/{action}/{item_id}")
def triage_decide(action: str, item_id: int,
                  _: None = Depends(_require_token)) -> JSONResponse:
    """One-tap approve/skip for a triage item."""
    if action not in ("approve", "skip"):
        raise HTTPException(400, "action must be approve or skip.")
    q = _triage_queue()
    try:
        it = q.approve(item_id) if action == "approve" else q.skip(item_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    finally:
        q.close()
    return JSONResponse({"id": it.id, "status": it.status})


# -- custom video orders ---------------------------------------------------------

def _order_store():
    from forge.orders.store import OrderStore
    return OrderStore(_config().get_path("orders.db_path",
                                         "./forge-data/orders.db"))


@app.get("/orders")
def orders_list_endpoint(status: str | None = None,
                         _: None = Depends(_require_token)) -> JSONResponse:
    """Custom video orders."""
    store = _order_store()
    try:
        orders = store.list(status=status)
    finally:
        store.close()
    return JSONResponse({"orders": [o.as_dict() for o in orders]})


@app.post("/orders/{order_id}/{action}")
async def orders_action_endpoint(order_id: int, action: str,
                                 request: Request,
                                 _: None = Depends(_require_token)
                                 ) -> JSONResponse:
    """Order transitions: pay | render | review | approve | deliver |
    cancel | refund. Body (optional): {delivery_note}."""
    from forge.identity.pack import resolve_pack_path
    from forge.orders.flow import (cancel_order, deliver_order, mark_paid,
                                   refund_order, render_order, review_order,
                                   OrderRefusedError)
    from forge.video.queue import VideoQueue
    if action not in ("pay", "render", "review", "approve", "deliver",
                      "cancel", "refund"):
        raise HTTPException(400, "Unknown order action.")
    try:
        body = await request.json()
    except Exception:
        body = {}
    store = _order_store()
    cfg = _config()
    try:
        if action == "pay":
            order = mark_paid(store, order_id)
        elif action == "render":
            pack_path = resolve_pack_path(None, cfg)
            if not pack_path:
                raise HTTPException(400, "No identity pack configured.")
            queue = VideoQueue(cfg.get_path("video.queue_db",
                                            "./forge-data/video-queue.db"))
            try:
                order = render_order(store, queue, cfg, order_id, pack_path)
            finally:
                queue.close()
        elif action == "review":
            queue = VideoQueue(cfg.get_path("video.queue_db",
                                            "./forge-data/video-queue.db"))
            try:
                order = review_order(store, queue, order_id)
            finally:
                queue.close()
        elif action in ("approve", "deliver"):
            order = deliver_order(store, order_id,
                                  delivery_note=str(body.get("delivery_note",
                                                             "")))
        elif action == "cancel":
            order = cancel_order(store, order_id,
                                 reason=str(body.get("reason", "")))
        else:  # refund
            order = refund_order(store, order_id)
    except (OrderRefusedError, KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    finally:
        store.close()
    return JSONResponse({"order": order.as_dict()})


@app.get("/orders/scenes")
def orders_scenes_endpoint(_: None = Depends(_require_token)
                           ) -> JSONResponse:
    """Orderable scene templates with comfort decisions."""
    from forge.identity.pack import resolve_pack_path
    from forge.orders.flow import list_orderable_scenes
    pack_path = resolve_pack_path(None, _config())
    if not pack_path:
        raise HTTPException(400, "No identity pack configured.")
    return JSONResponse({"scenes": list_orderable_scenes(_config(),
                                                         pack_path)})


# -- live avatar -----------------------------------------------------------------

@app.get("/live")
def live_status_endpoint(_: None = Depends(_require_token)) -> JSONResponse:
    """Live avatar session status."""
    from forge.live.session import LiveSessionManager
    mgr = LiveSessionManager(_config().get_path("data_dir", "./forge-data"))
    return JSONResponse(mgr.status())


@app.post("/live/start")
async def live_start_endpoint(request: Request,
                              _: None = Depends(_require_token)
                              ) -> JSONResponse:
    """Start a live avatar session. Body: {provider, api_key?, ...}."""
    from forge.live.adapters import LiveNotConfiguredError
    from forge.live.session import LiveSessionManager, local_guide_text
    try:
        body = await request.json()
    except Exception:
        body = {}
    provider = str(body.get("provider", "")).strip()
    if provider == "local-guide":
        return JSONResponse({"provider": "local-guide",
                             "guide": local_guide_text()})
    mgr = LiveSessionManager(_config().get_path("data_dir", "./forge-data"))
    kwargs = {k: body[k] for k in ("avatar_id", "voice_id",
                                   "source_image_url") if body.get(k)}
    try:
        session = mgr.start(provider, _config(),
                            api_key=str(body.get("api_key", "")), **kwargs)
    except LiveNotConfiguredError as e:
        raise HTTPException(400, str(e))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"session": session})


@app.post("/live/stop")
def live_stop_endpoint(_: None = Depends(_require_token)) -> JSONResponse:
    """Stop the active live session."""
    from forge.live.session import LiveSessionManager
    mgr = LiveSessionManager(_config().get_path("data_dir", "./forge-data"))
    return JSONResponse(mgr.stop(_config()))


# -- fan CRM ---------------------------------------------------------------------

def _crm_store():
    from forge.crm.store import FanCRM
    return FanCRM(_config().get_path("crm.db_path", "./forge-data/crm.db"))


@app.get("/crm")
def crm_list_endpoint(platform: str | None = None,
                      status: str | None = None,
                      tag: str | None = None,
                      _: None = Depends(_require_token)) -> JSONResponse:
    """Fan list (optional filters)."""
    store = _crm_store()
    try:
        return JSONResponse({"fans": store.list_fans(
            platform=platform, status=status, tag=tag)})
    finally:
        store.close()


@app.get("/crm/fan")
def crm_fan_endpoint(platform: str, handle: str,
                     _: None = Depends(_require_token)) -> JSONResponse:
    """Fan profile + rules-based buyer-intent score."""
    store = _crm_store()
    try:
        fan = store.get_fan(platform, handle)
        if not fan:
            raise HTTPException(404, "No such fan.")
        return JSONResponse({**fan,
                             "buyer_intent": store.buyer_intent(platform,
                                                                handle)})
    finally:
        store.close()


@app.post("/crm/fan")
async def crm_fan_upsert_endpoint(request: Request,
                                 _: None = Depends(_require_token)
                                 ) -> JSONResponse:
    """Upsert a fan / record spend / add tag / add note.

    Body: {platform, handle, action: upsert|spend|tag|note|status,
           amount?, tag?, note?, status?}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    platform, handle = str(body.get("platform", "")), str(
        body.get("handle", ""))
    if not platform or not handle:
        raise HTTPException(400, "platform and handle are required.")
    store = _crm_store()
    try:
        action = str(body.get("action", "upsert"))
        if action == "spend":
            fan = store.record_spend(platform, handle,
                                     float(body.get("amount", 0)))
        elif action == "tag":
            fan = store.add_tag(platform, handle, str(body.get("tag", "")))
        elif action == "note":
            fan = store.add_note(platform, handle, str(body.get("note", "")))
        elif action == "status":
            fan = store.set_status(platform, handle,
                                   str(body.get("status", "")))
        else:
            fan = store.upsert_fan(platform=platform, handle=handle)
        return JSONResponse({"fan": fan})
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    finally:
        store.close()


@app.get("/crm/smart/{kind}")
def crm_smart_endpoint(kind: str, platform: str | None = None,
                       _: None = Depends(_require_token)) -> JSONResponse:
    """Smart fan segment: whales/new/active/expired/quiet/online."""
    store = _crm_store()
    try:
        try:
            fans = store.smart_list(kind, platform=platform)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return JSONResponse({"kind": kind, "fans": fans})
    finally:
        store.close()


@app.get("/crm/stats")
def crm_stats_endpoint(platform: str | None = None,
                       _: None = Depends(_require_token)) -> JSONResponse:
    """Per-fan reply/spend stats for her review."""
    store = _crm_store()
    try:
        return JSONResponse(
            {"stats": store.conversation_stats(platform=platform)})
    finally:
        store.close()


# -- spicy livestream ------------------------------------------------------------

@app.get("/stream/platforms")
def stream_platforms_endpoint(_: None = Depends(_require_token)
                              ) -> JSONResponse:
    """Honest per-platform streaming capability matrix."""
    from forge.stream.platforms import list_platforms
    return JSONResponse({"platforms": list_platforms()})


@app.get("/stream/status")
def stream_status_endpoint(_: None = Depends(_require_token)
                           ) -> JSONResponse:
    """AFK stream session status."""
    from forge.stream.session import StreamSessionManager
    mgr = StreamSessionManager(
        _config().get_path("data_dir", "./forge-data"))
    return JSONResponse(mgr.status())


@app.post("/stream/go-live")
async def stream_go_live_endpoint(request: Request,
                                  _: None = Depends(_require_token)
                                  ) -> JSONResponse:
    """Start an AFK stream session.

    Body: {platform, avatar (loop|sadtalker|heygen|did), avatar_source?,
           i_understand_the_risk: true}. Risk confirmation is REQUIRED.
    """
    from forge.stream.platforms import get_platform
    from forge.stream.session import (StreamNotConfiguredError,
                                      StreamSessionManager)
    try:
        body = await request.json()
    except Exception:
        body = {}
    platform = str(body.get("platform", ""))
    try:
        plat = get_platform(platform)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not body.get("i_understand_the_risk"):
        raise HTTPException(400,
                            "ToS risk not acknowledged: " + plat["tos_risk"])
    mgr = StreamSessionManager(
        _config().get_path("data_dir", "./forge-data"))
    try:
        session = mgr.go_live(
            platform=platform, config=_config(),
            avatar=str(body.get("avatar", "loop")),
            avatar_source=str(body.get("avatar_source", "")),
            acknowledged_risk=True)
    except (StreamNotConfiguredError, RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return JSONResponse({"session": session})


@app.post("/stream/stop")
def stream_stop_endpoint(_: None = Depends(_require_token)) -> JSONResponse:
    """Stop the active AFK stream session."""
    from forge.stream.session import StreamSessionManager
    mgr = StreamSessionManager(
        _config().get_path("data_dir", "./forge-data"))
    return JSONResponse(mgr.stop())


# -- chat: PPV / flows / humanizer / compliance -------------------------------------

@app.post("/chat/ppv")
async def chat_ppv_endpoint(request: Request,
                            _: None = Depends(_require_token)
                            ) -> JSONResponse:
    """Draft a PPV upsell offer into the approval queue.

    Body: {platform, sender, text}. No buying intent -> no draft.
    """
    from forge.chat.ppv import ppv_offer_text
    try:
        body = await request.json()
    except Exception:
        body = {}
    cfg = _config()
    price_menu = cfg.get_path("orders.price_menu") or \
        cfg.get_path("pay.tip_menu", []) or []
    offer = ppv_offer_text(fan_message=str(body.get("text", "")),
                           price_menu=price_menu,
                           pay_links=build_payment_links(cfg),
                           sender=str(body.get("sender", "")))
    if not offer:
        return JSONResponse({"drafted": False,
                             "note": "No buying intent detected."})
    draft = _engine().queue.add(platform=str(body.get("platform", "")),
                                sender=str(body.get("sender", "")),
                                incoming=str(body.get("text", "")),
                                reply=offer, trigger="ppv")
    return JSONResponse({"drafted": True, "draft_id": draft.id,
                         "reply": offer})


@app.get("/chat/flows/pending")
def chat_flows_pending_endpoint(_: None = Depends(_require_token)
                                ) -> JSONResponse:
    """Flow runs still active, with due times."""
    from forge.chat.flows import FlowRunner
    runner = FlowRunner(_config().get_path("chat.flows_db",
                                           "./forge-data/chat-flows.db"))
    try:
        return JSONResponse({"pending": runner.pending()})
    finally:
        runner.close()


@app.post("/chat/flows/enroll")
async def chat_flows_enroll_endpoint(request: Request,
                                     _: None = Depends(_require_token)
                                     ) -> JSONResponse:
    """Enroll a fan in welcome/winback/nudge. Body: {flow, platform, handle}."""
    from forge.chat.flows import FlowRunner
    try:
        body = await request.json()
    except Exception:
        body = {}
    runner = FlowRunner(_config().get_path("chat.flows_db",
                                           "./forge-data/chat-flows.db"))
    try:
        try:
            result = runner.enroll(str(body.get("flow", "")),
                                   str(body.get("platform", "")),
                                   str(body.get("handle", "")))
        except ValueError as e:
            raise HTTPException(400, str(e))
        return JSONResponse(result)
    finally:
        runner.close()


@app.post("/chat/flows/run")
def chat_flows_run_endpoint(_: None = Depends(_require_token)
                            ) -> JSONResponse:
    """Draft due flow steps into the approval queue (never auto-sends)."""
    from forge.chat.flows import FlowRunner, run_due
    runner = FlowRunner(_config().get_path("chat.flows_db",
                                           "./forge-data/chat-flows.db"))
    try:
        drafts = run_due(runner, _engine())
        return JSONResponse({"drafted": len(drafts),
                             "draft_ids": [d.id for d in drafts]})
    finally:
        runner.close()


@app.post("/chat/humanize")
async def chat_humanize_endpoint(request: Request,
                                 _: None = Depends(_require_token)
                                 ) -> JSONResponse:
    """Preview the humanizer on a draft. Body: {text}."""
    from forge.chat.humanize import humanize
    try:
        body = await request.json()
    except Exception:
        body = {}
    cfg = _config()
    hcfg = dict(cfg.get_path("chat.humanize", {}) or {})
    hcfg["enabled"] = True
    return JSONResponse({"original": str(body.get("text", "")),
                         "humanized": humanize(str(body.get("text", "")),
                                               hcfg)})


@app.post("/chat/check")
async def chat_check_endpoint(request: Request,
                              _: None = Depends(_require_token)
                              ) -> JSONResponse:
    """Compliance check a draft against her wordlists. Body: {text}."""
    from forge.chat.compliance import check_draft_text
    try:
        body = await request.json()
    except Exception:
        body = {}
    findings = check_draft_text(str(body.get("text", "")),
                                _config().get_path("chat.compliance",
                                                   {}) or {})
    return JSONResponse({"clean": not findings, "findings": findings})


# -- content ideas / analytics additions ----------------------------------------------

@app.get("/content/ideas")
def content_ideas_endpoint(count: int = 10, seed: str = "forge",
                           _: None = Depends(_require_token)
                           ) -> JSONResponse:
    """Template-remix post ideas from her catalog tags (not generative AI)."""
    from forge.content.ideas import (catalog_tags_for_ideas,
                                     generate_ideas)
    items = _store().list(limit=500)
    ideas = generate_ideas(
        catalog_tags=catalog_tags_for_ideas(items), count=count,
        seed_salt=seed)
    return JSONResponse({"ideas": ideas})


@app.get("/analytics/ltv")
def analytics_ltv_endpoint(_: None = Depends(_require_token)
                           ) -> JSONResponse:
    """LTV/ARPU from recorded earnings + CRM fan count."""
    from forge.analytics.insights import ltv_arpu, plain_english_summary
    from forge.analytics.store import AnalyticsStore
    cfg = _config()
    astore = AnalyticsStore(cfg.get_path("analytics.db_path",
                                         "./forge-data/analytics.db"))
    try:
        totals = astore.totals()
    finally:
        astore.close()
    crm = _crm_store()
    try:
        fans = crm.list_fans(limit=100000)
    finally:
        crm.close()
    ltv = ltv_arpu(total_earnings=totals["total_earnings"],
                   fan_count=len(fans),
                   fan_spends=[f["total_spend"] for f in fans])
    return JSONResponse({"ltv": ltv, "totals": totals,
                         "summary": plain_english_summary(
                             totals=totals, ltv=ltv, peaks=[])})


@app.get("/analytics/peak-times")
def analytics_peak_times_endpoint(_: None = Depends(_require_token)
                                  ) -> JSONResponse:
    """Best posting slots from her recorded post stats."""
    from forge.analytics.insights import peak_posting_times
    from forge.analytics.store import AnalyticsStore
    cfg = _config()
    astore = AnalyticsStore(cfg.get_path("analytics.db_path",
                                         "./forge-data/analytics.db"))
    try:
        stats = astore.post_stats(limit=1000)
    finally:
        astore.close()
    return JSONResponse({"peak_times": peak_posting_times(stats)})


def create_app(config_path: str | None = None) -> FastAPI:
    config = load_config(config_path)
    db_path = config.get_path("catalog.db_path", "./forge-data/catalog.db")
    init_state(config, db_path)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)),
              name="static")
    return app
