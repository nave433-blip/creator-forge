"""Custom video orders: fan-facing order flow for paid AI videos.

Flow:
  fan picks a scene template from HER price menu + pays via her payment
  links -> order enters the generation queue -> she reviews/approves the
  finished video before delivery.

States: pending_payment -> queued -> rendering -> awaiting_review ->
delivered, plus cancelled / refunded.

Comfort boundaries are enforced at order time: AI-only scenes can be
ordered; refused categories are rejected outright with a clear reason.
"""

from __future__ import annotations
