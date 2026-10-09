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
                "trigger": d.trigger, "status": d.status}
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


def create_app(config_path: str | None = None) -> FastAPI:
    config = load_config(config_path)
    db_path = config.get_path("catalog.db_path", "./forge-data/catalog.db")
    init_state(config, db_path)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)),
              name="static")
    return app
