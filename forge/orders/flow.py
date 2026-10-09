"""Order state machine for custom video orders.

Allowed transitions:
  pending_payment -> queued        (pay: payment confirmed)
  pending_payment -> cancelled     (cancel)
  queued          -> rendering     (render: video job enqueued)
  queued          -> cancelled     (cancel)
  rendering       -> awaiting_review (review: video job finished)
  rendering       -> cancelled     (cancel)
  awaiting_review -> delivered     (approve / deliver: she reviewed it)
  awaiting_review -> cancelled     (cancel)
  cancelled       -> refunded      (refund)

Comfort boundaries: an order can only be created for a scene that
resolves to "ai" or "real" against her identity pack. "refused" scenes
raise OrderRefusedError -- the fan never gets to order those.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.orders.store import Order, OrderStore
from forge.video.scenes import (
    SceneRefusedError,
    load_scene,
    resolve_scene,
)


class OrderRefusedError(Exception):
    """Raised when an order hits a comfort boundary or bad state."""


_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending_payment": ("queued", "cancelled"),
    "queued": ("rendering", "cancelled"),
    "rendering": ("awaiting_review", "cancelled"),
    "awaiting_review": ("delivered", "cancelled"),
    "delivered": (),
    "cancelled": ("refunded",),
    "refunded": (),
}


def price_menu(config: Any) -> list[dict[str, str]]:
    """Her orderable price menu: orders.price_menu, falling back to
    pay.tip_menu."""
    try:
        menu = config.get_path("orders.price_menu", None)
        if menu:
            return [{"label": str(m.get("label", "")),
                     "price": str(m.get("price", ""))}
                    for m in menu if isinstance(m, dict)]
        tip = config.get_path("pay.tip_menu", []) or []
        return [{"label": str(m.get("label", "")),
                 "price": str(m.get("price", ""))}
                for m in tip if isinstance(m, dict)]
    except Exception:
        return []


def scenes_dir(config: Any) -> Path:
    try:
        d = config.get_path("orders.scenes_dir", "./scenes")
    except Exception:
        d = "./scenes"
    return Path(d)


def list_orderable_scenes(config: Any, pack_path: str | Path,
                          catalog_items: list[dict] | None = None
                          ) -> list[dict[str, Any]]:
    """Scenes in the scenes dir annotated with their comfort decision.

    Only "ai" and "real" scenes are orderable; "refused" ones are listed
    with their reason so she knows what to fix.
    """
    from forge.identity.pack import load_identity_pack, validate_identity_pack

    pack = validate_identity_pack(load_identity_pack(pack_path))
    out: list[dict[str, Any]] = []
    d = scenes_dir(config)
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
        try:
            scene = load_scene(f)
            decision = resolve_scene(scene, pack, catalog_items)
            out.append({"name": scene.name, "path": str(f),
                        "mode": decision.mode, "reason": decision.reason,
                        "orderable": decision.mode in ("ai", "real")})
        except Exception as e:
            out.append({"name": f.stem, "path": str(f), "mode": "error",
                        "reason": str(e), "orderable": False})
    return out


def create_order(store: OrderStore, *, fan_handle: str, scene_path: str | Path,
                 pack_path: str | Path, platform: str = "",
                 price_label: str = "", price: str = "",
                 catalog_items: list[dict] | None = None) -> Order:
    """Create an order in pending_payment.

    Raises OrderRefusedError if the scene hits a comfort boundary.
    """
    from forge.identity.pack import load_identity_pack, validate_identity_pack

    pack = validate_identity_pack(load_identity_pack(pack_path))
    scene = load_scene(scene_path)
    try:
        decision = resolve_scene(scene, pack, catalog_items)
    except SceneRefusedError as e:
        raise OrderRefusedError(str(e))
    if decision.mode == "refused":
        raise OrderRefusedError(
            f"Scene {scene.name!r} is not orderable: {decision.reason}")
    note = ("AI-generated custom" if decision.mode == "ai"
            else "She films this one herself")
    order = store.create(fan_handle=fan_handle, platform=platform,
                         scene_name=scene.name, scene_path=str(scene_path),
                         price_label=price_label, price=price)
    return store.update(order.id, delivery_note=note)


def transition(store: OrderStore, order_id: int, to_status: str,
               **fields: Any) -> Order:
    """Move an order to a new status if the transition is allowed."""
    order = store.get(order_id)
    allowed = _TRANSITIONS.get(order.status, ())
    if to_status not in allowed:
        raise OrderRefusedError(
            f"Order #{order_id} is {order.status!r}: cannot move to "
            f"{to_status!r}. Allowed: {list(allowed) or 'none'}.")
    return store.update(order_id, status=to_status, **fields)


def mark_paid(store: OrderStore, order_id: int) -> Order:
    return transition(store, order_id, "queued")


def render_order(store: OrderStore, queue: Any, config: Any,
                 order_id: int, pack_path: str | Path) -> Order:
    """Enqueue the order's video job. queued -> rendering."""
    from forge.video.scenes import load_scene as _load

    order = store.get(order_id)
    if order.status != "queued":
        raise OrderRefusedError(
            f"Order #{order_id} must be 'queued' to render "
            f"(is {order.status!r}).")
    scene = _load(order.scene_path)
    job = queue.add(prompt=scene.prompt(), pack_path=str(pack_path),
                    negative_prompt="", adapter="", duration_s=8)
    return transition(store, order_id, "rendering", video_job_id=job["id"])


def review_order(store: OrderStore, queue: Any, order_id: int) -> Order:
    """Check the video job; when done, move to awaiting_review so SHE
    looks at the finished video before it goes to the fan."""
    order = store.get(order_id)
    if order.status != "rendering":
        raise OrderRefusedError(
            f"Order #{order_id} must be 'rendering' to review "
            f"(is {order.status!r}).")
    if order.video_job_id is None:
        raise OrderRefusedError(f"Order #{order_id} has no video job.")
    job = queue.get(order.video_job_id)
    if job["status"] == "failed":
        raise OrderRefusedError(
            f"Video job #{job['id']} failed: {job.get('error')}. "
            "Fix the backend/consent issue, re-render, or cancel/refund.")
    if job["status"] != "done":
        raise OrderRefusedError(
            f"Video job #{job['id']} is {job['status']!r}, not done yet.")
    outputs = job.get("outputs") or []
    return transition(store, order_id, "awaiting_review",
                      output_path=outputs[0] if outputs else "")


def deliver_order(store: OrderStore, order_id: int,
                  delivery_note: str = "") -> Order:
    """She reviewed the finished video and it's going to the fan."""
    order = store.get(order_id)
    if order.status != "awaiting_review":
        raise OrderRefusedError(
            f"Order #{order_id} must be 'awaiting_review' to deliver "
            f"(is {order.status!r}). Review it first.")
    fields: dict[str, Any] = {}
    if delivery_note:
        fields["delivery_note"] = delivery_note
    return transition(store, order_id, "delivered", **fields)


def cancel_order(store: OrderStore, order_id: int,
                 reason: str = "") -> Order:
    order = store.get(order_id)
    fields: dict[str, Any] = {}
    if reason:
        fields["delivery_note"] = f"Cancelled: {reason}"
    return transition(store, order_id, "cancelled", **fields)


def refund_order(store: OrderStore, order_id: int) -> Order:
    return transition(store, order_id, "refunded")
