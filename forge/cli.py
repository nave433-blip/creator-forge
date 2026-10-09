"""CreatorForge command line: `forge <command>`.

Run `forge --help` for the full list. Every command reads forge.yaml
unless --config is given.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from forge.catalog.scanner import scan_directory
from forge.catalog.store import CatalogStore
from forge.chat.engine import Persona, RuleEngine, Trigger
from forge.config import load_config
from forge.identity.pack import (
    InvalidConsentError,
    create_identity_pack,
    load_identity_pack,
    validate_identity_pack,
    write_identity_pack,
)
from forge.pay.links import build_payment_links, tip_menu_html
from forge.post.manual import build_posting_packet, export_content_calendar
from forge.post.reddit import RedditPost, submit
from forge.video.pipeline import ConsentGateError, generate_video


class ForgeTyper(typer.Typer):
    """Typer app that turns tracebacks into clean user-facing errors.

    Domain errors (consent gates, missing files, bad values, unconfigured
    backends) print as one-line messages. Anything unexpected also prints
    cleanly; set FORGE_DEBUG=1 to get the full traceback for debugging.
    """

    def __call__(self, *args, **kwargs):
        import os
        import sys
        try:
            return super().__call__(*args, **kwargs)
        except (typer.Exit, SystemExit, KeyboardInterrupt):
            raise  # already-handled exits pass through untouched
        except (InvalidConsentError, ConsentGateError) as e:
            typer.echo(f"Refused: {e}", err=True)
            sys.exit(2)
        except FileNotFoundError as e:
            typer.echo(f"Not found: {e.filename or e}", err=True)
            sys.exit(1)
        except PermissionError as e:
            typer.echo(f"Permission denied: {e.filename or e}", err=True)
            sys.exit(1)
        except Exception as e:
            if os.environ.get("FORGE_DEBUG") == "1":
                raise
            name = type(e).__name__
            if isinstance(e, (KeyError, ValueError)) or \
                    name.endswith("NotConfiguredError"):
                msg = e.args[0] if e.args else e
                typer.echo(f"Error: {msg}", err=True)
            else:
                typer.echo(f"Something went wrong: {e}", err=True)
            sys.exit(1)


app = ForgeTyper(help="CreatorForge: AI creator-assistant toolkit.",
                 no_args_is_help=True)


def _cfg(config: Optional[str]):
    return load_config(config)


@app.command()
def init(path: str = typer.Argument(".", help="Project folder to set up.")):
    """Create a fresh CreatorForge project folder with example config."""
    import shutil
    dest = Path(path)
    dest.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent.parent
    for name in ("forge.yaml", "identity-pack.example.yaml",
                 "persona.example.yaml"):
        src = here / "examples" / name
        if src.is_file():
            shutil.copy2(src, dest / name.replace(".example", ""))
    typer.echo(f"Initialized CreatorForge project at {dest.resolve()}")
    typer.echo("Next: edit forge.yaml, then run `forge identity validate`.")


# -- catalog ---------------------------------------------------------------
catalog_app = typer.Typer(help="Content catalog commands.", no_args_is_help=True)
app.add_typer(catalog_app, name="catalog")


@catalog_app.command("scan")
def catalog_scan(
    root: str = typer.Argument(..., help="Folder of media to scan."),
    config: Optional[str] = typer.Option(None, "--config"),
    tags: str = typer.Option("", help="Comma-separated tags for new items."),
):
    """Scan a folder of images/videos into the catalog (dedupes by hash)."""
    cfg = _cfg(config)
    store = CatalogStore(cfg.get_path("catalog.db_path",
                                      "./forge-data/catalog.db"))
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    result = scan_directory(root, store, tags=tag_list)
    store.close()
    typer.echo(f"Scanned {result['scanned']}: added {result['added']}, "
               f"{result['skipped_duplicates']} duplicates skipped, "
               f"{result['skipped_unsupported']} unsupported files skipped.")


@catalog_app.command("list")
def catalog_list(config: Optional[str] = typer.Option(None, "--config"),
                 kind: Optional[str] = typer.Option(None, "--kind"),
                 query: Optional[str] = typer.Option(None, "--query")):
    """List catalog items (optionally filtered by kind or search query)."""
    cfg = _cfg(config)
    store = CatalogStore(cfg.get_path("catalog.db_path",
                                      "./forge-data/catalog.db"))
    items = store.search(query) if query else store.list(kind=kind)
    for it in items:
        typer.echo(f"[{it['id']}] {it['kind']:5} {it['path']} "
                   f"tags={','.join(it['tags'])}")
    typer.echo(f"{len(items)} item(s).")
    store.close()


# -- identity --------------------------------------------------------------
identity_app = typer.Typer(help="Identity pack (consent) commands.",
                           no_args_is_help=True)
app.add_typer(identity_app, name="identity")


@identity_app.command("create")
def identity_create(
    name: str = typer.Option(..., prompt=True),
    signer: str = typer.Option(..., prompt=True,
                               help="Full legal name signing consent."),
    scope: str = typer.Option(..., prompt=True,
                              help="What the consent covers."),
    statement_file: str = typer.Option(
        ..., "--statement-file",
        help="Path to the signed consent statement text file "
             "(see docs/CONSENT.md template)."),
    out: str = typer.Option("identity-pack.yaml", "--out"),
):
    """Create an identity pack from a signed consent statement."""
    statement = Path(statement_file).read_text(encoding="utf-8")
    pack = create_identity_pack(name=name, signer=signer, scope=scope,
                                statement=statement)
    validate_identity_pack(pack)  # fail fast if something is off
    p = write_identity_pack(pack, out)
    typer.echo(f"Identity pack written to {p}. Consent validated OK.")


@identity_app.command("validate")
def identity_validate(pack: Optional[str] = typer.Argument(
        None, help="Path to identity-pack.yaml (defaults to config)."),
        config: Optional[str] = typer.Option(None, "--config")):
    """Validate an identity pack's consent record."""
    path = pack or _cfg(config).get_path("identity.pack_path")
    if not path:
        raise typer.BadParameter("No pack path given and none configured.")
    try:
        validate_identity_pack(load_identity_pack(path))
    except InvalidConsentError as e:
        typer.echo(f"INVALID: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Valid consent pack: {path}")


# -- video -----------------------------------------------------------------
video_app = typer.Typer(help="Video generation commands.", no_args_is_help=True)
app.add_typer(video_app, name="video")


@video_app.command("generate")
def video_generate(
    prompt: str = typer.Option(..., "--prompt", help="Generation prompt."),
    pack: Optional[str] = typer.Option(None, "--pack",
                                       help="Identity pack (consent gate)."),
    config: Optional[str] = typer.Option(None, "--config"),
    adapter: Optional[str] = typer.Option(None, "--adapter",
                                          help="replicate | comfyui"),
    negative: str = typer.Option("", "--negative"),
    duration: int = typer.Option(5, "--duration"),
):
    """Generate a video. REFUSES to run without a valid consent pack."""
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    try:
        result = generate_video(config=cfg, identity_pack_path=pack_path,
                                prompt=prompt, negative_prompt=negative,
                                adapter_name=adapter, duration_s=duration)
    except ConsentGateError as e:
        typer.echo(f"REFUSED: {e}", err=True)
        raise typer.Exit(2)
    typer.echo("Done. Outputs:")
    for o in result.outputs:
        typer.echo(f"  {o}")


@video_app.command("prep-dataset")
def video_prep_dataset(
    out_csv: str = typer.Option("dataset/manifest.csv", "--out"),
    trigger: str = typer.Option("creatorpersona", "--trigger"),
    config: Optional[str] = typer.Option(None, "--config"),
    kind: str = typer.Option("image", "--kind"),
    limit: int = typer.Option(200, "--limit"),
):
    """Build a training manifest CSV from catalog images (see docs/VIDEO.md)."""
    from forge.video.training import build_dataset_manifest
    cfg = _cfg(config)
    store = CatalogStore(cfg.get_path("catalog.db_path",
                                      "./forge-data/catalog.db"))
    items = store.list(kind=kind, limit=limit)
    store.close()
    p = build_dataset_manifest(items, out_csv, trigger_word=trigger)
    typer.echo(f"Manifest with {len(items)} items written to {p}.")
    typer.echo("Next: review captions, then run "
               "`forge video write-kohya-config`.")


@video_app.command("write-kohya-config")
def video_kohya_config(
    out: str = typer.Option("training/kohya-lora.toml", "--out"),
    train_dir: str = typer.Option("dataset/captions", "--train-dir"),
    output_dir: str = typer.Option("training/output", "--output-dir"),
    base_model: str = typer.Option("", "--base-model",
                                   help="Base checkpoint path/URL."),
):
    """Generate a kohya_sd LoRA training TOML (GPU training still needed)."""
    from forge.video.training import write_kohya_config
    p = write_kohya_config(out, train_data_dir=train_dir,
                           output_dir=output_dir,
                           pretrained_model=base_model)
    typer.echo(f"kohya config written to {p}.")
    typer.echo("Train with: bash scripts/train_lora.sh "
               "(needs a CUDA GPU + your dataset).")


# -- post ------------------------------------------------------------------
post_app = typer.Typer(help="Posting commands.", no_args_is_help=True)
app.add_typer(post_app, name="post")


@post_app.command("reddit")
def post_reddit(
    subreddit: str = typer.Option(...),
    title: str = typer.Option(...),
    body: str = typer.Option(""),
    media: str = typer.Option(""),
    kind: str = typer.Option("text"),
    live: bool = typer.Option(False, "--live",
                              help="Actually submit. Default is dry-run."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Post to Reddit via the official API. Dry-run unless --live."""
    cfg = _cfg(config)
    result = submit(RedditPost(kind=kind, subreddit=subreddit, title=title,
                               body=body, media_path=media, dry_run=not live),
                    cfg)
    typer.echo(yaml.safe_dump(result, sort_keys=False))


@post_app.command("packet")
def post_packet(
    platform: str = typer.Option(..., help="e.g. snapchat, onlyfans, tiktok"),
    media: str = typer.Option(...),
    caption: str = typer.Option(...),
    hashtags: str = typer.Option(""),
    title: str = typer.Option(""),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Build a manual-assist posting packet (platforms with no posting API)."""
    cfg = _cfg(config)
    out = cfg.get_path("post.packets_dir", "./forge-data/packets")
    packet_dir = build_posting_packet(
        platform=platform, media_path=media, caption=caption,
        hashtags=[h.strip() for h in hashtags.split() if h.strip()],
        out_dir=out, title=title)
    typer.echo(f"Posting packet ready at {packet_dir}")
    typer.echo("Follow packet/checklist.md to post manually in the app.")


# -- chat ------------------------------------------------------------------
chat_app = typer.Typer(help="Chat bot commands (approval-gated).",
                       no_args_is_help=True)
app.add_typer(chat_app, name="chat")


def _load_engine(cfg) -> RuleEngine:
    persona_path = cfg.get_path("chat.persona_path")
    pdata: dict = {}
    if persona_path and Path(persona_path).is_file():
        with open(persona_path, encoding="utf-8") as fh:
            pdata = yaml.safe_load(fh) or {}
    triggers = [Trigger(**t) for t in pdata.get("triggers", [])]
    from forge.chat.engine import build_tip_menu_trigger
    tip_trigger = build_tip_menu_trigger(cfg)
    if tip_trigger is not None:
        triggers.append(tip_trigger)
    engine = RuleEngine(Persona.from_dict(pdata.get("persona", pdata)),
                        triggers)
    engine.escalation_config = cfg
    modes_path = cfg.get_path("chat.modes_path", "./forge-data/chat-modes.json")
    engine.load_modes(modes_path)
    engine.modes_path = modes_path  # type: ignore[attr-defined]
    queue_path = cfg.get_path("chat.queue_path", "./forge-data/chat-queue.json")
    engine.queue.load(queue_path)
    engine.queue_path = queue_path  # type: ignore[attr-defined]
    return engine


def _save_engine_modes(engine: RuleEngine) -> None:
    modes_path = getattr(engine, "modes_path",
                         "./forge-data/chat-modes.json")
    engine.save_modes(modes_path)


def _save_engine_queue(engine: RuleEngine) -> None:
    queue_path = getattr(engine, "queue_path",
                         "./forge-data/chat-queue.json")
    engine.queue.save(queue_path)


@chat_app.command("draft")
def chat_draft(platform: str = typer.Option(...), sender: str = typer.Option(...),
               text: str = typer.Option(...),
               config: Optional[str] = typer.Option(None, "--config")):
    """Draft a reply to an incoming message (goes to the approval queue)."""
    engine = _load_engine(_cfg(config))
    draft = engine.handle_message(platform=platform, sender=sender, text=text)
    _save_engine_queue(engine)
    if draft is None:
        typer.echo(f"Manual mode: message from {sender} logged as seen; "
                   "no draft created. Answer it yourself.")
        return
    typer.echo(f"Draft #{draft.id} [{draft.trigger}] status={draft.status}:")
    typer.echo(f"  In:  {draft.incoming}")
    typer.echo(f"  Out: {draft.reply}")


@chat_app.command("approve")
def chat_approve_cmd(draft_id: int = typer.Argument(...),
                     config: Optional[str] = typer.Option(None, "--config")):
    """Approve a pending draft. (Sending still happens in the app.)"""
    engine = _load_engine(_cfg(config))
    d = engine.queue.approve(draft_id)
    _save_engine_queue(engine)
    typer.echo(f"Draft #{d.id} approved. Copy/paste the reply yourself, then "
               f"run `forge chat sent {d.id}` to log it.")


@chat_app.command("sent")
def chat_sent_cmd(draft_id: int = typer.Argument(...),
                  config: Optional[str] = typer.Option(None, "--config")):
    """Log that an approved draft was actually sent."""
    engine = _load_engine(_cfg(config))
    d = engine.queue.mark_sent(draft_id)
    _save_engine_queue(engine)
    typer.echo(f"Draft #{d.id} logged as sent.")


@chat_app.command("mode")
def chat_mode_cmd(platform: str = typer.Option(...),
                  sender: str = typer.Option(...),
                  mode: str = typer.Option(..., help="auto | approve-first | manual"),
                  config: Optional[str] = typer.Option(None, "--config")):
    """Set the per-conversation mode for (platform, sender)."""
    cfg = _cfg(config)
    engine = _load_engine(cfg)
    engine.set_conversation_mode(platform, sender, mode)
    _save_engine_modes(engine)
    typer.echo(f"Conversation ({platform}, {sender}) set to '{mode}'.")
    if mode == "auto":
        typer.echo("WARNING: auto mode approves drafts automatically. "
                   "You are responsible for what gets sent.")


@chat_app.command("queue")
def chat_queue_cmd(config: Optional[str] = typer.Option(None, "--config")):
    """Show pending drafts."""
    engine = _load_engine(_cfg(config))
    pending = engine.queue.pending()
    if not pending:
        typer.echo("No pending drafts.")
        return
    for d in pending:
        typer.echo(f"#{d.id} [{d.platform}/{d.sender}] ({d.trigger}):")
        typer.echo(f"  In:  {d.incoming}")
        typer.echo(f"  Out: {d.reply}")


@chat_app.command("worker")
def chat_worker_cmd(
    adapter: str = typer.Option("manual-inbox", "--adapter"),
    inbox: str = typer.Option("inbox.jsonl", "--inbox",
                              help="JSONL inbox file for manual-inbox."),
    interval: int = typer.Option(30, "--interval"),
    once: bool = typer.Option(False, "--once", help="Single pass, then exit."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Run the chat worker: poll an adapter and draft replies.

    With manual-inbox, append {"platform","sender","text"} lines to the
    inbox file; the worker drafts them into the approval queue.
    """
    from forge.chat.worker import PollingWorker, get_adapter
    engine = _load_engine(_cfg(config))
    worker = PollingWorker(engine, get_adapter(adapter, inbox_path=inbox))
    if once:
        drafts = worker.run_once()
        _save_engine_queue(engine)
        typer.echo(f"Processed {len(drafts)} message(s).")
    else:
        worker.run_forever(interval)
        _save_engine_queue(engine)


@chat_app.command("style-build")
def chat_style_build(
    transcript: str = typer.Option(..., "--transcript",
                                   help="JSON list of {sender,text,ts} messages."),
    pack: str = typer.Option(..., "--pack", help="Identity pack (consent gate)."),
    out: str = typer.Option("style-profile.json", "--out"),
    vault: Optional[str] = typer.Option(None, "--vault",
                                        help="Also store encrypted in this vault."),
    vault_password: Optional[str] = typer.Option(None, "--vault-password"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Build her text style profile from exported chats (consent-gated)."""
    import json as _json
    from forge.chat.style import build_style_profile
    messages = _json.loads(Path(transcript).read_text(encoding="utf-8"))
    profile = build_style_profile(messages, identity_pack_path=pack)
    Path(out).write_text(_json.dumps(profile.to_dict(), indent=2),
                         encoding="utf-8")
    typer.echo(f"Style profile ({profile.sample_count} messages) -> {out}")
    if vault:
        v = _open_vault(vault, vault_password)
        v.put_json("style-profile", profile.to_dict())
        typer.echo("Also stored encrypted in vault as 'style-profile'.")
    typer.echo("Review it with: forge chat style-report --profile " + out)


@chat_app.command("style-report")
def chat_style_report(
    profile: str = typer.Option("style-profile.json", "--profile"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Print the human-readable style report for review/editing."""
    import json as _json
    from forge.chat.style import StyleProfile, style_report_md
    data = _json.loads(Path(profile).read_text(encoding="utf-8"))
    typer.echo(style_report_md(StyleProfile.from_dict(data)))


# -- pay -------------------------------------------------------------------
pay_app = typer.Typer(help="Payment link commands.", no_args_is_help=True)
app.add_typer(pay_app, name="pay")


@pay_app.command("links")
def pay_links(config: Optional[str] = typer.Option(None, "--config")):
    """Print all configured payment URLs."""
    links = build_payment_links(_cfg(config))
    if not links:
        typer.echo("No payment handles configured under 'pay' in forge.yaml.")
        return
    for label, url in links.items():
        typer.echo(f"{label}: {url}")


@pay_app.command("tip-menu")
def pay_tip_menu(out: str = typer.Option("tip-menu.html", "--out"),
                 config: Optional[str] = typer.Option(None, "--config")):
    """Generate a standalone tip-menu HTML page."""
    cfg = _cfg(config)
    html_page = tip_menu_html(build_payment_links(cfg),
                              cfg.get_path("pay.tip_menu", []))
    Path(out).write_text(html_page, encoding="utf-8")
    typer.echo(f"Tip menu written to {out}")


# -- vault -----------------------------------------------------------------
vault_app = typer.Typer(help="Encrypted vault commands.", no_args_is_help=True)
app.add_typer(vault_app, name="vault")


def _vault_password(password: Optional[str]) -> str:
    import os
    pw = password or os.environ.get("FORGE_VAULT_PASSWORD")
    if pw:
        return pw
    return typer.prompt("Vault password", hide_input=True, confirmation_prompt=False)


def _open_vault(path: str, password: Optional[str]):
    from forge.vault.store import Vault
    v = Vault(path)
    try:
        v._key()
    except Exception:
        v.unlock(_vault_password(password))
    return v


@vault_app.command("init")
def vault_init(path: str = typer.Argument("./forge-data/vault"),
               password: Optional[str] = typer.Option(None, "--password")):
    """Create a new encrypted vault (AES-256-GCM, scrypt key)."""
    from forge.vault.store import Vault
    pw = _vault_password(password)
    Vault.init(path, pw)
    typer.echo(f"Vault created at {path} and unlocked for this session.")
    typer.echo("The password is never stored. Lose it = lose the vault.")


@vault_app.command("unlock")
def vault_unlock(path: str = typer.Argument("./forge-data/vault"),
                 password: Optional[str] = typer.Option(None, "--password")):
    """Unlock the vault (verifies password, starts a session)."""
    from forge.vault.store import Vault
    Vault(path).unlock(_vault_password(password))
    typer.echo("Vault unlocked.")


@vault_app.command("lock")
def vault_lock(path: str = typer.Argument("./forge-data/vault")):
    """Lock the vault (ends the session)."""
    from forge.vault.store import Vault
    Vault(path).lock()
    typer.echo("Vault locked.")


@vault_app.command("import")
def vault_import(path: str = typer.Argument("./forge-data/vault"),
                 file: str = typer.Argument(..., help="File to encrypt into the vault."),
                 name: Optional[str] = typer.Option(None, "--name"),
                 password: Optional[str] = typer.Option(None, "--password")):
    """Encrypt a file into the vault."""
    v = _open_vault(path, password)
    blob_name = name or Path(file).name
    v.put(blob_name, Path(file).read_bytes())
    typer.echo(f"Stored as '{blob_name}' ({Path(file).stat().st_size} bytes).")


@vault_app.command("export")
def vault_export(path: str = typer.Argument("./forge-data/vault"),
                 name: str = typer.Argument(..., help="Blob name in the vault."),
                 out: Optional[str] = typer.Option(None, "--out"),
                 password: Optional[str] = typer.Option(None, "--password")):
    """Decrypt a vault blob back to a file (encrypted bundle handling)."""
    v = _open_vault(path, password)
    data = v.get(name)
    dest = out or name
    Path(dest).write_bytes(data)
    typer.echo(f"Wrote {len(data)} bytes to {dest}.")


@vault_app.command("list")
def vault_list(path: str = typer.Argument("./forge-data/vault"),
               password: Optional[str] = typer.Option(None, "--password")):
    """List blobs in the vault."""
    v = _open_vault(path, password)
    for name in v.list():
        typer.echo(name)


@vault_app.command("save-settings")
def vault_save_settings(path: str = typer.Argument("./forge-data/vault"),
                        config: Optional[str] = typer.Option(None, "--config"),
                        password: Optional[str] = typer.Option(None, "--password")):
    """Store the current forge.yaml encrypted in the vault as JSON."""
    v = _open_vault(path, password)
    cfg = _cfg(config)
    v.put_json("settings", {k: v_ for k, v_ in cfg.items()
                            if not k.startswith("_")})
    typer.echo("Settings saved encrypted as 'settings'.")


@vault_app.command("load-settings")
def vault_load_settings(path: str = typer.Argument("./forge-data/vault"),
                        out: str = typer.Option("forge.yaml.restored",
                                                "--out"),
                        password: Optional[str] = typer.Option(None, "--password")):
    """Restore forge.yaml from the vault's encrypted settings."""
    v = _open_vault(path, password)
    settings = v.get_json("settings")
    with open(out, "w", encoding="utf-8") as fh:
        yaml.safe_dump(settings, fh, sort_keys=False)
    typer.echo(f"Settings restored to {out}. Move into place yourself.")


# -- connect ---------------------------------------------------------------
connect_app = typer.Typer(help="Platform connector commands.",
                           no_args_is_help=True)
app.add_typer(connect_app, name="connect")


@connect_app.command("list")
def connect_list(csv_out: Optional[str] = typer.Option(None, "--csv")):
    """Show the honest per-platform capability matrix."""
    from forge.connect.registry import capabilities_table, export_capability_csv
    rows = capabilities_table()
    typer.echo(f"{'connector':12} {'import':8} {'export':8} platform")
    typer.echo("-" * 60)
    for r in rows:
        typer.echo(f"{r['connector']:12} {r['import']:8} {r['export']:8} {r['platform']}")
    typer.echo("\nfull = real API/automated | manual = she does the site/app "
               "part, we handle files | none = not possible")
    if csv_out:
        p = export_capability_csv(csv_out)
        typer.echo(f"Matrix exported to {p}")


@connect_app.command("import")
def connect_import(platform: str = typer.Option(...,
                                                help="fansly | onlyfans | reddit | filesystem | url"),
                   source: str = typer.Option(...,
                                              help="Folder, file, or URL (per connector)."),
                   dest: str = typer.Option("./forge-data/connect-import"),
                   config: Optional[str] = typer.Option(None, "--config")):
    """Import content via a connector.

    For fansly/onlyfans this is MANUAL: she exports her data from the site
    first (see `forge connect list` notes), then this ingests the files.
    """
    from forge.connect.registry import get_connector
    connector = get_connector(platform)
    caps = connector.capabilities()
    if caps.import_level == "manual":
        typer.echo(f"NOTE ({platform}): {caps.import_notes}")
    summary = connector.import_data(source, dest, config=config)
    typer.echo(yaml.safe_dump(summary, sort_keys=False))


# -- persona ---------------------------------------------------------------
persona_app = typer.Typer(help="Persona trainer registry + voice.",
                           no_args_is_help=True)
app.add_typer(persona_app, name="persona")


@persona_app.command("trainers")
def persona_trainers(kind: Optional[str] = typer.Option(
        None, "--kind", help="local-gpu | paid-api")):
    """List real persona/LoRA trainer options with honest requirements."""
    from forge.persona.trainers import list_trainers
    for t in list_trainers(kind):
        typer.echo(f"\n== {t.name} [{t.kind}] ==")
        typer.echo(f"   docs: {t.docs_url}")
        typer.echo(f"   needs: {', '.join(t.needs)}")
        typer.echo(f"   cost: {t.cost_notes}")
        typer.echo(f"   gpu: {t.gpu_notes}")
        for i, step in enumerate(t.setup_steps, 1):
            typer.echo(f"   {i}. {step}")


@persona_app.command("voice-clone")
def persona_voice_clone(
    name: str = typer.Option(...),
    audio: list[str] = typer.Option(..., "--audio",
                                    help="Sample audio files (repeatable)."),
    pack: Optional[str] = typer.Option(None, "--pack"),
    key: Optional[str] = typer.Option(None, "--key"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Clone her voice via ElevenLabs (consent-gated, needs API key)."""
    from forge.persona.voice import ElevenLabsVoice
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    voice = ElevenLabsVoice(key, cfg.get_path("persona.elevenlabs_key"))
    voice_id = voice.clone_voice(name=name, audio_files=audio,
                                 identity_pack_path=pack_path)
    typer.echo(f"Voice cloned. voice_id={voice_id}")
    typer.echo("Save this voice_id in forge.yaml under persona.elevenlabs_voice_id.")


@persona_app.command("voice-speak")
def persona_voice_speak(
    text: str = typer.Option(...),
    voice_id: Optional[str] = typer.Option(None, "--voice-id"),
    out: str = typer.Option("voiceover.mp3", "--out"),
    pack: Optional[str] = typer.Option(None, "--pack"),
    key: Optional[str] = typer.Option(None, "--key"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Synthesize speech with her cloned voice (consent-gated)."""
    from forge.persona.voice import ElevenLabsVoice
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    vid = voice_id or cfg.get_path("persona.elevenlabs_voice_id")
    if not vid:
        raise typer.BadParameter("No voice_id: clone first or set "
                                 "persona.elevenlabs_voice_id.")
    voice = ElevenLabsVoice(key, cfg.get_path("persona.elevenlabs_key"))
    p = voice.speak(text=text, voice_id=vid, out_path=out,
                    identity_pack_path=pack_path)
    typer.echo(f"Audio written to {p}")


# -- video: scene director ---------------------------------------------------
@video_app.command("scene")
def video_scene(
    scene: str = typer.Option(..., "--scene", help="Scene YAML file."),
    pack: Optional[str] = typer.Option(None, "--pack"),
    adapter: Optional[str] = typer.Option(None, "--adapter"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Resolve a scene against her comfort boundary, then produce it.

    AI-only scenes generate via the consent-gated pipeline; self-filmed
    scenes pull real catalog footage; anything uncategorized is refused.
    """
    from forge.video.pipeline import SceneRefused, generate_scene_video
    from forge.video.scenes import SceneRefusedError
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    catalog_items = None
    try:
        store = CatalogStore(cfg.get_path("catalog.db_path",
                                          "./forge-data/catalog.db"))
        catalog_items = store.list(kind="image", limit=500)
        store.close()
    except Exception:
        pass
    try:
        result = generate_scene_video(
            config=cfg, identity_pack_path=pack_path, scene_path=scene,
            catalog_items=catalog_items, adapter_name=adapter)
    except (SceneRefusedError, SceneRefused) as e:
        typer.echo(f"REFUSED: {e}", err=True)
        raise typer.Exit(3)
    typer.echo(yaml.safe_dump(result, sort_keys=False))


# -- menu ------------------------------------------------------------------
@app.command()
def menu():
    """Interactive numbered menu over every command (beginner-friendly)."""
    from forge.menu import run_menu
    run_menu()


# -- skills ----------------------------------------------------------------
skills_app = typer.Typer(help="Plugin/skill commands.", no_args_is_help=True)
app.add_typer(skills_app, name="skills")


@skills_app.command("list")
def skills_list(config: Optional[str] = typer.Option(None, "--config")):
    """List installed skills (built-in + skills.paths in forge.yaml)."""
    from forge.skills import discover_skills
    skills = discover_skills(_cfg(config))
    if not skills:
        typer.echo("No skills found.")
        return
    for name in sorted(skills):
        s = skills[name]
        typer.echo(f"- {s.name} v{s.version}: {s.description}")
        if s.usage:
            typer.echo(f"    {s.usage}")


@skills_app.command("run")
def skills_run(name: str = typer.Argument(..., help="Skill name."),
               args: list[str] = typer.Argument(
                   None, help="Extra args passed to the skill."),
               config: Optional[str] = typer.Option(None, "--config")):
    """Run a skill: forge skills run watermark --text @her in.png out.png"""
    from forge.skills import SkillError, run_skill
    try:
        typer.echo(run_skill(name, list(args or []), _cfg(config)))
    except SkillError as e:
        typer.echo(f"Skill failed: {e}", err=True)
        raise typer.Exit(1)


# -- post: scheduler ---------------------------------------------------------
@post_app.command("schedule")
def post_schedule_cmd(
    platform: str = typer.Option(...),
    media: str = typer.Option(...),
    caption: str = typer.Option(...),
    when: str = typer.Option(..., "--when",
                             help="ISO-8601, e.g. 2026-10-10T19:00"),
    title: str = typer.Option(""),
    hashtags: str = typer.Option(""),
    notes: str = typer.Option(""),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Build a manual posting packet AND schedule it for later.

    Reminder: Snapchat/OnlyFans/TikTok have no posting API -- scheduling
    means "remind me", not "post for me". See what's due with
    `forge post due`.
    """
    from forge.post.schedule import Scheduler
    cfg = _cfg(config)
    out = cfg.get_path("post.packets_dir", "./forge-data/packets")
    packet_dir = build_posting_packet(
        platform=platform, media_path=media, caption=caption,
        hashtags=[h.strip() for h in hashtags.split() if h.strip()],
        out_dir=out, title=title, scheduled_for=when)
    sched = Scheduler(cfg.get_path("post.schedule_db",
                                   "./forge-data/schedule.db"))
    row = sched.schedule_packet(platform=platform, packet_dir=packet_dir,
                                scheduled_for=when, title=title, notes=notes)
    sched.close()
    typer.echo(f"Packet ready at {packet_dir}")
    typer.echo(f"Scheduled #{row['id']} for {row['scheduled_for']} "
               f"(status: {row['status']}).")
    typer.echo("This is a REMINDER, not auto-posting -- post it yourself "
               "in the app when it's due.")


@post_app.command("due")
def post_due_cmd(config: Optional[str] = typer.Option(None, "--config")):
    """Show scheduled posts whose time has come (post them manually)."""
    from forge.post.schedule import Scheduler
    cfg = _cfg(config)
    sched = Scheduler(cfg.get_path("post.schedule_db",
                                   "./forge-data/schedule.db"))
    due = sched.due()
    sched.close()
    if not due:
        typer.echo("Nothing due right now. Upcoming:")
        sched2 = Scheduler(cfg.get_path("post.schedule_db",
                                        "./forge-data/schedule.db"))
        for r in sched2.upcoming(limit=5):
            typer.echo(f"  #{r['id']} {r['scheduled_for']} [{r['platform']}] "
                       f"{r['title']}")
        sched2.close()
        return
    typer.echo("DUE NOW -- post these in the apps, then mark done:")
    for r in due:
        typer.echo(f"  #{r['id']} [{r['platform']}] {r['title'] or '(no title)'}")
        typer.echo(f"      packet: {r['packet_dir']}")


@post_app.command("scheduled")
def post_scheduled_cmd(
    status: Optional[str] = typer.Option(None, "--status",
                                         help="scheduled | done | skipped"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """List scheduled posts (optionally filtered by status)."""
    from forge.post.schedule import Scheduler
    cfg = _cfg(config)
    sched = Scheduler(cfg.get_path("post.schedule_db",
                                   "./forge-data/schedule.db"))
    rows = sched.list(status=status)
    sched.close()
    if not rows:
        typer.echo("No scheduled posts.")
        return
    for r in rows:
        typer.echo(f"#{r['id']} {r['scheduled_for']} [{r['platform']}] "
                   f"{r['title'] or '(no title)'} -- {r['status']}")


@post_app.command("mark-done")
def post_mark_done_cmd(
    post_id: int = typer.Argument(...),
    status: str = typer.Option("done", "--status",
                               help="done | skipped | scheduled"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Mark a scheduled post done (or skipped)."""
    from forge.post.schedule import Scheduler
    cfg = _cfg(config)
    sched = Scheduler(cfg.get_path("post.schedule_db",
                                   "./forge-data/schedule.db"))
    try:
        row = sched.mark(post_id, status)
    except (KeyError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    finally:
        sched.close()
    typer.echo(f"#{row['id']} marked {row['status']}.")


# -- analytics ---------------------------------------------------------------
analytics_app = typer.Typer(help="Stats & earnings commands.",
                            no_args_is_help=True)
app.add_typer(analytics_app, name="analytics")


def _analytics_store(cfg):
    from forge.analytics.store import AnalyticsStore
    return AnalyticsStore(cfg.get_path("analytics.db_path",
                                       "./forge-data/analytics.db"))


@analytics_app.command("log-post")
def analytics_log_post(
    platform: str = typer.Option(...),
    post_ref: str = typer.Option(..., "--post-ref",
                                 help="Post id or URL."),
    title: str = typer.Option(""),
    views: int = typer.Option(0),
    likes: int = typer.Option(0),
    comments: int = typer.Option(0),
    earnings: float = typer.Option(0.0),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Manually log stats for one post (OnlyFans/Fansly/etc have no API)."""
    store = _analytics_store(_cfg(config))
    row = store.log_post_stat(platform=platform, post_ref=post_ref,
                              title=title, views=views, likes=likes,
                              comments=comments, earnings=earnings)
    store.close()
    typer.echo(f"Logged stats for [{platform}] {post_ref} (id {row['id']}).")


@analytics_app.command("log-earning")
def analytics_log_earning(
    platform: str = typer.Option(...),
    amount: float = typer.Option(...),
    kind: str = typer.Option("", help="subs | tips | ppv | custom | ..."),
    month: str = typer.Option("", help="YYYY-MM, blank = this month."),
    currency: str = typer.Option("USD"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Log money earned on a platform."""
    store = _analytics_store(_cfg(config))
    row = store.log_earning(platform=platform, amount=amount, kind=kind,
                            month=month, currency=currency)
    store.close()
    typer.echo(f"Logged {currency} {amount:.2f} on {platform} "
               f"for {row['month']} ({kind or 'unspecified'}).")


@analytics_app.command("import-earnings")
def analytics_import_earnings(
    csv_path: str = typer.Argument(...),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Import earnings from CSV (platform,amount[,currency,kind,month])."""
    store = _analytics_store(_cfg(config))
    try:
        n = store.import_earnings_csv(csv_path)
    finally:
        store.close()
    typer.echo(f"Imported {n} earning row(s) from {csv_path}.")


@analytics_app.command("report")
def analytics_report(config: Optional[str] = typer.Option(None, "--config")):
    """Print a plain-English analytics summary."""
    from forge.analytics.report import build_report
    store = _analytics_store(_cfg(config))
    try:
        typer.echo(build_report(store))
    finally:
        store.close()


@analytics_app.command("reddit-stats")
def analytics_reddit_stats(
    submission_id: str = typer.Argument(...),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Fetch LIVE stats for a Reddit submission (official API)."""
    from forge.analytics.store import reddit_submission_stats
    from forge.post.reddit import RedditNotConfiguredError
    cfg = _cfg(config)
    try:
        stats = reddit_submission_stats(cfg, submission_id)
    except RedditNotConfiguredError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(yaml.safe_dump(stats, sort_keys=False))
    # also store it locally for the report
    store = _analytics_store(cfg)
    try:
        store.log_post_stat(platform="reddit", post_ref=submission_id,
                            title=stats["title"],
                            likes=stats["score"],
                            comments=stats["num_comments"],
                            views=stats["views"] or 0)
    finally:
        store.close()
    typer.echo("Saved into local stats.")


# -- chat: templates, reject, worker-once --------------------------------------
@chat_app.command("reject")
def chat_reject_cmd(draft_id: int = typer.Argument(...),
                    config: Optional[str] = typer.Option(None, "--config")):
    """Reject a pending draft."""
    engine = _load_engine(_cfg(config))
    try:
        d = engine.queue.reject(draft_id)
    except (KeyError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    _save_engine_queue(engine)
    typer.echo(f"Draft #{d.id} rejected.")


@chat_app.command("worker-once")
def chat_worker_once(
    inbox: str = typer.Option("inbox.jsonl", "--inbox"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Single worker pass over the manual inbox (drafts into the queue)."""
    from forge.chat.worker import PollingWorker, get_adapter
    engine = _load_engine(_cfg(config))
    worker = PollingWorker(engine, get_adapter("manual-inbox",
                                               inbox_path=inbox))
    drafts = worker.run_once()
    _save_engine_queue(engine)
    typer.echo(f"Processed {len(drafts)} message(s).")
    for d in drafts:
        flag = " [ESCALATED: " + ",".join(d.escalation_categories) + "]" \
            if d.escalated else ""
        typer.echo(f"  #{d.id} ({d.platform}/{d.sender}){flag}: {d.reply[:80]}")


@chat_app.command("template-add")
def chat_template_add(
    name: str = typer.Option(...),
    text: str = typer.Option(...),
    category: str = typer.Option("general"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Save a canned response template. {sender} = their name."""
    from forge.chat.templates import add_template, ensure_defaults
    ensure_defaults()
    try:
        add_template(name, text, category)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"Template '{name}' saved.")


@chat_app.command("template-list")
def chat_template_list(config: Optional[str] = typer.Option(None, "--config")):
    """List canned response templates."""
    from forge.chat.templates import ensure_defaults, load_templates
    ensure_defaults()
    templates = load_templates()
    if not templates:
        typer.echo("No templates.")
        return
    for name in sorted(templates):
        t = templates[name]
        typer.echo(f"- {name} [{t.get('category', 'general')}]: "
                   f"{t['text'][:70]}")


@chat_app.command("template-use")
def chat_template_use(
    name: str = typer.Option(...),
    platform: str = typer.Option(...),
    sender: str = typer.Option(...),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Draft a canned template into the approval queue."""
    from forge.chat.templates import ensure_defaults, render_template
    ensure_defaults()
    cfg = _cfg(config)
    engine = _load_engine(cfg)
    try:
        text = render_template(name, sender=sender,
                               persona_name=engine.persona.name)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    draft = engine.queue.add(platform=platform, sender=sender,
                             incoming=f"(template: {name})", reply=text,
                             trigger=f"template:{name}")
    _save_engine_queue(engine)
    typer.echo(f"Draft #{draft.id} queued from template '{name}':")
    typer.echo(f"  {text}")


@chat_app.command("template-delete")
def chat_template_delete(
    name: str = typer.Option(...),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Delete a canned response template."""
    from forge.chat.templates import delete_template
    try:
        delete_template(name)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"Template '{name}' deleted.")


def _load_lexicon(cfg):
    from forge.chat.lexicon import CustomLexicon
    return CustomLexicon.load(
        cfg.get_path("chat.lexicon_path", "./forge-data/lexicon.json"))


def _save_lexicon(cfg, lex) -> None:
    lex.save(cfg.get_path("chat.lexicon_path", "./forge-data/lexicon.json"))


@chat_app.command("lexicon-add")
def chat_lexicon_add(
    category: str = typer.Option(..., help="slang|phrases|pet_names|emoji|openers|closers|spicy"),
    term: str = typer.Option(...),
    note: str = typer.Option("", "--note"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Save a word/phrase to her custom word bank."""
    from forge.chat.lexicon import CATEGORIES
    cfg = _cfg(config)
    lex = _load_lexicon(cfg)
    try:
        added = lex.add(category, term, note)
    except ValueError as e:
        typer.echo(f"Pick a category: {', '.join(CATEGORIES)}", err=True)
        raise typer.Exit(1)
    if not added:
        typer.echo(f"Already in {category}: {term}")
        return
    _save_lexicon(cfg, lex)
    typer.echo(f"Saved to {category}: {term}")


@chat_app.command("lexicon-list")
def chat_lexicon_list(
    category: Optional[str] = typer.Option(None, "--category"),
    search: Optional[str] = typer.Option(None, "--search"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """List her custom word bank (optionally one category or a search)."""
    cfg = _cfg(config)
    lex = _load_lexicon(cfg)
    if search:
        hits = lex.search(search)
        if not hits:
            typer.echo(f"No matches for '{search}'.")
            return
        for cat, e in hits:
            typer.echo(f"- [{cat}] {e.term}" + (f" ({e.note})" if e.note else ""))
        return
    data = lex.list(category)
    empty = True
    for cat, items in data.items():
        if items:
            empty = False
            typer.echo(f"[{cat}]")
            for e in items:
                typer.echo(f"  - {e.term}" + (f" ({e.note})" if e.note else ""))
    if empty:
        typer.echo("Word bank is empty. Add with: forge chat lexicon-add")


@chat_app.command("lexicon-remove")
def chat_lexicon_remove(
    category: str = typer.Option(...),
    term: str = typer.Option(...),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Remove a word/phrase from her word bank."""
    cfg = _cfg(config)
    lex = _load_lexicon(cfg)
    try:
        removed = lex.remove(category, term)
    except ValueError:
        typer.echo("Unknown category.", err=True)
        raise typer.Exit(1)
    if removed:
        _save_lexicon(cfg, lex)
        typer.echo(f"Removed from {category}: {term}")
    else:
        typer.echo(f"Not found in {category}: {term}")


@chat_app.command("lexicon-import")
def chat_lexicon_import(
    file: str = typer.Option(..., "--file", help="JSON file to import."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Import a word bank JSON file (merges, skips dupes)."""
    import json as _json
    cfg = _cfg(config)
    lex = _load_lexicon(cfg)
    data = _json.loads(Path(file).read_text(encoding="utf-8"))
    incoming = (data.get("entries") or {}) if isinstance(data, dict) else {}
    added = 0
    for cat, items in incoming.items():
        for item in items:
            term = item.get("term") if isinstance(item, dict) else item
            if term and lex.add(cat, str(term),
                               item.get("note", "") if isinstance(item, dict) else ""):
                added += 1
    _save_lexicon(cfg, lex)
    typer.echo(f"Imported {added} new term(s).")


@chat_app.command("lexicon-export")
def chat_lexicon_export(
    file: str = typer.Option("lexicon.json", "--file"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Export her word bank to a JSON file (backup/share)."""
    cfg = _cfg(config)
    lex = _load_lexicon(cfg)
    lex.save(file)
    total = sum(len(v) for v in lex.entries.values())
    typer.echo(f"Exported {total} term(s) to {file}")


@chat_app.command("lexicon-adopt")
def chat_lexicon_adopt(
    profile: str = typer.Option("style-profile.json", "--profile"),
    n: int = typer.Option(10, "--n", help="How many top words to adopt."),
    category: str = typer.Option("slang", "--category"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Promote top words from her learned style profile into the word bank."""
    import json as _json
    from forge.chat.style import StyleProfile
    cfg = _cfg(config)
    data = _json.loads(Path(profile).read_text(encoding="utf-8"))
    prof = StyleProfile.from_dict(data)
    lex = _load_lexicon(cfg)
    try:
        added = lex.adopt_from_profile(prof, n=n, category=category)
    except ValueError:
        typer.echo("Unknown category.", err=True)
        raise typer.Exit(1)
    _save_lexicon(cfg, lex)
    typer.echo(f"Adopted {len(added)} word(s) into {category}: "
               f"{', '.join(added) or '(none new)'}")
    typer.echo("Review with: forge chat lexicon-list")


# -- video: batch queue --------------------------------------------------------
@video_app.command("queue-add")
def video_queue_add(
    prompt: str = typer.Option(..., "--prompt"),
    pack: Optional[str] = typer.Option(None, "--pack"),
    adapter: str = typer.Option("", "--adapter"),
    duration: int = typer.Option(5, "--duration"),
    negative: str = typer.Option("", "--negative"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Queue a video generation to run later (consent still required)."""
    from forge.video.queue import VideoQueue
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    q = VideoQueue(cfg.get_path("video.queue_db",
                                "./forge-data/video-queue.db"))
    job = q.add(prompt=prompt, pack_path=pack_path, negative_prompt=negative,
                adapter=adapter, duration_s=duration)
    q.close()
    typer.echo(f"Queued job #{job['id']}. Run with: forge video queue-run")


@video_app.command("queue-run")
def video_queue_run(config: Optional[str] = typer.Option(None, "--config")):
    """Run all queued video jobs sequentially (consent-gated each)."""
    from forge.video.queue import VideoQueue
    cfg = _cfg(config)
    q = VideoQueue(cfg.get_path("video.queue_db",
                                "./forge-data/video-queue.db"))
    jobs = q.run_all(cfg)
    q.close()
    if not jobs:
        typer.echo("Queue is empty.")
        return
    for j in jobs:
        if j["status"] == "done":
            typer.echo(f"#{j['id']} done: {', '.join(j['outputs'])}")
        else:
            typer.echo(f"#{j['id']} FAILED: {j['error']}")


@video_app.command("queue-list")
def video_queue_list(
    status: Optional[str] = typer.Option(None, "--status"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """List video queue jobs."""
    from forge.video.queue import VideoQueue
    cfg = _cfg(config)
    q = VideoQueue(cfg.get_path("video.queue_db",
                                "./forge-data/video-queue.db"))
    jobs = q.list(status=status)
    q.close()
    if not jobs:
        typer.echo("No jobs.")
        return
    for j in jobs:
        typer.echo(f"#{j['id']} [{j['status']}] {j['prompt'][:60]}")


# -- identity: multi-persona ---------------------------------------------------
def _default_pack(cfg) -> Optional[str]:
    """Active persona pack > identity.pack_path from config (may be None)."""
    from forge.identity.pack import resolve_pack_path
    return resolve_pack_path(
        None, cfg, cfg.get_path("data_dir", "./forge-data"))


@identity_app.command("list")
def identity_list_cmd(config: Optional[str] = typer.Option(None, "--config")):
    """List persona packs (multi-persona) and which is active."""
    from forge.identity.pack import get_active_pack, list_packs
    cfg = _cfg(config)
    packs_dir = cfg.get_path("identity.packs_dir", "./identity-packs")
    data_dir = cfg.get_path("data_dir", "./forge-data")
    active = get_active_pack(data_dir)
    packs = list_packs(packs_dir)
    # also surface the legacy single pack_path if configured
    legacy = cfg.get_path("identity.pack_path")
    if legacy and Path(legacy).is_file() and not any(
            p["path"] == str(Path(legacy)) for p in packs):
        packs.append({"path": str(Path(legacy)), "name": "(legacy pack)",
                      "version": 1, "status": "valid"})
    if not packs:
        typer.echo(f"No packs in {packs_dir}. Create one with "
                   "`forge identity create`.")
        return
    for p in packs:
        marker = "  <-- active" if active and Path(p["path"]) == Path(active) \
            else ""
        typer.echo(f"- {p['name']} v{p['version']} [{p['status']}]")
        typer.echo(f"    {p['path']}{marker}")


@identity_app.command("use")
def identity_use_cmd(
    pack: str = typer.Argument(..., help="Pack path to make active."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Switch the active persona (validates consent first)."""
    from forge.identity.pack import set_active_pack
    cfg = _cfg(config)
    try:
        path = set_active_pack(pack, cfg.get_path("data_dir",
                                                  "./forge-data"))
    except InvalidConsentError as e:
        typer.echo(f"INVALID: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Active persona pack: {path}")


@identity_app.command("new-version")
def identity_new_version_cmd(
    pack: str = typer.Argument(...),
    notes: str = typer.Option("", "--notes"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Create a versioned copy of a pack (v1 -> v2, original untouched)."""
    from forge.identity.pack import bump_pack_version
    try:
        dest = bump_pack_version(pack, notes)
    except InvalidConsentError as e:
        typer.echo(f"INVALID: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"New version written to {dest}")


# -- vault: backup / restore ---------------------------------------------------
@vault_app.command("backup")
def vault_backup(
    path: str = typer.Argument("./forge-data/vault"),
    out: str = typer.Option("forge-backup.enc", "--out"),
    password: Optional[str] = typer.Option(None, "--password"),
):
    """Encrypted backup: vault blobs + settings + databases.

    Everything is encrypted with your vault password into one file.
    Restore with: forge vault restore --backup forge-backup.enc
    """
    from forge.vault.bundle import collect_dir, write_bundle_file
    v = _open_vault(path, password)
    files: dict[str, bytes] = {}
    # vault blobs (raw .enc files, still encrypted -- double-wrapped, fine)
    files.update(collect_dir(Path(path) / "data", "vault/data"))
    files["vault/vault.json"] = (Path(path) / "vault.json").read_bytes()
    # settings + operational databases next to the vault
    data_dir = Path(path).parent
    for name in ("catalog.db", "schedule.db", "analytics.db",
                 "video-queue.db", "chat-queue.json", "chat-modes.json",
                 "chat-templates.json", "promptlib.json",
                 "style-profile.json"):
        p = data_dir / name
        if p.is_file():
            files[f"data/{name}"] = p.read_bytes()
    cfg_yaml = Path("forge.yaml")
    if cfg_yaml.is_file():
        files["settings/forge.yaml"] = cfg_yaml.read_bytes()
    pw = _vault_password(password)
    dest = write_bundle_file(files, out, pw,
                             meta={"kind": "creatorforge-backup",
                                   "version": 1})
    typer.echo(f"Backup ({len(files)} files) written encrypted to {dest}.")
    typer.echo("Keep the password safe -- without it the backup is useless.")


@vault_app.command("restore")
def vault_restore(
    backup: str = typer.Option(..., "--backup"),
    dest: str = typer.Option("./forge-restore", "--dest"),
    password: Optional[str] = typer.Option(None, "--password"),
):
    """Restore an encrypted backup into a folder (docs/SETUP.md: Restore)."""
    from forge.vault.bundle import BundleError, open_bundle
    pw = _vault_password(password)
    try:
        files, meta = open_bundle(Path(backup).read_bytes(), pw)
    except BundleError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    if meta.get("kind") != "creatorforge-backup":
        typer.echo("This is not a CreatorForge backup bundle.", err=True)
        raise typer.Exit(1)
    dest_p = Path(dest)
    restored = 0
    for name, data in files.items():
        target = dest_p / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        restored += 1
    typer.echo(f"Restored {restored} files to {dest_p}.")
    typer.echo("To use it: copy vault/ back over your vault dir (after "
               "unlocking to confirm), and data/*.db / *.json over "
               "forge-data/. See docs/SETUP.md for the full checklist.")


# -- profile export / import ---------------------------------------------------
@app.command("export-profile")
def export_profile_cmd(
    out: str = typer.Option("forge-profile.enc", "--out"),
    password: Optional[str] = typer.Option(None, "--password",
                                           help="Bundle password."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Export settings+persona+packs+templates as ONE encrypted bundle.

    The vault itself is NOT included (move secrets separately with
    `forge vault backup`). Import with: forge import-profile
    """
    from forge.profile import export_profile
    from forge.vault.bundle import BundleError
    pw = password or typer.prompt("Bundle password", hide_input=True,
                                  confirmation_prompt=True)
    try:
        dest = export_profile(_cfg(config), out, pw)
    except BundleError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"Profile exported encrypted to {dest}.")
    typer.echo("The bundle password is the only key -- don't lose it.")


@app.command("import-profile")
def import_profile_cmd(
    bundle: str = typer.Argument(...),
    dest: str = typer.Option(".", "--dest"),
    password: Optional[str] = typer.Option(None, "--password"),
):
    """Unpack an exported profile bundle into a folder."""
    from forge.profile import import_profile
    from forge.vault.bundle import BundleError
    pw = password or typer.prompt("Bundle password", hide_input=True,
                                  confirmation_prompt=False)
    try:
        result = import_profile(bundle, dest, pw)
    except BundleError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"Restored {result['count']} files into {dest}:")
    for name in result["restored"]:
        typer.echo(f"  {name}")
    typer.echo("Next: review settings/forge.yaml, move files into place, "
               "then run `forge identity validate`.")


# -- tube sites (manual-assist uploads) ------------------------------------------
tube_app = typer.Typer(help="Tube-site upload packets (manual-assist).",
                       no_args_is_help=True)
app.add_typer(tube_app, name="tube")


@tube_app.command("sites")
def tube_sites():
    """List tube sites and their honest upload capabilities."""
    from forge.tube.sites import capability_rows
    typer.echo(f"{'site':10} {'upload':8} {'verification':14} monetization")
    typer.echo("-" * 70)
    for r in capability_rows():
        typer.echo(f"{r['site']:10} {r['upload']:8} {r['verification']:14} "
                   f"{r['monetization']}")
    typer.echo("\nAll tube sites are MANUAL upload: she posts in the site's "
               "own dashboard. No public upload API exists -- tools claiming "
               "auto-upload get accounts banned.")


@tube_app.command("metadata")
def tube_metadata(
    site: str = typer.Option(..., help="pornhub|xvideos|xnxx|xhamster|redtube|youporn"),
    scene: Optional[str] = typer.Option(None, "--scene", help="Scene YAML file."),
    name: str = typer.Option("", "--name", help="Her display name for titles."),
    tags: str = typer.Option("", "--tags", help="Comma-separated custom tags."),
    template: int = typer.Option(0, "--template", help="Title template 0-3."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Preview title/description/tags for one site (nothing is posted)."""
    import yaml as _yaml
    from forge.pay.links import build_payment_links
    from forge.tube.metadata import generate_metadata
    from forge.tube.sites import get_site
    cfg = _cfg(config)
    scene_data = (_yaml.safe_load(Path(scene).read_text(encoding="utf-8"))
                  if scene else None) or {}
    try:
        tube_site = get_site(site)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    meta = generate_metadata(
        tube_site, scene_data, name=name,
        custom_tags=[t.strip() for t in tags.split(",") if t.strip()],
        links=build_payment_links(cfg), template_idx=template)
    typer.echo(f"TITLE ({len(meta.title)} chars):\n  {meta.title}\n")
    typer.echo(f"DESCRIPTION:\n{meta.description}\n")
    typer.echo(f"TAGS ({len(meta.tags)}/{tube_site.max_tags}): "
               f"{', '.join(meta.tags)}")
    if meta.tags_truncated:
        typer.echo(f"NOTE: {tube_site.name} only takes {tube_site.max_tags} "
                   f"tags -- weakest ones were dropped. Put your strongest "
                   f"tags first in --tags.")


@tube_app.command("packet")
def tube_packet(
    video: str = typer.Option(..., "--video", help="Video file path."),
    site: str = typer.Option(..., help="pornhub|xvideos|xnxx|xhamster|redtube|youporn"),
    scene: Optional[str] = typer.Option(None, "--scene"),
    name: str = typer.Option("", "--name"),
    tags: str = typer.Option("", "--tags"),
    template: int = typer.Option(0, "--template", help="Title template 0-3."),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Build an upload packet (title/description/tags/checklist) for one video."""
    from forge.pay.links import build_payment_links
    from forge.tube.packets import build_packet
    from forge.tube.sites import get_site
    import yaml as _yaml
    cfg = _cfg(config)
    scene_data = (_yaml.safe_load(Path(scene).read_text(encoding="utf-8"))
                  if scene else None) or {}
    try:
        tube_site = get_site(site)
    except KeyError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    out = cfg.get_path("post.packets_dir", "./forge-data/packets")
    dest = build_packet(
        video, tube_site, out, scene=scene_data, name=name,
        custom_tags=[t.strip() for t in tags.split(",") if t.strip()],
        links=build_payment_links(cfg), template_idx=template)
    typer.echo(f"Packet ready at {dest}")
    typer.echo("Copy title/description/tags into the site's upload page, "
               "then publish there.")


@tube_app.command("bulk")
def tube_bulk(
    dir: str = typer.Option(..., "--dir", help="Folder of videos."),
    sites: str = typer.Option("pornhub,xvideos,xnxx,xhamster,redtube,youporn",
                              "--sites", help="Comma-separated site keys."),
    scene: Optional[str] = typer.Option(None, "--scene"),
    name: str = typer.Option("", "--name"),
    tags: str = typer.Option("", "--tags"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Build upload packets for a whole folder of videos across many sites."""
    from forge.pay.links import build_payment_links
    from forge.tube.packets import build_bulk
    import yaml as _yaml
    cfg = _cfg(config)
    scene_data = (_yaml.safe_load(Path(scene).read_text(encoding="utf-8"))
                  if scene else None) or {}
    vids = sorted(str(p) for p in Path(dir).glob("*")
                  if p.suffix.lower() in (".mp4", ".mov", ".webm", ".m4v"))
    if not vids:
        typer.echo(f"No videos found in {dir}", err=True)
        raise typer.Exit(1)
    out = cfg.get_path("post.packets_dir", "./forge-data/packets")
    manifest = build_bulk(
        vids, [s.strip() for s in sites.split(",") if s.strip()], out,
        scene=scene_data, name=name,
        custom_tags=[t.strip() for t in tags.split(",") if t.strip()],
        links=build_payment_links(cfg))
    typer.echo(f"{len(vids)} video(s) x packets ready. Manifest: {manifest}")
    typer.echo("Work through the packets site by site -- she publishes "
               "each one in the site's own dashboard.")


# -- public AI providers (Grok / Gemini / Claude) --------------------------------
ai_app = typer.Typer(help="Public AI helpers (her API keys; drafts only).",
                     no_args_is_help=True)
app.add_typer(ai_app, name="ai")


def _ai_provider(provider: Optional[str], cfg):
    from forge.ai.providers import resolve_provider
    return resolve_provider(provider, cfg)


@ai_app.command("providers")
def ai_providers(config: Optional[str] = typer.Option(None, "--config")):
    """Show AI providers and whether each has a key configured."""
    from forge.ai.providers import provider_status
    for p in provider_status(_cfg(config)):
        mark = "ready" if p["configured"] else "no key"
        typer.echo(f"{p['provider']:8} [{mark}] model={p['model']}")
        if not p["configured"]:
            typer.echo(f"         get a key: {p['docs']}")
    typer.echo("\nSet keys in forge.yaml under ai: (or XAI_API_KEY / "
               "GEMINI_API_KEY / ANTHROPIC_API_KEY).")


@ai_app.command("ask")
def ai_ask(
    prompt: str = typer.Option(..., "--prompt"),
    provider: Optional[str] = typer.Option(None, "--provider",
                                           help="grok|gemini|claude"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Ask the AI anything. Prints the answer (draft, not sent anywhere)."""
    from forge.ai.tasks import ask
    resp = ask(_ai_provider(provider, _cfg(config)), prompt)
    typer.echo(f"[{resp.provider}/{resp.model}]\n{resp.text}")


@ai_app.command("caption")
def ai_caption(
    topic: str = typer.Option(...),
    n: int = typer.Option(3, "--n"),
    tone: str = typer.Option("playful", "--tone"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Write social captions about a topic."""
    from forge.ai.tasks import captions
    resp = captions(_ai_provider(provider, _cfg(config)), topic, n, tone)
    typer.echo(resp.text)


@ai_app.command("titles")
def ai_titles(
    topic: str = typer.Option(...),
    n: int = typer.Option(5, "--n"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Brainstorm video titles."""
    from forge.ai.tasks import titles
    typer.echo(titles(_ai_provider(provider, _cfg(config)), topic, n).text)


@ai_app.command("hashtags")
def ai_hashtags(
    topic: str = typer.Option(...),
    n: int = typer.Option(10, "--n"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Suggest hashtags for a topic."""
    from forge.ai.tasks import hashtags
    typer.echo(hashtags(_ai_provider(provider, _cfg(config)), topic, n).text)


@ai_app.command("ideas")
def ai_ideas(
    niche: str = typer.Option(...),
    n: int = typer.Option(10, "--n"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Brainstorm video content ideas for her niche."""
    from forge.ai.tasks import content_ideas
    typer.echo(content_ideas(_ai_provider(provider, _cfg(config)),
                             niche, n).text)


@ai_app.command("scene-ideas")
def ai_scene_ideas(
    vibe: str = typer.Option(...),
    n: int = typer.Option(5, "--n"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Describe filmable AI-video scene concepts for a vibe."""
    from forge.ai.tasks import scene_ideas
    typer.echo(scene_ideas(_ai_provider(provider, _cfg(config)),
                           vibe, n).text)


@ai_app.command("polish")
def ai_polish(
    text: str = typer.Option(...),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Rewrite her draft punchier, keeping her voice."""
    from forge.ai.tasks import polish
    typer.echo(polish(_ai_provider(provider, _cfg(config)), text).text)


@ai_app.command("reply-assist")
def ai_reply_assist(
    incoming: str = typer.Option(..., "--incoming",
                                 help="The fan's message."),
    context: str = typer.Option("", "--context"),
    platform: Optional[str] = typer.Option(None, "--platform"),
    sender: Optional[str] = typer.Option(None, "--sender"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Draft reply options for a fan message.

    With --platform and --sender, the draft goes into the approval queue;
    otherwise it's just printed.
    """
    from forge.ai.tasks import reply_assist
    cfg = _cfg(config)
    resp = reply_assist(_ai_provider(provider, cfg), incoming, context)
    if platform and sender:
        engine = _load_engine(cfg)
        draft = engine.queue.add(platform=platform, sender=sender,
                                 incoming=incoming, reply=resp.text,
                                 trigger="ai-assist")
        _save_engine_queue(engine)
        typer.echo(f"Draft #{draft.id} queued for approval:")
    typer.echo(resp.text)


@ai_app.command("promo")
def ai_promo(
    item: str = typer.Option(...),
    price: str = typer.Option(...),
    provider: Optional[str] = typer.Option(None, "--provider"),
    config: Optional[str] = typer.Option(None, "--config"),
):
    """Write promo lines for a menu item at her price."""
    from forge.ai.tasks import promo_text
    typer.echo(promo_text(_ai_provider(provider, _cfg(config)),
                          item, price).text)


# -- dashboard ---------------------------------------------------------------
@app.command()
def dashboard(config: Optional[str] = typer.Option(None, "--config"),
              host: str = "127.0.0.1", port: int = 8765):
    """Serve the local dashboard (localhost only)."""
    import uvicorn
    from forge.dashboard.app import create_app
    uvicorn.run(create_app(config), host=host, port=port)


@app.command()
def gui(config: Optional[str] = typer.Option(None, "--config")):
    """Launch the desktop GUI (needs `pip install "creator-forge\\[gui]"`)."""
    from forge.gui import launch
    raise SystemExit(launch(config))


# -- spicy chat (consent-gated) ----------------------------------------------

def _resolve_pack(pack: "str | None", cfg) -> str:
    from forge.identity.pack import resolve_pack_path
    path = resolve_pack_path(pack, cfg)
    if not path:
        raise typer.BadParameter(
            "No identity pack: pass --pack, set one active "
            "(`forge identity use`), or set identity.pack_path.")
    return path


def _spicy_engine(cfg, pack: "str | None"):
    """Build a consent-gated SpicyEngine sharing the main approval queue."""
    from forge.chat.spicy import SpicyEngine, SpicyConsentError
    pack_path = _resolve_pack(pack, cfg)
    engine = _load_engine(cfg)  # shared queue/modes persistence
    try:
        spicy = SpicyEngine.from_pack(
            pack_path, queue=engine.queue, config=cfg,
            heat_path=cfg.get_path("chat.spicy_heat_path",
                                   "./forge-data/chat-spicy-heat.json"))
    except SpicyConsentError as e:
        typer.echo(f"REFUSED: {e}", err=True)
        raise typer.Exit(2)
    return spicy, engine


@chat_app.command("spicy-templates")
def chat_spicy_templates(
    action: str = typer.Argument(..., help="list | add | delete"),
    tier: str = typer.Option("playful", "--tier",
                             help="playful | teasing | explicit"),
    name: str = typer.Option("", "--name"),
    text: str = typer.Option("", "--text"),
    pack: "str | None" = typer.Option(None, "--pack"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Manage spicy reply templates. Consent-gated: the identity pack's
    scope must explicitly cover spicy/adult chat."""
    from forge.chat.spicy import (
        TIERS, add_spicy_template, delete_spicy_template,
        ensure_spicy_defaults, load_spicy_templates, require_spicy_consent,
    )
    require_spicy_consent(_resolve_pack(pack, _cfg(config)))
    ensure_spicy_defaults()
    if action == "list":
        tiers = load_spicy_templates()
        for t in TIERS:
            typer.echo(f"== {t} ==")
            for n, txt in sorted(tiers.get(t, {}).items()):
                typer.echo(f"  [{n}] {txt[:90]}")
    elif action == "add":
        if not name or not text:
            raise typer.BadParameter("add needs --name and --text.")
        add_spicy_template(tier, name, text)
        typer.echo(f"Added [{tier}/{name}].")
    elif action == "delete":
        if not name:
            raise typer.BadParameter("delete needs --name.")
        delete_spicy_template(tier, name)
        typer.echo(f"Deleted [{tier}/{name}].")
    else:
        raise typer.BadParameter("action must be list | add | delete.")


@chat_app.command("spicy-tier")
def chat_spicy_tier(
    platform: str = typer.Option(...),
    sender: str = typer.Option(...),
    tier: str = typer.Option(..., help="playful | teasing | explicit"),
    pack: "str | None" = typer.Option(None, "--pack"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Set the spicy tier ("heat") for one conversation. Only SHE changes
    this -- the bot never escalates on its own."""
    spicy, _ = _spicy_engine(_cfg(config), pack)
    spicy.set_tier(platform, sender, tier)
    typer.echo(f"Spicy tier for ({platform}, {sender}) set to '{tier}'.")


@chat_app.command("spicy-draft")
def chat_spicy_draft(
    platform: str = typer.Option(...),
    sender: str = typer.Option(...),
    text: str = typer.Option(..., help="The fan's incoming message."),
    pack: "str | None" = typer.Option(None, "--pack"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Draft a spicy reply into the approval queue (never auto-approved)."""
    from forge.pay.links import build_payment_links
    cfg = _cfg(config)
    spicy, engine = _spicy_engine(cfg, pack)
    links = build_payment_links(cfg)
    menu = cfg.get_path("pay.tip_menu", []) or []
    draft = spicy.draft(platform=platform, sender=sender, text=text,
                        links=links, menu=menu)
    _save_engine_queue(engine)
    typer.echo(f"Spicy draft #{draft.id} [{draft.trigger}] "
               f"tier={spicy.get_tier(platform, sender)} status={draft.status}:")
    typer.echo(f"  In:  {draft.incoming}")
    typer.echo(f"  Out: {draft.reply}")


# -- media triage ------------------------------------------------------------

def _triage_queue(cfg):
    from forge.chat.triage import TriageQueue, get_classifier
    name = ""
    try:
        name = cfg.get_path("chat.triage.nsfw_classifier", "") or "none"
    except Exception:
        name = "none"
    return TriageQueue(
        cfg.get_path("chat.triage_db", "./forge-data/triage.db"),
        thumbs_dir=cfg.get_path("chat.triage_thumbs_dir",
                                "./forge-data/triage-thumbs"),
        classifier=get_classifier(name or "none"))


@chat_app.command("triage-add")
def chat_triage_add(
    platform: str = typer.Option(...),
    sender: str = typer.Option(...),
    media: str = typer.Option(..., help="Path to the fan-sent image."),
    note: str = typer.Option("", "--note"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Queue a fan-sent pic for her review (blurred thumbnail). Drafts a
    'got your pic' reply into the approval queue -- never auto-sent."""
    from forge.chat.triage import triage_auto_reply_text
    cfg = _cfg(config)
    q = _triage_queue(cfg)
    try:
        item = q.add(platform=platform, sender=sender, media_path=media,
                     note=note)
    finally:
        q.close()
    typer.echo(f"Triage item #{item.id} queued (nsfw: {item.nsfw_label}). "
               f"Blurred thumb: {item.thumb_path}")
    engine = _load_engine(cfg)
    draft = engine.queue.add(
        platform=platform, sender=sender,
        incoming=f"(triage #{item.id}: fan sent a pic)",
        reply=triage_auto_reply_text(cfg), trigger="triage:auto-reply")
    _save_engine_queue(engine)
    typer.echo(f"Auto-reply drafted as #{draft.id} (pending approval).")


@chat_app.command("triage-list")
def chat_triage_list(
    status: str = typer.Option("pending", "--status",
                               help="pending | approved | skipped"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """List triage items awaiting her review."""
    cfg = _cfg(config)
    q = _triage_queue(cfg)
    try:
        items = q.list(status=status)
    finally:
        q.close()
    if not items:
        typer.echo(f"No {status} triage items.")
        return
    for it in items:
        typer.echo(f"#{it.id} [{it.platform}/{it.sender}] {it.status} "
                   f"nsfw={it.nsfw_label} thumb={it.thumb_path}")


@chat_app.command("triage-approve")
def chat_triage_approve(item_id: int = typer.Argument(...),
                        config: "str | None" = typer.Option(None, "--config")):
    """Mark a triage item reviewed-and-fine."""
    q = _triage_queue(_cfg(config))
    try:
        it = q.approve(item_id)
    finally:
        q.close()
    typer.echo(f"Triage item #{it.id} approved.")


@chat_app.command("triage-skip")
def chat_triage_skip(item_id: int = typer.Argument(...),
                     config: "str | None" = typer.Option(None, "--config")):
    """Skip a triage item (she doesn't want to deal with it)."""
    q = _triage_queue(_cfg(config))
    try:
        it = q.skip(item_id)
    finally:
        q.close()
    typer.echo(f"Triage item #{it.id} skipped.")


# -- custom video orders -------------------------------------------------------
orders_app = typer.Typer(help="Custom video order commands.", no_args_is_help=True)
app.add_typer(orders_app, name="orders")


def _order_store(cfg):
    from forge.orders.store import OrderStore
    return OrderStore(cfg.get_path("orders.db_path",
                                   "./forge-data/orders.db"))


def _show_order(order) -> None:
    typer.echo(f"#{order.id} [{order.status}] {order.scene_name} "
               f"for {order.fan_handle} ({order.platform}) "
               f"{order.price_label} {order.price}".rstrip())


@orders_app.command("scenes")
def orders_scenes(pack: "str | None" = typer.Option(None, "--pack"),
                  config: "str | None" = typer.Option(None, "--config")):
    """List scene templates with comfort decisions (what fans may order)."""
    from forge.orders.flow import list_orderable_scenes
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    for s in list_orderable_scenes(cfg, pack_path):
        flag = "ORDERABLE" if s["orderable"] else f"NOT orderable ({s['mode']})"
        typer.echo(f"- {s['name']}: {flag}\n    {s['reason']}")


@orders_app.command("create")
def orders_create(
    fan: str = typer.Option(..., "--fan", help="Fan handle."),
    scene: str = typer.Option(..., "--scene", help="Scene YAML path."),
    pack: "str | None" = typer.Option(None, "--pack"),
    platform: str = typer.Option("", "--platform"),
    price_label: str = typer.Option("", "--price-label"),
    price: str = typer.Option("", "--price"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Create a custom video order (pending_payment). Refused outright if
    the scene hits a comfort boundary."""
    from forge.orders.flow import OrderRefusedError, create_order
    cfg = _cfg(config)
    pack_path = _resolve_pack(pack, cfg)
    store = _order_store(cfg)
    try:
        order = create_order(store, fan_handle=fan, scene_path=scene,
                             pack_path=pack_path, platform=platform,
                             price_label=price_label, price=price)
    except OrderRefusedError as e:
        typer.echo(f"REFUSED: {e}", err=True)
        raise typer.Exit(3)
    finally:
        store.close()
    typer.echo("Order created (pending_payment). Send her payment link, "
               "then `forge orders pay`.")
    _show_order(order)


@orders_app.command("list")
def orders_list(status: "str | None" = typer.Option(None, "--status"),
                config: "str | None" = typer.Option(None, "--config")):
    """List orders, optionally filtered by status."""
    store = _order_store(_cfg(config))
    try:
        orders = store.list(status=status)
    finally:
        store.close()
    if not orders:
        typer.echo("No orders.")
        return
    for o in orders:
        _show_order(o)


def _order_transition(cmd_name: str, to: str, order_id: int, cfg,
                      **fields):
    from forge.orders.flow import (
        cancel_order, deliver_order, mark_paid, refund_order,
        render_order, review_order, OrderRefusedError,
    )
    from forge.video.queue import VideoQueue
    store = _order_store(cfg)
    try:
        if to == "queued":
            order = mark_paid(store, order_id)
        elif to == "rendering":
            pack_path = _resolve_pack(None, cfg)
            queue = VideoQueue(cfg.get_path("video.queue_db",
                                            "./forge-data/video-queue.db"))
            try:
                order = render_order(store, queue, cfg, order_id, pack_path)
            finally:
                queue.close()
        elif to == "awaiting_review":
            queue = VideoQueue(cfg.get_path("video.queue_db",
                                            "./forge-data/video-queue.db"))
            try:
                order = review_order(store, queue, order_id)
            finally:
                queue.close()
        elif to == "delivered":
            order = deliver_order(store, order_id, **fields)
        elif to == "cancelled":
            order = cancel_order(store, order_id, **fields)
        elif to == "refunded":
            order = refund_order(store, order_id)
        else:
            raise AssertionError(to)
    except OrderRefusedError as e:
        typer.echo(f"REFUSED: {e}", err=True)
        raise typer.Exit(3)
    finally:
        store.close()
    typer.echo(f"Order #{order.id} -> {order.status}.")
    _show_order(order)


@orders_app.command("pay")
def orders_pay(order_id: int = typer.Argument(...),
               config: "str | None" = typer.Option(None, "--config")):
    """Confirm payment received: pending_payment -> queued."""
    _order_transition("pay", "queued", order_id, _cfg(config))


@orders_app.command("render")
def orders_render(order_id: int = typer.Argument(...),
                  config: "str | None" = typer.Option(None, "--config")):
    """Enqueue the video job: queued -> rendering."""
    _order_transition("render", "rendering", order_id, _cfg(config))


@orders_app.command("review")
def orders_review(order_id: int = typer.Argument(...),
                  config: "str | None" = typer.Option(None, "--config")):
    """Video job done -> awaiting_review (she looks before delivery)."""
    _order_transition("review", "awaiting_review", order_id, _cfg(config))


@orders_app.command("approve")
def orders_approve(order_id: int = typer.Argument(...),
                   note: str = typer.Option("", "--note"),
                   config: "str | None" = typer.Option(None, "--config")):
    """She reviewed the finished video and approves it: -> delivered."""
    _order_transition("approve", "delivered", order_id, _cfg(config),
                      delivery_note=note)


@orders_app.command("deliver")
def orders_deliver(order_id: int = typer.Argument(...),
                   note: str = typer.Option("", "--note",
                                            help="Where/how it was sent."),
                   config: "str | None" = typer.Option(None, "--config")):
    """Log delivery to the fan: awaiting_review -> delivered."""
    _order_transition("deliver", "delivered", order_id, _cfg(config),
                      delivery_note=note)


@orders_app.command("cancel")
def orders_cancel(order_id: int = typer.Argument(...),
                  reason: str = typer.Option("", "--reason"),
                  config: "str | None" = typer.Option(None, "--config")):
    """Cancel an order."""
    _order_transition("cancel", "cancelled", order_id, _cfg(config),
                      reason=reason)


@orders_app.command("refund")
def orders_refund(order_id: int = typer.Argument(...),
                  config: "str | None" = typer.Option(None, "--config")):
    """Mark a cancelled order refunded."""
    _order_transition("refund", "refunded", order_id, _cfg(config))


# -- live avatar ---------------------------------------------------------------
live_app = typer.Typer(help="Live AI avatar session commands.",
                       no_args_is_help=True)
app.add_typer(live_app, name="live")


def _live_manager(cfg):
    from forge.live.session import LiveSessionManager
    return LiveSessionManager(cfg.get_path("data_dir", "./forge-data"))


@live_app.command("start")
def live_start(
    provider: str = typer.Option(..., "--provider",
                                 help="heygen | did | local-guide"),
    api_key: str = typer.Option("", "--api-key",
                                help="Provider key (or set in forge.yaml)."),
    avatar_id: str = typer.Option("", "--avatar-id"),
    voice_id: str = typer.Option("", "--voice-id"),
    source_image: str = typer.Option("", "--source-image",
                                     help="D-ID source image URL."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Start a live avatar session (real provider APIs; local-guide prints
    the honest OBS setup instead of starting anything)."""
    from forge.live.adapters import LiveNotConfiguredError
    from forge.live.session import local_guide_text
    cfg = _cfg(config)
    if provider == "local-guide":
        typer.echo(local_guide_text())
        return
    mgr = _live_manager(cfg)
    kwargs: dict[str, str] = {}
    if avatar_id:
        kwargs["avatar_id"] = avatar_id
    if voice_id:
        kwargs["voice_id"] = voice_id
    if source_image:
        kwargs["source_image_url"] = source_image
    try:
        session = mgr.start(provider, cfg, api_key=api_key, **kwargs)
    except LiveNotConfiguredError as e:
        typer.echo(f"NOT CONFIGURED: {e}", err=True)
        raise typer.Exit(2)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"Live session started via {session['provider']}.")
    typer.echo(f"  started: {session['started_at']}")
    info = session.get("info", {})
    for k in ("session_id", "id", "url", "note"):
        if info.get(k):
            typer.echo(f"  {k}: {info[k]}")


@live_app.command("stop")
def live_stop(config: "str | None" = typer.Option(None, "--config")):
    """Stop the active live session."""
    result = _live_manager(_cfg(config)).stop(_cfg(config))
    if result.get("stopped"):
        typer.echo("Live session stopped.")
    else:
        typer.echo(result.get("note", "No active live session."))


@live_app.command("status")
def live_status(config: "str | None" = typer.Option(None, "--config")):
    """Show the live session status."""
    import yaml as _yaml
    st = _live_manager(_cfg(config)).status()
    typer.echo(_yaml.safe_dump(st, sort_keys=False))


# -- fan CRM -------------------------------------------------------------------
crm_app = typer.Typer(help="Fan/subscriber CRM commands.",
                      no_args_is_help=True)
app.add_typer(crm_app, name="crm")


def _crm(cfg):
    from forge.crm.store import FanCRM
    return FanCRM(cfg.get_path("crm.db_path", "./forge-data/crm.db"))


@crm_app.command("add")
def crm_add(platform: str = typer.Option(...),
            handle: str = typer.Option(...),
            config: "str | None" = typer.Option(None, "--config")):
    """Add (or fetch) a fan record."""
    c = _crm(_cfg(config))
    fan = c.upsert_fan(platform=platform, handle=handle)
    c.close()
    typer.echo(yaml.safe_dump(fan, sort_keys=False))


@crm_app.command("show")
def crm_show(platform: str = typer.Option(...),
             handle: str = typer.Option(...),
             config: "str | None" = typer.Option(None, "--config")):
    """Show a fan's full profile + buyer-intent score."""
    c = _crm(_cfg(config))
    fan = c.get_fan(platform, handle)
    if not fan:
        typer.echo(f"No fan {handle} on {platform}.", err=True)
        raise typer.Exit(1)
    score = c.buyer_intent(platform, handle)
    c.close()
    typer.echo(yaml.safe_dump({**fan, "buyer_intent": score},
                              sort_keys=False))


@crm_app.command("list")
def crm_list(platform: "str | None" = typer.Option(None, "--platform"),
             status: "str | None" = typer.Option(None, "--status"),
             tag: "str | None" = typer.Option(None, "--tag"),
             config: "str | None" = typer.Option(None, "--config")):
    """List fans (optionally filtered)."""
    c = _crm(_cfg(config))
    for f in c.list_fans(platform=platform, status=status, tag=tag):
        typer.echo(f"{f['platform']:10} {f['handle']:20} "
                   f"${f['total_spend']:.0f} msgs={f['message_count']} "
                   f"[{f['status']}] tags={','.join(f['tags'])}")
    c.close()


@crm_app.command("tag")
def crm_tag(platform: str = typer.Option(...),
            handle: str = typer.Option(...),
            tag: str = typer.Option(...),
            config: "str | None" = typer.Option(None, "--config")):
    """Tag a fan (e.g. whale, online, vip)."""
    c = _crm(_cfg(config))
    fan = c.add_tag(platform, handle, tag)
    c.close()
    typer.echo(f"Tags for {handle}: {','.join(fan['tags'])}")


@crm_app.command("untag")
def crm_untag(platform: str = typer.Option(...),
              handle: str = typer.Option(...),
              tag: str = typer.Option(...),
              config: "str | None" = typer.Option(None, "--config")):
    """Remove a tag from a fan."""
    c = _crm(_cfg(config))
    fan = c.remove_tag(platform, handle, tag)
    c.close()
    typer.echo(f"Tags for {handle}: {','.join(fan['tags'])}")


@crm_app.command("note")
def crm_note(platform: str = typer.Option(...),
             handle: str = typer.Option(...),
             note: str = typer.Option(...),
             config: "str | None" = typer.Option(None, "--config")):
    """Append a timestamped note to a fan."""
    c = _crm(_cfg(config))
    c.add_note(platform, handle, note)
    c.close()
    typer.echo("Note saved.")


@crm_app.command("spend")
def crm_spend(platform: str = typer.Option(...),
              handle: str = typer.Option(...),
              amount: float = typer.Option(...),
              config: "str | None" = typer.Option(None, "--config")):
    """Record a purchase from a fan (updates LTV)."""
    c = _crm(_cfg(config))
    fan = c.record_spend(platform, handle, amount)
    c.close()
    typer.echo(f"{handle}: total spend now ${fan['total_spend']:.2f} "
               f"({fan['purchase_count']} purchases)")


@crm_app.command("message")
def crm_message(platform: str = typer.Option(...),
                handle: str = typer.Option(...),
                config: "str | None" = typer.Option(None, "--config")):
    """Log that a fan sent a message (activity tracking)."""
    c = _crm(_cfg(config))
    c.record_message(platform, handle)
    c.close()
    typer.echo("Logged.")


@crm_app.command("set-status")
def crm_set_status(platform: str = typer.Option(...),
                   handle: str = typer.Option(...),
                   status: str = typer.Option(...,
                                              help="new/active/expired/vip"),
                   config: "str | None" = typer.Option(None, "--config")):
    """Set a fan's status."""
    c = _crm(_cfg(config))
    c.set_status(platform, handle, status)
    c.close()
    typer.echo(f"{handle} -> {status}")


@crm_app.command("score")
def crm_score(platform: str = typer.Option(...),
              handle: str = typer.Option(...),
              config: "str | None" = typer.Option(None, "--config")):
    """Rules-based buyer-intent score for a fan (heuristic, not ML)."""
    c = _crm(_cfg(config))
    s = c.buyer_intent(platform, handle)
    c.close()
    typer.echo(f"Buyer intent: {s['score']}/100 ({s['method']})")
    for r in s["reasons"]:
        typer.echo(f"  + {r}")


@crm_app.command("smart-list")
def crm_smart_list(kind: str = typer.Option(...,
                                           help="whales/new/active/expired/quiet/online"),
                   platform: "str | None" = typer.Option(None, "--platform"),
                   config: "str | None" = typer.Option(None, "--config")):
    """Show a pre-built fan segment."""
    c = _crm(_cfg(config))
    try:
        fans = c.smart_list(kind, platform=platform)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    for f in fans:
        typer.echo(f"{f['platform']:10} {f['handle']:20} "
                   f"${f['total_spend']:.0f}")
    typer.echo(f"{len(fans)} fan(s) in '{kind}'.")
    c.close()


@crm_app.command("import-csv")
def crm_import_csv(csv_path: str = typer.Option(..., "--csv"),
                   config: "str | None" = typer.Option(None, "--config")):
    """Import fans from a CSV YOU exported from each site.

    Columns: platform,handle[,tags,notes,total_spend,status].
    Tags are ';'-separated.
    """
    c = _crm(_cfg(config))
    n = c.import_csv(csv_path)
    c.close()
    typer.echo(f"Imported {n} fan(s).")


@crm_app.command("stats")
def crm_stats(platform: "str | None" = typer.Option(None, "--platform"),
              config: "str | None" = typer.Option(None, "--config")):
    """Per-fan reply/spend stats for her own review."""
    c = _crm(_cfg(config))
    for s in c.conversation_stats(platform=platform):
        typer.echo(f"{s['platform']:10} {s['handle']:20} "
                   f"msgs={s['messages']} buys={s['purchases']} "
                   f"${s['total_spend']:.0f} [{s['status']}]")
    c.close()


# -- spicy livestreaming -------------------------------------------------------
stream_app = typer.Typer(help="Spicy livestream (AFK avatar) commands.",
                         no_args_is_help=True)
app.add_typer(stream_app, name="stream")


def _stream_mgr(cfg):
    from forge.stream.session import StreamSessionManager
    return StreamSessionManager(cfg.get_path("data_dir", "./forge-data"))


@stream_app.command("platforms")
def stream_platforms():
    """Show the honest per-platform streaming capability matrix."""
    from forge.stream.platforms import list_platforms
    for p in list_platforms():
        typer.echo(f"\n== {p['label']} [{p['key']}] ==")
        typer.echo(f"   RTMP ingest: {'yes' if p['rtmp_ingest'] else 'no'}"
                   f" -- {p['rtmp_notes']}")
        typer.echo(f"   Chat API: {p['chat_api']} -- {p['chat_notes']}")
        typer.echo(f"   Verification: {p['verification']}")
        typer.echo(f"   ToS risk (AFK avatar): {p['tos_risk']}")
        typer.echo(f"   Payout: {p['payout_notes']}")
    typer.echo("\nDetails: docs/STREAMING.md. Verify on each platform's "
               "broadcaster pages before going live.")


@stream_app.command("setup")
def stream_setup(platform: str = typer.Option(...),
                 config: "str | None" = typer.Option(None, "--config")):
    """Print the setup steps for one platform (key, RTMP, OBS)."""
    from forge.stream.platforms import get_platform
    cfg = _cfg(config)
    try:
        p = get_platform(platform)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    key = p["key"]
    has_rtmp = bool(cfg.get_path(f"stream.{key}_rtmp", ""))
    has_key = bool(cfg.get_path(f"stream.{key}_key", ""))
    typer.echo(f"Setup for {p['label']}:")
    typer.echo(f"  1. Get verified as a broadcaster ({p['verification']}).")
    typer.echo(f"  2. Copy the RTMP URL + stream key from the broadcaster "
               f"dashboard.")
    typer.echo(f"  3. Set stream.{key}_rtmp "
               f"({'set' if has_rtmp else 'MISSING'}) and "
               f"stream.{key}_key ({'set' if has_key else 'MISSING'}) "
               f"in forge.yaml.")
    typer.echo(f"  4. OBS: Settings -> Stream -> Custom, paste server + key.")
    typer.echo(f"  5. {p['rtmp_notes']}")
    typer.echo(f"  Risk: {p['tos_risk']}")


@stream_app.command("go-live")
def stream_go_live(
    platform: str = typer.Option(...),
    avatar: str = typer.Option("loop",
                               help="loop | sadtalker | heygen | did"),
    avatar_source: str = typer.Option(
        "", "--avatar-source",
        help="Video file (loop) or portrait image (sadtalker)."),
    i_understand_the_risk: bool = typer.Option(
        False, "--i-understand-the-risk",
        help="Confirm you read the ToS risk note."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Start an AFK stream session (avatar -> OBS -> RTMP).

    CreatorForge does NOT stream to the platform itself: OBS does the
    RTMP ingest with YOUR stream key. This tracks the session and
    drives the avatar side. Most cam sites expect a live verified
    performer -- AFK avatar streaming can get the account banned.
    """
    from forge.stream.platforms import get_platform
    from forge.stream.session import StreamNotConfiguredError
    cfg = _cfg(config)
    try:
        p = get_platform(platform)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    if not i_understand_the_risk:
        typer.echo("ToS RISK -- read this first:", err=True)
        typer.echo(f"  {p['tos_risk']}", err=True)
        typer.echo("Re-run with --i-understand-the-risk to confirm.",
                   err=True)
        raise typer.Exit(2)
    mgr = _stream_mgr(cfg)
    try:
        session = mgr.go_live(platform=platform, config=cfg, avatar=avatar,
                              avatar_source=avatar_source,
                              acknowledged_risk=True)
    except (StreamNotConfiguredError, RuntimeError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"AFK stream session started on {session['platform_label']}.")
    typer.echo(f"Avatar mode: {avatar}. Chat: {session['chat_mode']}.")
    typer.echo("Checklist:")
    for step in session["checklist"]:
        typer.echo(f"  - {step}")


@stream_app.command("stop")
def stream_stop(config: "str | None" = typer.Option(None, "--config")):
    """Stop the active AFK stream session."""
    result = _stream_mgr(_cfg(config)).stop()
    typer.echo(result.get("note", "No active stream session."))


@stream_app.command("status")
def stream_status(config: "str | None" = typer.Option(None, "--config")):
    """Show the AFK stream session status."""
    st = _stream_mgr(_cfg(config)).status()
    typer.echo(yaml.safe_dump(st, sort_keys=False))


# -- content ideas ---------------------------------------------------------------
content_app = typer.Typer(help="Content idea generator commands.",
                          no_args_is_help=True)
app.add_typer(content_app, name="content")


@content_app.command("ideas")
def content_ideas(
    count: int = typer.Option(10, "--count"),
    seed: str = typer.Option("forge", "--seed",
                             help="Change for a fresh batch."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Generate post ideas from her catalog tags + templates.

    Template remix of HER material -- not generative AI. She picks and
    rewrites what she likes.
    """
    from forge.content.ideas import catalog_tags_for_ideas, generate_ideas
    cfg = _cfg(config)
    store = CatalogStore(cfg.get_path("catalog.db_path",
                                      "./forge-data/catalog.db"))
    items = store.list(limit=500)
    store.close()
    tags = catalog_tags_for_ideas(items)
    ideas = generate_ideas(catalog_tags=tags, count=count, seed_salt=seed)
    for i, idea in enumerate(ideas, 1):
        typer.echo(f"\n{i}. [{idea['angle']}] {idea['caption']}")
        typer.echo(f"   {idea['hashtags']}")
    typer.echo(f"\n({ideas[0]['method']})" if ideas else "")


# -- chat: PPV / flows / humanizer / compliance -----------------------------------
@chat_app.command("ppv")
def chat_ppv(platform: str = typer.Option(...),
             sender: str = typer.Option(...),
             text: str = typer.Option(..., help="The fan's message."),
             config: "str | None" = typer.Option(None, "--config")):
    """Draft a PPV upsell offer if the message shows buying intent.

    Goes to the approval queue like everything else -- never auto-sends.
    """
    from forge.chat.ppv import ppv_offer_text
    cfg = _cfg(config)
    engine = _load_engine(cfg)
    price_menu = cfg.get_path("orders.price_menu") or \
        cfg.get_path("pay.tip_menu", []) or []
    offer = ppv_offer_text(fan_message=text, price_menu=price_menu,
                           pay_links=build_payment_links(cfg),
                           sender=sender)
    if not offer:
        typer.echo("No buying intent detected -- no offer drafted.")
        return
    draft = engine.queue.add(platform=platform, sender=sender,
                             incoming=text, reply=offer, trigger="ppv")
    _save_engine_queue(engine)
    typer.echo(f"PPV draft #{draft.id} queued for approval:")
    typer.echo(f"  {offer}")


@chat_app.command("flows")
def chat_flows(
    action: str = typer.Option(..., "--action",
                               help="enroll | run | pending | cancel | list"),
    flow: str = typer.Option("", "--flow",
                             help="welcome | winback | nudge"),
    platform: str = typer.Option("", "--platform"),
    handle: str = typer.Option("", "--handle",
                               help="Fan handle."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Welcome / win-back / online-nudge message flows.

    `run` drafts due steps into the approval queue -- nothing auto-sends.
    """
    from forge.chat.flows import FlowRunner, run_due
    cfg = _cfg(config)
    runner = FlowRunner(cfg.get_path("chat.flows_db",
                                     "./forge-data/chat-flows.db"))
    if action == "list":
        typer.echo("Available flows: "
                   + ", ".join(sorted(runner.flows)))
        for name, steps in runner.flows.items():
            typer.echo(f"\n{name}:")
            for s in steps:
                typer.echo(f"  +{s['delay_hours']}h: {s['template'][:60]}")
    elif action == "enroll":
        if not flow or not platform or not handle:
            typer.echo("--flow, --platform and --handle are required.",
                       err=True)
            raise typer.Exit(1)
        typer.echo(yaml.safe_dump(
            runner.enroll(flow, platform, handle), sort_keys=False))
    elif action == "run":
        engine = _load_engine(cfg)
        drafts = run_due(runner, engine)
        _save_engine_queue(engine)
        typer.echo(f"Drafted {len(drafts)} due flow step(s) for approval.")
    elif action == "pending":
        for r in runner.pending():
            typer.echo(f"{r['flow']:8} {r['platform']:10} {r['handle']:20} "
                       f"step {r['step_idx'] + 1} due {r['due_at']}")
    elif action == "cancel":
        if not flow or not platform or not handle:
            typer.echo("--flow, --platform and --handle are required.",
                       err=True)
            raise typer.Exit(1)
        runner.cancel(flow, platform, handle)
        typer.echo("Cancelled.")
    else:
        typer.echo(f"Unknown action {action!r}.", err=True)
        raise typer.Exit(1)
    runner.close()


@chat_app.command("humanize")
def chat_humanize(
    text: str = typer.Option(..., "--text"),
    typo: float = typer.Option(0.15, "--typo",
                               help="Typo intensity 0.0-1.0."),
    lowercase: bool = typer.Option(False, "--lowercase"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Preview the humanizer on a draft (typo simulation + tone fix)."""
    from forge.chat.humanize import humanize
    cfg = _cfg(config)
    hcfg = dict(cfg.get_path("chat.humanize", {}) or {})
    hcfg.update({"enabled": True, "typo_intensity": typo,
                 "lowercase": lowercase})
    typer.echo(humanize(text, hcfg))


@chat_app.command("check")
def chat_check(
    text: str = typer.Option(..., "--text"),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Run the compliance checker on a draft (her wordlists)."""
    from forge.chat.compliance import check_draft_text
    cfg = _cfg(config)
    findings = check_draft_text(
        text, cfg.get_path("chat.compliance", {}) or {})
    if not findings:
        typer.echo("Clean -- no compliance flags.")
        return
    for f in findings:
        typer.echo(f"[{f['category']}] {f['match']}: {f['detail']}")


@chat_app.command("translate")
def chat_translate(
    text: str = typer.Option(..., "--text"),
    target: str = typer.Option(..., "--target",
                               help="Language code, e.g. es, de."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Translate a draft via her LibreTranslate-compatible endpoint.

    Basic machine translation -- review anything important.
    """
    from forge.chat.humanize import TranslationNotConfigured, translate
    cfg = _cfg(config)
    endpoint = str(cfg.get_path("chat.humanize.translate_endpoint", "")
                   or "")
    try:
        typer.echo(translate(text, target, endpoint))
    except TranslationNotConfigured as e:
        typer.echo(f"NOT CONFIGURED: {e}", err=True)
        raise typer.Exit(2)


# -- post: mass DM -------------------------------------------------------------------
@post_app.command("massdm")
def post_massdm(
    message: str = typer.Option(..., "--message",
                                help="Template; {handle}/{first}/{spend}."),
    platform: str = typer.Option(...,
                                 help="Target platform for the packet."),
    fan_list: str = typer.Option(..., "--list",
                                 help="Smart list: whales/new/active/expired/quiet/online"),
    exclude_recent: bool = typer.Option(True, "--exclude-recent/--include-recent",
                                        help="Skip fans chatted in last 48h."),
    live: bool = typer.Option(False, "--live",
                              help="Write the packet. Default is dry-run."),
    schedule: str = typer.Option("", "--schedule",
                                 help="Also schedule a reminder, e.g. 2026-10-10T19:00."),
    config: "str | None" = typer.Option(None, "--config"),
):
    """Build a smart mass-DM packet (manual-assist where no messaging API).

    Dry-run by default: shows who would get it. --live writes the packet
    with per-fan messages + checklist. Platforms without a messaging API
    (OnlyFans/Fansly/Snapchat) are ALWAYS manual copy/paste.
    """
    from forge.post.massdm import build_mass_dm
    cfg = _cfg(config)
    crm = _crm(cfg)
    try:
        fans = crm.smart_list(fan_list, platform=platform)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    crm.close()
    out_dir = cfg.get_path("post.packets_dir", "./forge-data/packets")
    manifest = build_mass_dm(
        message_template=message, fans=fans, platform=platform,
        out_dir=out_dir, exclude_recently_chatted=exclude_recent,
        dry_run=not live)
    typer.echo(yaml.safe_dump(manifest, sort_keys=False))
    if live and schedule:
        from forge.post.schedule import Scheduler
        s = Scheduler(cfg.get_path("post.schedule_db",
                                   "./forge-data/schedule.db"))
        entry = s.schedule(platform=platform, media_path="",
                           caption=f"MASS-DM: {manifest['packet_dir']}",
                           when=schedule,
                           title=f"Mass-DM to {fan_list} ({platform})")
        s.close()
        typer.echo(f"Reminder scheduled: {entry['when']}")


# -- analytics: LTV + peak times -------------------------------------------------------
@analytics_app.command("ltv")
def analytics_ltv(config: "str | None" = typer.Option(None, "--config")):
    """LTV/ARPU from recorded earnings + CRM fan count (honest inputs)."""
    from forge.analytics.insights import ltv_arpu, plain_english_summary
    from forge.analytics.store import AnalyticsStore
    cfg = _cfg(config)
    astore = AnalyticsStore(cfg.get_path("analytics.db_path",
                                         "./forge-data/analytics.db"))
    totals = astore.totals()
    astore.close()
    crm = _crm(cfg)
    fans = crm.list_fans(limit=100000)
    spends = [f["total_spend"] for f in fans]
    crm.close()
    ltv = ltv_arpu(total_earnings=totals["total_earnings"],
                   fan_count=len(fans), fan_spends=spends)
    peaks = analytics_peak_times_list(cfg)
    typer.echo(yaml.safe_dump(ltv, sort_keys=False))
    typer.echo()
    typer.echo(plain_english_summary(totals=totals, ltv=ltv, peaks=peaks))


def analytics_peak_times_list(cfg) -> list:
    from forge.analytics.insights import peak_posting_times
    from forge.analytics.store import AnalyticsStore
    astore = AnalyticsStore(cfg.get_path("analytics.db_path",
                                         "./forge-data/analytics.db"))
    stats = astore.post_stats(limit=1000)
    astore.close()
    return peak_posting_times(stats)


@analytics_app.command("peak-times")
def analytics_peak_times(config: "str | None" = typer.Option(None, "--config")):
    """Best posting slots from HER recorded post stats."""
    peaks = analytics_peak_times_list(_cfg(config))
    for p in peaks:
        typer.echo(f"{p['weekday']:3} {p['hour']:02d}:00  "
                   f"avg engagement {p['avg_engagement']} "
                   f"({p['posts']} posts)")
    if peaks:
        typer.echo(f"Note: {peaks[0]['note']}")


# -- vault: labels + sent log ------------------------------------------------------------
@vault_app.command("label")
def vault_label_cmd(path: str = typer.Argument("./forge-data/vault"),
                    name: str = typer.Option(..., "--name",
                                             help="Blob name in the vault."),
                    labels: str = typer.Option(..., "--labels",
                                               help="Comma-separated labels."),
                    password: "str | None" = typer.Option(None, "--password")):
    """Set labels on a vault blob (encrypted, searchable)."""
    v = _open_vault(path, password)
    result = v.set_labels(name, [l.strip() for l in labels.split(",")])
    typer.echo(f"Labels for '{name}': {', '.join(result)}")


@vault_app.command("labels")
def vault_labels_cmd(path: str = typer.Argument("./forge-data/vault"),
                     name: str = typer.Option(..., "--name"),
                     password: "str | None" = typer.Option(None, "--password")):
    """Show a blob's labels."""
    v = _open_vault(path, password)
    typer.echo(", ".join(v.get_labels(name)) or "(no labels)")


@vault_app.command("find-label")
def vault_find_label_cmd(path: str = typer.Argument("./forge-data/vault"),
                         label: str = typer.Option(..., "--label"),
                         password: "str | None" = typer.Option(None, "--password")):
    """List blobs with a label."""
    v = _open_vault(path, password)
    for b in v.blobs_by_label(label):
        typer.echo(b)


@vault_app.command("search")
def vault_search_cmd(path: str = typer.Argument("./forge-data/vault"),
                     query: str = typer.Option(..., "--query"),
                     password: "str | None" = typer.Option(None, "--password")):
    """Search vault blob names + labels."""
    v = _open_vault(path, password)
    for hit in v.search(query):
        typer.echo(f"{hit['blob']}  [{', '.join(hit['labels'])}]")


@vault_app.command("sent")
def vault_sent_cmd(path: str = typer.Argument("./forge-data/vault"),
                   name: str = typer.Option(..., "--name",
                                            help="Blob that was sent."),
                   fan: str = typer.Option(..., "--fan",
                                           help="Fan handle it went to."),
                   password: "str | None" = typer.Option(None, "--password")):
    """Log that a blob was sent to a fan (no-resend guard)."""
    v = _open_vault(path, password)
    fans = v.log_sent(name, fan)
    typer.echo(f"'{name}' sent to: {', '.join(fans)}")


@vault_app.command("sent-log")
def vault_sent_log_cmd(path: str = typer.Argument("./forge-data/vault"),
                       name: str = typer.Option(..., "--name"),
                       password: "str | None" = typer.Option(None, "--password")):
    """Show who already got a blob."""
    v = _open_vault(path, password)
    fans = v.sent_to(name)
    typer.echo(", ".join(fans) if fans else "(nobody yet)")


@vault_app.command("check-sent")
def vault_check_sent_cmd(path: str = typer.Argument("./forge-data/vault"),
                         name: str = typer.Option(..., "--name"),
                         fan: str = typer.Option(..., "--fan"),
                         password: "str | None" = typer.Option(None, "--password")):
    """Check whether a fan already got a blob (avoid double-sending PPV)."""
    v = _open_vault(path, password)
    if v.already_sent(name, fan):
        typer.echo(f"YES -- {fan} already got '{name}'. Don't resend.")
    else:
        typer.echo(f"No -- {fan} hasn't gotten '{name}' yet.")


if __name__ == "__main__":
    app()
