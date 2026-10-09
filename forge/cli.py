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

app = typer.Typer(help="CreatorForge: AI creator-assistant toolkit.",
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
    pack_path = pack or cfg.get_path("identity.pack_path")
    if not pack_path:
        raise typer.BadParameter("No identity pack: pass --pack or set "
                                 "identity.pack_path in forge.yaml.")
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
    engine = RuleEngine(Persona.from_dict(pdata.get("persona", pdata)),
                        triggers)
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
    pack_path = pack or cfg.get_path("identity.pack_path")
    if not pack_path:
        raise typer.BadParameter("No identity pack: pass --pack or configure it.")
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
    pack_path = pack or cfg.get_path("identity.pack_path")
    vid = voice_id or cfg.get_path("persona.elevenlabs_voice_id")
    if not pack_path:
        raise typer.BadParameter("No identity pack: pass --pack or configure it.")
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
    pack_path = pack or cfg.get_path("identity.pack_path")
    if not pack_path:
        raise typer.BadParameter("No identity pack: pass --pack or configure it.")
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


# -- dashboard ---------------------------------------------------------------
@app.command()
def dashboard(config: Optional[str] = typer.Option(None, "--config"),
              host: str = "127.0.0.1", port: int = 8765):
    """Serve the local dashboard (localhost only)."""
    import uvicorn
    from forge.dashboard.app import create_app
    uvicorn.run(create_app(config), host=host, port=port)


if __name__ == "__main__":
    app()
