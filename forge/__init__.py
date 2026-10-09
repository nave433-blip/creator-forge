"""CreatorForge: an AI creator-assistant toolkit.

Catalog -> identity (consent-gated) -> video generation -> posting helpers
-> approval-gated chat -> payment links, with a small local dashboard.

Nothing here sends, posts, or generates anything without explicit
configuration and, for anything touching the creator's likeness, a
validated consent record. See docs/CONSENT.md.
"""

from forge.config import ForgeConfig

__all__ = ["ForgeConfig"]
__version__ = "0.1.0"
