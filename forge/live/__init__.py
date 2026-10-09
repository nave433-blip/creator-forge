"""Live AI avatar sessions for video calls and streams.

REAL adapters only: HeyGen streaming API and D-ID API (both paid, both
need her own API keys). Without a key they raise LiveNotConfiguredError
-- they never fake a live avatar.

For the no-budget path, `forge live start --provider local-guide`
prints the honest local setup (talking-head model + OBS virtual camera)
instead of pretending to start anything. See docs/LIVE.md.
"""

from __future__ import annotations
