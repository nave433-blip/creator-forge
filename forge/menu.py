"""Interactive menu mode: `forge menu`.

A friendly numbered menu over every CreatorForge command -- no need to
remember flags. Each menu item asks for what it needs in plain English
(with sensible defaults shown in [brackets]) and then runs the same
code as the equivalent CLI command.
"""

from __future__ import annotations

from typing import Any, Callable


def _cmds():
    """Lazy import to avoid a circular import with forge.cli."""
    import forge.cli as C
    return C


# Each entry: (label, function-name in forge.cli, [(param, prompt, default)])
# A default of None means "required". "..." suffix on param name means
# comma-separated list.
SECTIONS: list[tuple[str, list[tuple[str, str, list[tuple[str, str, Any]]]]]] = [
    ("Catalog -- your content library", [
        ("Scan a folder into the catalog", "catalog_scan",
         [("root", "Folder of media to scan", None),
          ("tags", "Tags for new items (comma-separated, optional)", "")]),
        ("List catalog items", "catalog_list",
         [("kind", "Filter by kind: image/video (blank = all)", None),
          ("query", "Search text (blank = all)", None)]),
    ]),
    ("Identity -- consent packs & personas", [
        ("Create an identity pack (consent)", "identity_create",
         [("name", "Persona name", None),
          ("signer", "Full legal name signing consent", None),
          ("scope", "What the consent covers", None),
          ("statement_file", "Path to signed consent statement file", None),
          ("out", "Where to write the pack", "identity-pack.yaml")]),
        ("Validate an identity pack", "identity_validate",
         [("pack", "Pack path (blank = configured/active)", None)]),
        ("List persona packs", "identity_list_cmd", []),
        ("Switch active persona", "identity_use_cmd",
         [("pack", "Pack path to make active", None)]),
        ("Make a new version of a pack", "identity_new_version_cmd",
         [("pack", "Pack path", None),
          ("notes", "What changed in this version", "")]),
    ]),
    ("Video -- generate AI video", [
        ("Generate a video (consent-gated)", "video_generate",
         [("prompt", "Describe the video", None),
          ("pack", "Identity pack (blank = active/configured)", None),
          ("adapter", "Adapter: replicate/comfyui (blank = config)", None),
          ("duration", "Duration in seconds", 5)]),
        ("Run a scene (comfort boundary)", "video_scene",
         [("scene", "Scene YAML file", None),
          ("pack", "Identity pack (blank = active/configured)", None)]),
        ("Queue a generation for later", "video_queue_add",
         [("prompt", "Describe the video", None),
          ("pack", "Identity pack (blank = active/configured)", None),
          ("adapter", "Adapter (blank = config)", ""),
          ("duration", "Duration in seconds", 5)]),
        ("Run the video queue", "video_queue_run", []),
        ("Show video queue", "video_queue_list",
         [("status", "Filter: queued/running/done/failed (blank = all)", None)]),
        ("Prepare a training dataset manifest", "video_prep_dataset",
         [("out_csv", "Output CSV path", "dataset/manifest.csv"),
          ("trigger", "Trigger word for training", "creatorpersona")]),
    ]),
    ("Persona -- trainers & voice", [
        ("List persona trainer options", "persona_trainers",
         [("kind", "Filter: local-gpu/paid-api (blank = all)", None)]),
        ("Clone voice (ElevenLabs, consent-gated)", "persona_voice_clone",
         [("name", "Voice name", None),
          ("audio", "Sample audio files (comma-separated paths)", None),
          ("pack", "Identity pack (blank = configured)", None)]),
        ("Speak with cloned voice", "persona_voice_speak",
         [("text", "Text to speak", None),
          ("out", "Output audio path", "voiceover.mp3"),
          ("pack", "Identity pack (blank = configured)", None)]),
    ]),
    ("Chat -- approval-gated bot", [
        ("Draft a reply", "chat_draft",
         [("platform", "Platform (e.g. onlyfans, reddit)", None),
          ("sender", "Who sent the message", None),
          ("text", "The incoming message", None)]),
        ("Show approval queue", "chat_queue_cmd", []),
        ("Approve a draft", "chat_approve_cmd",
         [("draft_id", "Draft number", None)]),
        ("Reject a draft", "chat_reject_cmd",
         [("draft_id", "Draft number", None)]),
        ("Log a draft as sent", "chat_sent_cmd",
         [("draft_id", "Draft number", None)]),
        ("Set conversation mode", "chat_mode_cmd",
         [("platform", "Platform", None),
          ("sender", "Sender", None),
          ("mode", "auto / approve-first / manual", "approve-first")]),
        ("Run the chat worker once", "chat_worker_once",
         [("inbox", "Inbox JSONL file", "inbox.jsonl")]),
        ("Add a canned template", "chat_template_add",
         [("name", "Template name", None),
          ("text", "Template text ({sender} = their name)", None),
          ("category", "Category", "general")]),
        ("List canned templates", "chat_template_list", []),
        ("Add a word to her word bank", "chat_lexicon_add",
         [("category", "slang / phrases / pet_names / emoji / openers / closers / spicy", "slang"),
          ("term", "Word or phrase", None),
          ("note", "Note (optional)", "")]),
        ("List her word bank", "chat_lexicon_list",
         [("category", "Category (blank = all)", ""),
          ("search", "Search (blank = all)", "")]),
        ("Remove a word from her word bank", "chat_lexicon_remove",
         [("category", "Category", "slang"),
          ("term", "Word or phrase", None)]),
        ("Adopt learned words into her word bank", "chat_lexicon_adopt",
         [("profile", "Style profile path", "style-profile.json"),
          ("n", "How many words", "10"),
          ("category", "Category", "slang")]),
        ("Use a template (draft into queue)", "chat_template_use",
         [("name", "Template name", None),
          ("platform", "Platform", None),
          ("sender", "Sender", None)]),
        ("Build her text-style profile", "chat_style_build",
         [("transcript", "Transcript JSON file", None),
          ("pack", "Identity pack (consent gate)", None),
          ("out", "Output profile path", "style-profile.json")]),
        ("Read the style report", "chat_style_report",
         [("profile", "Profile JSON path", "style-profile.json")]),
        ("Spicy: list templates", "chat_spicy_templates",
         [("action", "list / add / delete", "list"),
          ("tier", "playful / teasing / explicit", "playful"),
          ("pack", "Identity pack (consent gate)", None)]),
        ("Spicy: draft a flirty reply", "chat_spicy_draft",
         [("platform", "Platform", None),
          ("sender", "Sender", None),
          ("text", "Their message", None),
          ("pack", "Identity pack (consent gate)", None)]),
        ("Spicy: set conversation tier", "chat_spicy_tier",
         [("platform", "Platform", None),
          ("sender", "Sender", None),
          ("tier", "playful / teasing / explicit", "teasing"),
          ("pack", "Identity pack (consent gate)", None)]),
        ("Triage: queue a fan-sent pic", "chat_triage_add",
         [("platform", "Platform", None),
          ("sender", "Sender", None),
          ("media", "Image file path", None)]),
        ("Triage: list pending", "chat_triage_list", []),
        ("Triage: approve", "chat_triage_approve",
         [("item_id", "Triage item number", None)]),
        ("Triage: skip", "chat_triage_skip",
         [("item_id", "Triage item number", None)]),
        ("PPV: draft upsell offer (buying intent)", "chat_ppv",
         [("platform", "Platform", None),
          ("sender", "Sender", None),
          ("text", "The fan's message", None)]),
        ("Flows: enroll/run/pending/cancel/list", "chat_flows",
         [("action", "enroll / run / pending / cancel / list", "pending"),
          ("flow", "welcome / winback / nudge (for enroll/cancel)", ""),
          ("platform", "Platform (for enroll/cancel)", ""),
          ("handle", "Fan handle (for enroll/cancel)", "")]),
        ("Preview humanizer on a draft", "chat_humanize",
         [("text", "Draft text", None),
          ("typo", "Typo intensity 0.0-1.0", 0.15),
          ("lowercase", "Lowercase everything? yes/no", "no")]),
        ("Compliance check a draft", "chat_check",
         [("text", "Draft text", None)]),
        ("Translate a draft", "chat_translate",
         [("text", "Draft text", None),
          ("target", "Language code (e.g. es)", None)]),
    ]),
    ("Custom orders -- fan-paid videos", [
        ("What can fans order? (comfort-checked scenes)", "orders_scenes",
         [("pack", "Identity pack", None)]),
        ("Create an order", "orders_create",
         [("fan", "Fan handle", None),
          ("scene", "Scene YAML path", None),
          ("pack", "Identity pack", None),
          ("price_label", "Price label (optional)", ""),
          ("price", "Price (optional)", "")]),
        ("List orders", "orders_list",
         [("status", "Filter by status (blank = all)", None)]),
        ("Mark paid", "orders_pay",
         [("order_id", "Order number", None)]),
        ("Render (enqueue video job)", "orders_render",
         [("order_id", "Order number", None)]),
        ("Move to review (job done)", "orders_review",
         [("order_id", "Order number", None)]),
        ("Approve finished video", "orders_approve",
         [("order_id", "Order number", None)]),
        ("Deliver to fan", "orders_deliver",
         [("order_id", "Order number", None),
          ("note", "Where/how sent", "")]),
        ("Cancel order", "orders_cancel",
         [("order_id", "Order number", None)]),
    ]),
    ("Live avatar -- video calls & streams", [
        ("Start live session", "live_start",
         [("provider", "heygen / did / local-guide", "local-guide")]),
        ("Session status", "live_status", []),
        ("Stop live session", "live_stop", []),
    ]),
    ("Post & Schedule -- get content out", [
        ("Post to Reddit (dry-run by default)", "post_reddit",
         [("subreddit", "Subreddit (no r/)", None),
          ("title", "Post title", None),
          ("body", "Text body (blank for media)", ""),
          ("media", "Media file path (blank for text)", ""),
          ("kind", "text / image / video", "text"),
          ("live", "Actually post? yes/no", "no")]),
        ("Build a manual posting packet", "post_packet",
         [("platform", "Platform (snapchat, onlyfans, tiktok...)", None),
          ("media", "Media file path", None),
          ("caption", "Caption", None),
          ("hashtags", "Hashtags (space-separated)", "")]),
        ("Schedule a packet", "post_schedule_cmd",
         [("platform", "Platform", None),
          ("media", "Media file path", None),
          ("caption", "Caption", None),
          ("when", "When (e.g. 2026-10-10T19:00)", None),
          ("title", "Title (optional)", "")]),
        ("What's due to post", "post_due_cmd", []),
        ("Show scheduled posts", "post_scheduled_cmd",
         [("status", "scheduled/done/skipped (blank = all)", None)]),
        ("Mark a scheduled post done", "post_mark_done_cmd",
         [("post_id", "Schedule entry number", None)]),
        ("Build a mass-DM packet", "post_massdm",
         [("message", "Message ({handle}/{first}/{spend})", None),
          ("platform", "Target platform", None),
          ("fan_list", "whales/new/active/expired/quiet/online",
           "whales"),
          ("exclude_recent", "Skip fans chatted in 48h? yes/no", "yes"),
          ("live", "Write packet? (default: dry-run) yes/no", "no"),
          ("schedule", "Reminder time (blank = none)", "")]),
        ("Tube sites: list + honest capabilities", "tube_sites", []),
        ("Tube: preview title/description/tags", "tube_metadata",
         [("site", "pornhub/xvideos/xnxx/xhamster/redtube/youporn", "pornhub"),
          ("scene", "Scene YAML (blank = none)", ""),
          ("name", "Her display name", ""),
          ("tags", "Custom tags, comma-separated", "")]),
        ("Tube: build upload packet for a video", "tube_packet",
         [("video", "Video file path", None),
          ("site", "pornhub/xvideos/xnxx/xhamster/redtube/youporn", "pornhub"),
          ("scene", "Scene YAML (blank = none)", ""),
          ("name", "Her display name", ""),
          ("tags", "Custom tags, comma-separated", "")]),
        ("Tube: bulk packets (folder x sites)", "tube_bulk",
         [("dir", "Folder of videos", None),
          ("sites", "Comma-separated site keys",
           "pornhub,xvideos,xnxx,xhamster,redtube,youporn"),
          ("scene", "Scene YAML (blank = none)", ""),
          ("name", "Her display name", ""),
          ("tags", "Custom tags, comma-separated", "")]),
    ]),
    ("Pay -- payment links", [
        ("Show payment links", "pay_links", []),
        ("Generate tip-menu page", "pay_tip_menu",
         [("out", "Output HTML path", "tip-menu.html")]),
    ]),
    ("Vault -- encrypted storage", [
        ("Create a vault", "vault_init",
         [("path", "Vault folder", "./forge-data/vault")]),
        ("Unlock the vault", "vault_unlock",
         [("path", "Vault folder", "./forge-data/vault")]),
        ("Lock the vault", "vault_lock",
         [("path", "Vault folder", "./forge-data/vault")]),
        ("Put a file in the vault", "vault_import",
         [("path", "Vault folder", "./forge-data/vault"),
          ("file", "File to encrypt in", None)]),
        ("Take a file out of the vault", "vault_export",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name in the vault", None)]),
        ("List vault contents", "vault_list",
         [("path", "Vault folder", "./forge-data/vault")]),
        ("Back up everything (encrypted)", "vault_backup",
         [("path", "Vault folder", "./forge-data/vault"),
          ("out", "Backup file", "forge-backup.enc")]),
        ("Restore from a backup", "vault_restore",
         [("backup", "Backup file", None),
          ("dest", "Restore into folder", "./forge-restore")]),
        ("Label a vault blob", "vault_label_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name", None),
          ("labels", "Comma-separated labels", None)]),
        ("Show blob labels", "vault_labels_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name", None)]),
        ("Find blobs by label", "vault_find_label_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("label", "Label", None)]),
        ("Search vault (names + labels)", "vault_search_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("query", "Search text", None)]),
        ("Log a blob sent to a fan", "vault_sent_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name", None),
          ("fan", "Fan handle", None)]),
        ("Who got a blob?", "vault_sent_log_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name", None)]),
        ("Check before resending", "vault_check_sent_cmd",
         [("path", "Vault folder", "./forge-data/vault"),
          ("name", "Blob name", None),
          ("fan", "Fan handle", None)]),
    ]),
    ("Connect -- platform import/export", [
        ("Show platform capability matrix", "connect_list", []),
        ("Import content via a connector", "connect_import",
         [("platform", "fansly / onlyfans / reddit / filesystem / url", None),
          ("source", "Folder, file, or URL", None)]),
    ]),
    ("Analytics -- stats & earnings", [
        ("Log stats for a post", "analytics_log_post",
         [("platform", "Platform", None),
          ("post_ref", "Post id or URL", None),
          ("title", "Post title", ""),
          ("views", "Views", 0),
          ("likes", "Likes", 0),
          ("comments", "Comments", 0)]),
        ("Log earnings", "analytics_log_earning",
         [("platform", "Platform", None),
          ("amount", "Amount", None),
          ("kind", "Kind (subs, tips, ppv...)", ""),
          ("month", "Month YYYY-MM (blank = this month)", "")]),
        ("Import earnings CSV", "analytics_import_earnings",
         [("csv_path", "CSV file path", None)]),
        ("Show analytics report", "analytics_report", []),
        ("Fetch live Reddit stats", "analytics_reddit_stats",
         [("submission_id", "Reddit submission id", None)]),
        ("LTV / ARPU report", "analytics_ltv", []),
        ("Best posting times", "analytics_peak_times", []),
    ]),
    ("Skills -- extra capabilities", [
        ("List installed skills", "skills_list", []),
        ("Run a skill", "skills_run",
         [("name", "Skill name", None),
          ("args", "Extra args, space-separated (blank = none)", "")]),
    ]),
    ("Fan CRM -- subscribers & spend", [
        ("Add / fetch a fan", "crm_add",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None)]),
        ("Show fan profile + buyer-intent score", "crm_show",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None)]),
        ("List fans", "crm_list",
         [("platform", "Platform (blank = all)", None),
          ("status", "Status filter (blank = all)", None),
          ("tag", "Tag filter (blank = all)", None)]),
        ("Tag a fan", "crm_tag",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None),
          ("tag", "Tag (e.g. whale, online, vip)", None)]),
        ("Untag a fan", "crm_untag",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None),
          ("tag", "Tag to remove", None)]),
        ("Add a note about a fan", "crm_note",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None),
          ("note", "Note", None)]),
        ("Record a fan purchase (updates LTV)", "crm_spend",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None),
          ("amount", "Amount", None)]),
        ("Log a fan message", "crm_message",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None)]),
        ("Set fan status", "crm_set_status",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None),
          ("status", "new / active / expired / vip", "active")]),
        ("Buyer-intent score", "crm_score",
         [("platform", "Platform", None),
          ("handle", "Fan handle", None)]),
        ("Smart list (segment)", "crm_smart_list",
         [("kind", "whales / new / active / expired / quiet / online",
           "whales"),
          ("platform", "Platform (blank = all)", None)]),
        ("Import fans from CSV", "crm_import_csv",
         [("csv_path", "CSV file path", None)]),
        ("Per-fan stats (her review)", "crm_stats",
         [("platform", "Platform (blank = all)", None)]),
    ]),
    ("Spicy livestream -- AFK avatar", [
        ("Platform capability matrix", "stream_platforms", []),
        ("Setup steps for a platform", "stream_setup",
         [("platform", "Platform key", None)]),
        ("Go live (AFK avatar -> OBS -> RTMP)", "stream_go_live",
         [("platform", "Platform key", None),
          ("avatar", "loop / sadtalker / heygen / did", "loop"),
          ("avatar_source", "Video file (loop mode)", None),
          ("i_understand_the_risk", "Type yes to confirm ToS risk",
           "no")]),
        ("Stream status", "stream_status", []),
        ("Stop stream", "stream_stop", []),
    ]),
    ("Content ideas", [
        ("Generate post ideas (template remix)", "content_ideas",
         [("count", "How many ideas", 10),
          ("seed", "Change for a fresh batch", "forge")]),
    ]),
    ("Profile & Settings", [
        ("Export full profile (encrypted)", "export_profile_cmd",
         [("out", "Output file", "forge-profile.enc")]),
        ("Import a profile", "import_profile_cmd",
         [("bundle", "Profile file", None),
          ("dest", "Unpack into folder", ".")]),
        ("Start the dashboard", "dashboard",
         [("port", "Port", 8765)]),
        ("Set up a new project folder", "init",
         [("path", "Folder", ".")]),
    ]),
]


def _ask(prompt: str, default: Any) -> Any:
    """Prompt for one value; blank keeps the default (None = required)."""
    if default is None:
        while True:
            val = input(f"{prompt}: ").strip()
            if val:
                return val
            print("  (this one is required)")
    else:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default


_INT_PARAMS = {"draft_id", "post_id", "port", "duration", "views",
               "likes", "comments", "n"}
_FLOAT_PARAMS = {"amount", "opacity", "typo"}


def _coerce(name: str, value: Any) -> Any:
    if name.endswith("..."):
        return [v.strip() for v in str(value).split(",") if v.strip()]
    if isinstance(value, bool):
        return value
    base = name[:-3] if name.endswith("...") else name
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if base in _INT_PARAMS:
        try:
            return int(text)
        except ValueError:
            return value
    if base in _FLOAT_PARAMS:
        try:
            return float(text)
        except ValueError:
            return value
    low = text.lower()
    if base in ("live", "i_understand_the_risk", "exclude_recent",
                "lowercase"):
        if low in ("yes", "y", "true", "1"):
            return True
        if low in ("no", "n", "false", "0"):
            return False
    return value


def run_menu() -> None:
    """Run the interactive menu. Ctrl+C exits cleanly."""
    C = _cmds()
    print("\n=== CreatorForge ===")
    print("Pick a section, then pick an action. Ctrl+C quits anytime.\n")
    try:
        while True:
            for i, (title, _) in enumerate(SECTIONS, 1):
                print(f"  {i}. {title}")
            print("  0. Quit")
            choice = input("\nSection [0]: ").strip() or "0"
            if not choice.isdigit() or not (0 <= int(choice) <= len(SECTIONS)):
                print("Not a valid number -- try again.\n")
                continue
            if choice == "0":
                print("Bye!")
                return
            title, items = SECTIONS[int(choice) - 1]
            print(f"\n-- {title} --")
            for i, (label, _, _) in enumerate(items, 1):
                print(f"  {i}. {label}")
            print("  0. Back")
            sub = input("\nAction [0]: ").strip() or "0"
            if not sub.isdigit() or not (0 <= int(sub) <= len(items)):
                print("Not a valid number -- try again.\n")
                continue
            if sub == "0":
                print()
                continue
            label, func_name, params = items[int(sub) - 1]
            func: Callable = getattr(C, func_name)
            kwargs: dict[str, Any] = {}
            print(f"\n{label}")
            for pname, prompt, default in params:
                raw = _ask(prompt, default)
                key = pname[:-3] if pname.endswith("...") else pname
                kwargs[key] = _coerce(pname, raw)
            # typer commands take config=None by default; pass it through
            try:
                print()
                func(**kwargs)
            except SystemExit:
                pass  # typer.Exit -- just return to the menu
            except Exception as e:  # noqa: BLE001 - friendly menu
                print(f"\nSomething went wrong: {e}")
            print("\n" + "-" * 40 + "\n")
    except (KeyboardInterrupt, EOFError):
        print("\nBye!")


if __name__ == "__main__":
    run_menu()
