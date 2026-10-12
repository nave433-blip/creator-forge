# CreatorForge changelog

## v0.3.5 (draft — wave 2, not yet released)

### New features
- **Promo short-link click tracking**: `forge promo link-create` now
  prints a short link; `GET /promo/go/<code>` 302-redirects to the
  tagged URL and logs a raw click (user-agent + referrer). New
  `forge promo clicks --code` command, `/promo/clicks/<code>` API, and
  per-campaign click totals in `promo report`. Honest scope: counts
  only clicks routed through your own short links on a reachable
  dashboard — raw hits, not deduplicated uniques; earnings are still
  logged manually from payout reports.
- **Chat worker inbox rotation recovery**: `ManualInboxAdapter` no
  longer stalls forever when the inbox file is truncated or rotated —
  a stale offset past EOF resets cleanly; negative offsets are
  clamped.
- **Catalog pagination**: `GET /catalog` accepts `offset` and returns
  `total` alongside `count`, so large catalogs page properly.

### GUI
- **New browser dashboard UI** (`/ui/`): a real responsive home page
  (status cards for identity/consent, pending drafts, catalog,
  Telegram, promo), plus interactive Chat queue (approve/reject/mark
  sent from the browser), Catalog (search + pagination), Promo (links,
  click counts, per-campaign report), and Schedule (mark done) pages.
  Every page has loading, error, and empty states; mobile-responsive
  CSS; token prompt when `dashboard.api_token` is set. The JSON API
  is unchanged for the mobile app and scripts.
- **New desktop Promo screen** (PySide6): create links, see click
  counts and attributed earnings, short link copied to clipboard.
- **Mobile app**: Promo screen shows click counts; Catalog screen
  gains "Load more" pagination. `tsc` clean.

### Installer / packaging
- `anyio` is now a declared dependency (it was imported directly by
  the dashboard but only arrived transitively).
- The wheel now ships the dashboard PWA assets
  (`manifest.json`, `sw.js`, icons) — previously missing from
  `pip install`, which broke PWA install from an installed package.
- `docs/SETUP.md` documents the `/ui/` pages and the optional
  `ffmpeg`/`ffprobe` system tools (video durations/resizing degrade
  gracefully without them).
- Verified: clean `pip install` of the built wheel into a fresh venv,
  `forge init` scaffolds a project, and the installed dashboard
  serves the web UI.

### Tests
- 231/231 passing (8 new: promo click tracking ×5, worker offset
  edge cases ×2, web UI pages ×1). Privacy grep clean (no real names).

## v0.3.4

- Declared `httpx` as a runtime dependency (the Telegram adapter
  imports it directly — same transitive-dependency bug class fixed
  again in v0.3.5 with `anyio`).
- Refinement round: Telegram bot retry with exponential backoff
  (honoring `retry_after`), chat-engine fail-fast trigger regex +
  `safe_format`, atomic approval-queue persistence, dashboard
  worker-thread Telegram sends with correct 400/502 status codes,
  vault hardening (empty passwords rejected, atomic put), PPV
  word-boundary intent matching + exact price-match picking, clean
  one-line CLI `VaultError` handling.
- 223/223 tests passing. Privacy grep clean.
