"""GUI screens. Each screen is a QWidget that calls the existing
backend modules directly (Python imports, never subprocess).

Every backend call is wrapped so failures show a friendly message box,
never a traceback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from forge.config import ForgeConfig
from forge.gui import widgets as W


def _data_dir(config: ForgeConfig) -> Path:
    return Path(config.get_path("data_dir", "./forge-data"))


def _wrap(fn):
    """Decorator: run a refresh/handler, show friendly errors."""

    def inner(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except Exception as e:  # noqa: BLE001 - GUI boundary
            W.show_error(self, "Something went wrong", str(e) or repr(e))
            return None

    return inner


class _Base(QWidget):
    def __init__(self, config: ForgeConfig):
        super().__init__()
        self.config = config
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(10)

    def title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Title")
        self.layout.addWidget(lbl)
        return lbl

    def hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Dim")
        lbl.setWordWrap(True)
        self.layout.addWidget(lbl)
        return lbl


# -- Catalog -----------------------------------------------------------------
class CatalogScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Catalog")
        self.hint("Your content library. Search it, or scan a new folder in.")
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.kind = QComboBox()
        self.kind.addItems(["all", "image", "video"])
        go = QPushButton("Search")
        go.clicked.connect(self.refresh)
        scan = QPushButton("Scan folder…")
        scan.setObjectName("Ghost")
        scan.clicked.connect(self.scan_folder)
        row.addWidget(self.search, 3)
        row.addWidget(self.kind, 1)
        row.addWidget(go)
        row.addWidget(scan)
        self.layout.addLayout(row)
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.catalog.store import CatalogStore
        q = self.search.text().strip()
        kind = self.kind.currentText()
        store = CatalogStore(self.config.get_path("catalog.db_path",
                                                  "./forge-data/catalog.db"))
        try:
            items = (store.search(q) if q
                     else store.list(kind=None if kind == "all" else kind))
        finally:
            store.close()
        rows = [[i["id"], i["kind"], i["path"],
                 ",".join(i.get("tags", []))] for i in items[:500]]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(
            W.make_table(["ID", "Kind", "Path", "Tags"], rows))
        lbl = QLabel(f"{len(items)} item(s)" + (" (showing 500)" if len(items) > 500 else ""))
        lbl.setObjectName("Dim")
        self.table_holder.addWidget(lbl)

    @_wrap
    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder of media to scan")
        if not folder:
            return
        from forge.catalog.scanner import scan_directory
        from forge.catalog.store import CatalogStore
        store = CatalogStore(self.config.get_path("catalog.db_path",
                                                  "./forge-data/catalog.db"))
        try:
            result = scan_directory(folder, store)
        finally:
            store.close()
        W.show_info(self, "Scan complete",
                    f"Added {result['added']}, {result['skipped_duplicates']} "
                    f"duplicates skipped.")
        self.refresh()


# -- Identity ------------------------------------------------------------------
class IdentityScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Identity & consent")
        self.hint("Video, voice, and style features REFUSE to run without a "
                  "valid signed consent pack. One pack per persona; switch "
                  "the active one below.")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        row = QHBoxLayout()
        use_btn = QPushButton("Make selected active")
        use_btn.clicked.connect(self.make_active)
        newv = QPushButton("New version of selected")
        newv.setObjectName("Ghost")
        newv.clicked.connect(self.new_version)
        row.addWidget(use_btn)
        row.addWidget(newv)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.identity.pack import (
            InvalidConsentError,
            consent_summary,
            get_active_pack,
            list_packs,
            load_identity_pack,
            resolve_pack_path,
            validate_identity_pack,
        )
        data_dir = _data_dir(self.config)
        packs_dir = self.config.get_path("identity.packs_dir", "./identity-packs")
        packs = list_packs(packs_dir)
        legacy = self.config.get_path("identity.pack_path")
        if legacy and Path(legacy).is_file() and not any(
                p["path"] == str(Path(legacy)) for p in packs):
            packs.append({"path": str(Path(legacy)), "name": "(legacy pack)",
                          "version": 1, "status": "valid"})
        active = resolve_pack_path(None, self.config, data_dir)
        if active:
            try:
                pack = validate_identity_pack(load_identity_pack(active))
                self.status.setText("✅ Active: " + consent_summary(pack))
            except InvalidConsentError as e:
                self.status.setText(f"❌ Active pack INVALID: {e}")
        else:
            self.status.setText("⚠️ No active pack. Create one with "
                                "`forge identity create`.")
        rows = []
        self._paths = []
        for p in packs:
            marker = "  ✓" if active and Path(p["path"]) == Path(active) else ""
            rows.append([p["name"], p["version"], p["status"], marker])
            self._paths.append(p["path"])
        W.clear_layout(self.table_holder)
        self._table = W.make_table(["Persona", "Ver", "Status", "Active"], rows)
        self.table_holder.addWidget(self._table)

    def _selected_path(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select a pack first.")
            return None
        return self._paths[rows[0].row()]

    @_wrap
    def make_active(self):
        from forge.identity.pack import set_active_pack
        path = self._selected_path()
        if not path:
            return
        set_active_pack(path, _data_dir(self.config))
        W.show_info(self, "Active persona", f"Now using:\n{path}")
        self.refresh()

    @_wrap
    def new_version(self):
        from forge.identity.pack import bump_pack_version
        path = self._selected_path()
        if not path:
            return
        dest = bump_pack_version(path, notes="created from desktop GUI")
        W.show_info(self, "New version", f"Written to:\n{dest}")
        self.refresh()


# -- Video ---------------------------------------------------------------------
class VideoScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Video")
        self.hint("Consent-gated: generation refuses to run without a valid "
                  "identity pack. Backends (Replicate / ComfyUI) need your "
                  "own keys -- see docs/VIDEO.md.")
        form = QFormLayout()
        self.prompt = QTextEdit()
        self.prompt.setPlaceholderText("Describe the video…")
        self.prompt.setMaximumHeight(90)
        self.adapter = QComboBox()
        self.adapter.addItems(["(config default)", "replicate", "comfyui"])
        self.duration = QSpinBox()
        self.duration.setRange(1, 60)
        self.duration.setValue(5)
        form.addRow("Prompt:", self.prompt)
        form.addRow("Adapter:", self.adapter)
        form.addRow("Duration (s):", self.duration)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        gen = QPushButton("Generate video")
        gen.clicked.connect(self.generate)
        scene_btn = QPushButton("Run a scene file…")
        scene_btn.setObjectName("Ghost")
        scene_btn.clicked.connect(self.run_scene)
        row.addWidget(gen)
        row.addWidget(scene_btn)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Results and refusal messages appear here.")
        self.layout.addWidget(self.output, 1)

    def _pack_or_warn(self) -> str | None:
        from forge.identity.pack import resolve_pack_path
        pack = resolve_pack_path(None, self.config, _data_dir(self.config))
        if not pack:
            W.show_error(self, "No identity pack",
                         "Set an active persona first (Identity tab) or run "
                         "`forge identity create`.")
            return None
        return pack

    @_wrap
    def generate(self):
        from forge.video.adapters import NotConfiguredError
        from forge.video.pipeline import ConsentGateError, generate_video
        pack = self._pack_or_warn()
        if not pack:
            return
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            W.show_error(self, "Empty prompt", "Describe the video first.")
            return
        adapter = self.adapter.currentText()
        adapter = None if adapter.startswith("(") else adapter
        self.output.setPlainText("Working…")
        try:
            result = generate_video(
                config=self.config, identity_pack_path=pack, prompt=prompt,
                adapter_name=adapter, duration_s=self.duration.value())
        except ConsentGateError as e:
            self.output.setPlainText(f"🛑 REFUSED (consent gate):\n{e}")
            return
        except NotConfiguredError as e:
            self.output.setPlainText(f"⚙️ Backend not configured:\n{e}")
            return
        self.output.setPlainText("Done. Outputs:\n" + "\n".join(result.outputs))

    @_wrap
    def run_scene(self):
        from forge.video.pipeline import SceneRefused, generate_scene_video
        from forge.video.scenes import SceneRefusedError
        path, _ = QFileDialog.getOpenFileName(
            self, "Scene YAML file", "", "YAML (*.yaml *.yml)")
        if not path:
            return
        pack = self._pack_or_warn()
        if not pack:
            return
        self.output.setPlainText("Resolving scene against comfort boundary…")
        try:
            result = generate_scene_video(
                config=self.config, identity_pack_path=pack, scene_path=path)
        except (SceneRefusedError, SceneRefused) as e:
            self.output.setPlainText(f"🛑 Scene refused:\n{e}")
            return
        import json
        self.output.setPlainText(json.dumps(result, indent=2, default=str))


# -- Persona -------------------------------------------------------------------
class PersonaScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Persona trainers")
        self.hint("Real ways to train her face/persona model. Each needs her "
                  "data plus a GPU or a paid API key -- pick what fits, then "
                  "follow its setup steps (shown in the terminal with "
                  "`forge persona trainers`).")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.persona.trainers import list_trainers
        rows = [[t.name, t.kind, ", ".join(t.needs), t.cost_notes]
                for t in list_trainers()]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(
            ["Trainer", "Kind", "Needs", "Cost notes"], rows))
        note = QLabel("Voice cloning lives in the terminal for now:\n"
                      "forge persona voice-clone / voice-speak "
                      "(ElevenLabs key + consent-gated).")
        note.setObjectName("Dim")
        note.setWordWrap(True)
        self.table_holder.addWidget(note)


# -- Chat ----------------------------------------------------------------------
def _load_chat_engine(config: ForgeConfig):
    import yaml
    from forge.chat.engine import (Persona, RuleEngine, Trigger,
                                   build_tip_menu_trigger)
    pdata: dict = {}
    persona_path = config.get_path("chat.persona_path")
    if persona_path and Path(persona_path).is_file():
        with open(persona_path, encoding="utf-8") as fh:
            pdata = yaml.safe_load(fh) or {}
    triggers = [Trigger(**t) for t in pdata.get("triggers", [])]
    tip = build_tip_menu_trigger(config)
    if tip is not None:
        triggers.append(tip)
    engine = RuleEngine(Persona.from_dict(pdata.get("persona", pdata)),
                        triggers)
    engine.escalation_config = config
    data = _data_dir(config)
    engine.load_modes(data / "chat-modes.json")
    engine.queue.load(data / "chat-queue.json")
    return engine


def _save_chat_engine(config: ForgeConfig, engine) -> None:
    data = _data_dir(config)
    engine.save_modes(data / "chat-modes.json")
    engine.queue.save(data / "chat-queue.json")


class ChatScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Chat approval queue")
        self.hint("Nothing sends itself. Approve a draft, send the reply "
                  "yourself in the platform's app, then mark it sent. "
                  "⚠ flagged drafts need your eyes first.")
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        btns = QHBoxLayout()
        approve = QPushButton("Approve selected")
        approve.clicked.connect(lambda: self._decide("approve"))
        reject = QPushButton("Reject selected")
        reject.setObjectName("Danger")
        reject.clicked.connect(lambda: self._decide("reject"))
        sent = QPushButton("Mark selected sent")
        sent.setObjectName("Ghost")
        sent.clicked.connect(lambda: self._decide("sent"))
        btns.addWidget(approve)
        btns.addWidget(reject)
        btns.addWidget(sent)
        btns.addStretch(1)
        self.layout.addLayout(btns)
        self.refresh()

    @_wrap
    def refresh(self):
        engine = _load_chat_engine(self.config)
        pending = engine.queue.pending()
        rows = []
        self._ids = []
        for d in pending:
            flag = "⚠ " + ",".join(d.escalation_categories) if d.escalated else ""
            rows.append([d.id, d.platform, d.sender, flag,
                         (d.incoming[:60] + "…") if len(d.incoming) > 60 else d.incoming,
                         (d.reply[:80] + "…") if len(d.reply) > 80 else d.reply])
            self._ids.append(d.id)
        W.clear_layout(self.table_holder)
        self._table = W.make_table(
            ["ID", "Platform", "From", "Flag", "Incoming", "Draft reply"], rows)
        self.table_holder.addWidget(self._table)
        if not pending:
            lbl = QLabel("No pending drafts. You're all caught up. 💕")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)

    def _selected_id(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select a draft first.")
            return None
        return self._ids[rows[0].row()]

    @_wrap
    def _decide(self, action: str):
        draft_id = self._selected_id()
        if draft_id is None:
            return
        engine = _load_chat_engine(self.config)
        if action == "approve":
            engine.queue.approve(draft_id)
        elif action == "reject":
            if not W.confirm(self, "Reject draft",
                             f"Reject draft #{draft_id}?"):
                return
            engine.queue.reject(draft_id)
        else:
            engine.queue.mark_sent(draft_id)
        _save_chat_engine(self.config, engine)
        if action == "sent":
            W.show_info(self, "Logged", f"Draft #{draft_id} marked as sent.")
        self.refresh()


# -- Post & Schedule -------------------------------------------------------------
def _packet_rows(config: ForgeConfig) -> list[list[str]]:
    import yaml
    packets_dir = Path(config.get_path("post.packets_dir",
                                       "./forge-data/packets"))
    rows = []
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
            rows.append([child.name, str(meta.get("platform", "?")),
                         str(meta.get("title", "")),
                         str(meta.get("status", "ready"))])
    return rows


class PostScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Posting packets")
        self.hint("Manual-assist packets for Snapchat / OnlyFans / TikTok -- "
                  "they have no posting API, so you do the final tap in the "
                  "app. Build packets in the terminal: `forge post packet`.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.refresh()

    @_wrap
    def refresh(self):
        W.clear_layout(self.table_holder)
        rows = _packet_rows(self.config)
        self.table_holder.addWidget(W.make_table(
            ["Packet", "Platform", "Title", "Status"], rows))
        if not rows:
            lbl = QLabel("No packets yet.")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)


class ScheduleScreen2(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Schedule")
        self.hint("Reminders, not auto-posting: when something is due, post "
                  "it yourself in the app, then mark it done here.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        done = QPushButton("Mark selected done")
        done.clicked.connect(lambda: self._mark("done"))
        skip = QPushButton("Skip selected")
        skip.setObjectName("Danger")
        skip.clicked.connect(lambda: self._mark("skipped"))
        row.addWidget(refresh)
        row.addWidget(done)
        row.addWidget(skip)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.post.schedule import Scheduler
        sched = Scheduler(self.config.get_path("post.schedule_db",
                                               "./forge-data/schedule.db"))
        try:
            rows_data = sched.list()
            due_ids = {r["id"] for r in sched.due()}
        finally:
            sched.close()
        rows = []
        self._ids = []
        for r in rows_data:
            due = "DUE NOW" if r["id"] in due_ids else ""
            rows.append([r["id"], r["scheduled_for"], r["platform"],
                         r["title"] or "(no title)", r["status"], due])
            self._ids.append(r["id"])
        W.clear_layout(self.table_holder)
        self._table = W.make_table(
            ["ID", "When", "Platform", "Title", "Status", ""], rows)
        self.table_holder.addWidget(self._table)

    @_wrap
    def _mark(self, status: str):
        from forge.post.schedule import Scheduler
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select a row first.")
            return
        post_id = self._ids[rows[0].row()]
        sched = Scheduler(self.config.get_path("post.schedule_db",
                                               "./forge-data/schedule.db"))
        try:
            sched.mark(post_id, status)
        finally:
            sched.close()
        self.refresh()


# -- Pay -------------------------------------------------------------------------
class PayScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Payment links")
        self.hint("Configured under 'pay' in forge.yaml. Generate a shareable "
                  "tip-menu page with: forge pay tip-menu")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.pay.links import build_payment_links
        links = build_payment_links(self.config)
        menu = self.config.get_path("pay.tip_menu", []) or []
        rows = [[label, url] for label, url in links.items()]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(["Label", "URL"], rows))
        if menu:
            items = "\n".join(
                f"• {m.get('label')}: {m.get('price', '')}"
                for m in menu if isinstance(m, dict))
            lbl = QLabel("Tip menu:\n" + items)
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)
        if not rows:
            lbl = QLabel("No payment handles configured yet -- see "
                         "examples/forge.yaml.")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)


# -- Vault -------------------------------------------------------------------------
class VaultScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Vault")
        self.hint("AES-256-GCM encrypted storage. The password is never "
                  "stored -- lose it and the vault is gone for good.")
        form = QFormLayout()
        self.path = QLineEdit(self.config.get_path("vault.path",
                                                   "./forge-data/vault"))
        form.addRow("Vault folder:", self.path)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        unlock = QPushButton("Unlock")
        unlock.clicked.connect(self.unlock)
        lock = QPushButton("Lock")
        lock.setObjectName("Ghost")
        lock.clicked.connect(self.lock)
        refresh = QPushButton("Refresh list")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(unlock)
        row.addWidget(lock)
        row.addWidget(refresh)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.status = QLabel()
        self.status.setObjectName("Dim")
        self.layout.addWidget(self.status)
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)

    @_wrap
    def _vault(self):
        from forge.vault.store import Vault
        return Vault(self.path.text().strip())

    @_wrap
    def unlock(self):
        pw = W.ask_password(self, "Unlock vault", "Vault password:")
        if not pw:
            return
        self._vault().unlock(pw)
        W.show_info(self, "Vault", "Unlocked.")
        self.refresh()

    @_wrap
    def lock(self):
        self._vault().lock()
        W.show_info(self, "Vault", "Locked.")
        self.refresh()

    @_wrap
    def refresh(self):
        v = self._vault()
        try:
            names = v.list()
            self.status.setText(f"🔓 Unlocked -- {len(names)} blob(s).")
        except Exception:
            self.status.setText("🔒 Locked (or no vault here yet).")
            W.clear_layout(self.table_holder)
            return
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(["Blob"], [[n] for n in names]))


# -- Connect -----------------------------------------------------------------------
class ConnectScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Connectors")
        self.hint("Honest capability matrix: 'full' = real API, 'manual' = "
                  "she does the site/app part and CreatorForge handles the "
                  "files, 'none' = not possible.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.connect.registry import capabilities_table
        rows = [[r["connector"], r["import"], r["export"], r["platform"]]
                for r in capabilities_table()]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(
            ["Connector", "Import", "Export", "Platform"], rows))


# -- Analytics -----------------------------------------------------------------------
class AnalyticsScreen2(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Analytics")
        self.hint("Earnings and post stats you log (or import from CSV). "
                  "OnlyFans / Fansly / Snapchat have no stats API -- those "
                  "numbers are only as fresh as your last entry. Reddit "
                  "stats come live from Reddit's API.")
        self.body = QVBoxLayout()
        self.layout.addLayout(self.body, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.analytics.report import build_report
        from forge.analytics.store import AnalyticsStore
        store = AnalyticsStore(self.config.get_path("analytics.db_path",
                                                    "./forge-data/analytics.db"))
        try:
            totals = store.totals()
            by_pm = store.earnings_by_platform_month()
        finally:
            store.close()
        W.clear_layout(self.body)
        summary = QLabel(
            f"Total earnings logged: ${totals['total_earnings']:,.2f}\n"
            f"Posts tracked: {totals['posts_tracked']} "
            f"({totals['total_views']:,} views, {totals['total_likes']:,} likes)")
        summary.setObjectName("Section")
        self.body.addWidget(summary)
        rows = [[r["month"], r["platform"], f"${r['total']:,.2f}",
                 r["entries"]] for r in by_pm]
        self.body.addWidget(W.make_table(
            ["Month", "Platform", "Total", "Entries"], rows))
        if not by_pm:
            lbl = QLabel("No earnings logged yet. In the terminal:\n"
                         "forge analytics log-earning --platform onlyfans "
                         "--amount 120 --kind subs")
            lbl.setObjectName("Dim")
            self.body.addWidget(lbl)


# -- Skills ----------------------------------------------------------------------------
class SkillsScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Skills")
        self.hint("Extra capabilities, auto-discovered from "
                  "forge/skills/builtin/ (plus skills.paths in forge.yaml). "
                  "Drop in a new .py file with a SKILL object to add one.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        form = QFormLayout()
        self.args = QLineEdit()
        self.args.setPlaceholderText('--text "@her" in.png out.png')
        form.addRow("Skill args:", self.args)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        run = QPushButton("Run selected skill")
        run.clicked.connect(self.run_selected)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(run)
        row.addWidget(refresh)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setMaximumHeight(120)
        self.layout.addWidget(self.out)
        self.refresh()

    @_wrap
    def refresh(self):
        from forge.skills import discover_skills
        skills = discover_skills(self.config)
        self._names = sorted(skills)
        rows = [[s.name, s.version, s.description]
                for s in (skills[n] for n in self._names)]
        W.clear_layout(self.table_holder)
        self._table = W.make_table(["Skill", "Version", "Description"], rows)
        self.table_holder.addWidget(self._table)

    @_wrap
    def run_selected(self):
        import shlex
        from forge.skills import SkillError, run_skill
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select a skill first.")
            return
        name = self._names[rows[0].row()]
        args = shlex.split(self.args.text().strip())
        self.out.setPlainText(f"Running {name}…")
        try:
            result = run_skill(name, args, self.config)
        except SkillError as e:
            self.out.setPlainText(f"Skill failed:\n{e}")
            return
        self.out.setPlainText(result)


# -- Settings ----------------------------------------------------------------------------
class SettingsScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Settings")
        self.hint("Your forge.yaml as the app sees it (env overrides "
                  "applied). Edit the file itself to change things.")
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.layout.addWidget(self.view, 1)
        self.refresh()

    @_wrap
    def refresh(self):
        import yaml
        data = {k: v for k, v in self.config.items()
                if not k.startswith("_")}
        # redact anything that looks like a secret
        def redact(node):
            if isinstance(node, dict):
                return {k: ("•••" if any(s in k.lower() for s in
                                         ("token", "secret", "password", "key"))
                            and v else redact(v))
                        for k, v in node.items()}
            if isinstance(node, list):
                return [redact(x) for x in node]
            return node
        self.view.setPlainText(yaml.safe_dump(redact(data), sort_keys=False,
                                              default_flow_style=False))


# -- Spicy chat --------------------------------------------------------------------
class SpicyScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Spicy chat")
        self.hint("Flirty/dirty-talk drafts in her voice. Consent-gated: the "
                  "identity pack's scope must cover spicy chat. Drafts go "
                  "through the approval queue like everything else.")
        form = QFormLayout()
        self.platform = QLineEdit("onlyfans")
        self.sender = QLineEdit()
        self.sender.setPlaceholderText("fan handle")
        self.msg = QLineEdit()
        self.msg.setPlaceholderText("their message")
        self.tier = QComboBox()
        self.tier.addItems(["playful", "teasing", "explicit"])
        form.addRow("Platform", self.platform)
        form.addRow("Sender", self.sender)
        form.addRow("Their message", self.msg)
        form.addRow("Tier", self.tier)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        draft = QPushButton("Draft flirty reply")
        draft.clicked.connect(self._draft)
        settier = QPushButton("Set tier")
        settier.setObjectName("Ghost")
        settier.clicked.connect(self._set_tier)
        row.addWidget(draft)
        row.addWidget(settier)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.out = QLabel("")
        self.out.setWordWrap(True)
        self.out.setObjectName("Dim")
        self.layout.addWidget(self.out)
        self.layout.addStretch(1)

    def _pack(self):
        from forge.identity.pack import resolve_pack_path
        return resolve_pack_path(None, self.config)

    @_wrap
    def _draft(self):
        from forge.chat.spicy import SpicyEngine
        pack = self._pack()
        if not pack:
            W.show_error(self, "No identity pack",
                         "Set an identity pack first (Identity screen).")
            return
        engine = _load_chat_engine(self.config)
        eng = SpicyEngine.from_pack(
            pack, queue=engine.queue, config=self.config,
            heat_path=self.config.get_path("chat.spicy_heat_path",
                                           "./forge-data/chat-spicy-heat.json"))
        draft = eng.draft(platform=self.platform.text().strip(),
                          sender=self.sender.text().strip(),
                          text=self.msg.text().strip())
        _save_chat_engine(self.config, engine)
        self.out.setText("Drafted into the approval queue:\n"
                         + draft.reply)

    @_wrap
    def _set_tier(self):
        from forge.chat.spicy import SpicyEngine
        pack = self._pack()
        if not pack:
            W.show_error(self, "No identity pack",
                         "Set an identity pack first (Identity screen).")
            return
        eng = SpicyEngine.from_pack(
            pack, config=self.config,
            heat_path=self.config.get_path("chat.spicy_heat_path",
                                           "./forge-data/chat-spicy-heat.json"))
        eng.set_tier(self.platform.text().strip(),
                     self.sender.text().strip(), self.tier.currentText())
        W.show_info(self, "Tier set",
                    f"{self.sender.text().strip()} is now "
                    f"'{self.tier.currentText()}'.")


# -- Triage ----------------------------------------------------------------------
class TriageScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Incoming pic triage")
        self.hint("Blurred thumbnails of fan-sent pics. Approve the ones "
                  "worth her time, skip the rest -- no staring required.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        approve = QPushButton("Approve selected")
        approve.clicked.connect(lambda: self._decide("approve"))
        skip = QPushButton("Skip selected")
        skip.setObjectName("Danger")
        skip.clicked.connect(lambda: self._decide("skip"))
        row.addWidget(approve)
        row.addWidget(skip)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.refresh()

    def _queue(self):
        from forge.chat.triage import TriageQueue
        return TriageQueue(
            self.config.get_path("chat.triage_db",
                                 "./forge-data/triage.db"),
            self.config.get_path("chat.triage_thumbs_dir",
                                 "./forge-data/triage-thumbs"))

    @_wrap
    def refresh(self):
        q = self._queue()
        try:
            items = q.list(status="pending")
        finally:
            q.close()
        rows = [[i.id, i.platform, i.sender, i.nsfw_label,
                 i.note or ""] for i in items]
        self._ids = [i.id for i in items]
        W.clear_layout(self.table_holder)
        self._table = W.make_table(
            ["ID", "Platform", "From", "Scan", "Note"], rows)
        self.table_holder.addWidget(self._table)
        if not items:
            lbl = QLabel("Triage queue is empty. 🎉")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)

    @_wrap
    def _decide(self, action: str):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select an item first.")
            return
        item_id = self._ids[rows[0].row()]
        q = self._queue()
        try:
            if action == "approve":
                q.approve(item_id)
            else:
                q.skip(item_id)
        finally:
            q.close()
        self.refresh()


# -- Orders ----------------------------------------------------------------------
class OrdersScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Custom video orders")
        self.hint("Fan-paid custom videos. Comfort boundaries are enforced: "
                  "refused categories can't be ordered.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        btns = QHBoxLayout()
        for label, action in [("Mark paid", "pay"), ("Render", "render"),
                              ("To review", "review"),
                              ("Approve", "approve"),
                              ("Deliver", "deliver"),
                              ("Cancel", "cancel")]:
            b = QPushButton(label)
            if action == "cancel":
                b.setObjectName("Danger")
            b.clicked.connect(
                lambda _=False, a=action: self._transition(a))
            btns.addWidget(b)
        btns.addStretch(1)
        self.layout.addLayout(btns)
        self.refresh()

    def _store(self):
        from forge.orders.store import OrderStore
        return OrderStore(self.config.get_path("orders.db_path",
                                               "./forge-data/orders.db"))

    @_wrap
    def refresh(self):
        store = self._store()
        try:
            orders = store.list()
        finally:
            store.close()
        rows = [[o.id, o.fan_handle, o.scene_name or o.scene_path,
                 o.status, o.price_label or ""] for o in orders]
        self._ids = [o.id for o in orders]
        W.clear_layout(self.table_holder)
        self._table = W.make_table(
            ["ID", "Fan", "Scene", "Status", "Price"], rows)
        self.table_holder.addWidget(self._table)
        if not orders:
            lbl = QLabel("No orders yet.")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)

    @_wrap
    def _transition(self, action: str):
        from forge.orders.flow import (cancel_order, deliver_order,
                                       mark_paid, render_order, review_order)
        from forge.video.queue import VideoQueue
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            W.show_error(self, "No selection", "Select an order first.")
            return
        order_id = self._ids[rows[0].row()]
        store = self._store()
        try:
            if action == "pay":
                mark_paid(store, order_id)
            elif action == "render":
                from forge.identity.pack import resolve_pack_path
                pack = resolve_pack_path(None, self.config)
                if not pack:
                    raise ValueError("No identity pack configured.")
                queue = VideoQueue(self.config.get_path(
                    "video.queue_db", "./forge-data/video-queue.db"))
                try:
                    render_order(store, queue, self.config, order_id, pack)
                finally:
                    queue.close()
            elif action == "review":
                queue = VideoQueue(self.config.get_path(
                    "video.queue_db", "./forge-data/video-queue.db"))
                try:
                    review_order(store, queue, order_id)
                finally:
                    queue.close()
            elif action in ("approve", "deliver"):
                deliver_order(store, order_id)
            else:
                if not W.confirm(self, "Cancel order",
                                 f"Cancel order #{order_id}?"):
                    return
                cancel_order(store, order_id)
        finally:
            store.close()
        W.show_info(self, "Done", f"Order #{order_id} -> {action}.")
        self.refresh()


# -- Live avatar -------------------------------------------------------------------
class LiveScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Live AI avatar")
        self.hint("Real-time avatar for video calls (HeyGen/D-ID, paid) or "
                  "the honest local path (loop clip + OBS virtual camera).")
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.layout.addWidget(self.status_lbl)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["local-guide", "heygen", "did",
                                "sadtalker"])
        form.addRow("Provider", self.provider)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        start = QPushButton("Start")
        start.clicked.connect(self._start)
        stop = QPushButton("Stop")
        stop.setObjectName("Danger")
        stop.clicked.connect(self._stop)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(start)
        row.addWidget(stop)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.layout.addStretch(1)
        self.refresh()

    def _mgr(self):
        from forge.live.session import LiveSessionManager
        return LiveSessionManager(
            self.config.get_path("data_dir", "./forge-data"))

    @_wrap
    def refresh(self):
        st = self._mgr().status()
        if st.get("active"):
            self.status_lbl.setText(
                f"ACTIVE via {st.get('provider')} "
                f"(since {st.get('started_at')})")
        else:
            self.status_lbl.setText("No active live session.")

    @_wrap
    def _start(self):
        from forge.live.session import local_guide_text
        provider = self.provider.currentText()
        if provider == "local-guide":
            W.show_info(self, "Local path", local_guide_text())
            return
        session = self._mgr().start(provider, self.config)
        W.show_info(self, "Started",
                    f"Live session via {session['provider']}.")
        self.refresh()

    @_wrap
    def _stop(self):
        result = self._mgr().stop(self.config)
        W.show_info(self, "Stopped",
                    str(result.get("note") or "Session closed."))
        self.refresh()


# -- Spicy livestream ---------------------------------------------------------------
class StreamScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Spicy livestream (AFK)")
        self.hint("Her AI avatar streams via OBS -> RTMP while she's away. "
                  "Most cam sites expect a live verified performer -- AFK "
                  "avatar streaming can get the account banned. Read the "
                  "risk notes in docs/STREAMING.md.")
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.layout.addWidget(self.status_lbl)
        form = QFormLayout()
        self.platform = QComboBox()
        self.avatar = QComboBox()
        self.avatar.addItems(["loop", "sadtalker", "heygen", "did"])
        self.avatar_source = QLineEdit()
        self.avatar_source.setPlaceholderText(
            "video file (loop mode) or portrait (sadtalker)")
        form.addRow("Platform", self.platform)
        form.addRow("Avatar mode", self.avatar)
        form.addRow("Avatar source", self.avatar_source)
        self.layout.addLayout(form)
        self._load_platforms()
        row = QHBoxLayout()
        go = QPushButton("Go live")
        go.clicked.connect(self._go_live)
        stop = QPushButton("Stop")
        stop.setObjectName("Danger")
        stop.clicked.connect(self._stop)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(go)
        row.addWidget(stop)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.risk_lbl = QLabel("")
        self.risk_lbl.setWordWrap(True)
        self.risk_lbl.setObjectName("Dim")
        self.layout.addWidget(self.risk_lbl)
        self.layout.addStretch(1)
        self.refresh()

    def _mgr(self):
        from forge.stream.session import StreamSessionManager
        return StreamSessionManager(
            self.config.get_path("data_dir", "./forge-data"))

    @_wrap
    def _load_platforms(self):
        from forge.stream.platforms import list_platforms
        self._plats = list_platforms()
        self.platform.clear()
        for p in self._plats:
            self.platform.addItem(f"{p['label']} [{p['key']}]", p["key"])
        self.platform.currentIndexChanged.connect(self._show_risk)
        self._show_risk()

    @_wrap
    def _show_risk(self):
        key = self.platform.currentData()
        for p in self._plats:
            if p["key"] == key:
                self.risk_lbl.setText(
                    f"ToS risk: {p['tos_risk']}\n"
                    f"Chat: {p['chat_api']} -- {p['chat_notes']}")
                break

    @_wrap
    def refresh(self):
        st = self._mgr().status()
        if st.get("active"):
            self.status_lbl.setText(
                f"STREAMING on {st.get('platform_label')} "
                f"(since {st.get('started_at')})")
        else:
            self.status_lbl.setText("Not streaming.")

    @_wrap
    def _go_live(self):
        key = self.platform.currentData()
        if not W.confirm(
                self, "Confirm ToS risk",
                "AFK avatar streaming can get the account banned on most "
                "cam platforms. She keeps the risk. Continue?"):
            return
        session = self._mgr().go_live(
            platform=key, config=self.config,
            avatar=self.avatar.currentText(),
            avatar_source=self.avatar_source.text().strip(),
            acknowledged_risk=True)
        steps = "\n".join("- " + s for s in session["checklist"])
        W.show_info(self, "Session started",
                    f"Live on {session['platform_label']}.\n\n{steps}")
        self.refresh()

    @_wrap
    def _stop(self):
        result = self._mgr().stop()
        W.show_info(self, "Stopped", str(result.get("note", "")))
        self.refresh()


# -- Fan CRM --------------------------------------------------------------------------
class CRMScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Fan CRM")
        self.hint("Tags, notes, spend tracking, buyer-intent scores. Records "
                  "come from what she enters or imports -- the app can't "
                  "see inside the platforms.")
        row = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(["whales", "new", "active", "expired", "quiet",
                            "online"])
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(QLabel("Smart list:"))
        row.addWidget(self.kind)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        form = QFormLayout()
        self.platform = QLineEdit("onlyfans")
        self.handle = QLineEdit()
        self.handle.setPlaceholderText("fan handle")
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("25.00")
        self.note = QLineEdit()
        self.note.setPlaceholderText("note about this fan")
        self.tag = QLineEdit()
        self.tag.setPlaceholderText("tag, e.g. whale")
        form.addRow("Platform", self.platform)
        form.addRow("Handle", self.handle)
        form.addRow("Purchase $", self.amount)
        form.addRow("Note", self.note)
        form.addRow("Tag", self.tag)
        self.layout.addLayout(form)
        btns = QHBoxLayout()
        add = QPushButton("Add fan")
        add.clicked.connect(lambda: self._fan_op("upsert"))
        spend = QPushButton("Log purchase")
        spend.clicked.connect(lambda: self._fan_op("spend"))
        note = QPushButton("Save note")
        note.setObjectName("Ghost")
        note.clicked.connect(lambda: self._fan_op("note"))
        tag = QPushButton("Add tag")
        tag.setObjectName("Ghost")
        tag.clicked.connect(lambda: self._fan_op("tag"))
        score = QPushButton("Buyer intent")
        score.setObjectName("Ghost")
        score.clicked.connect(self._score)
        for b in (add, spend, note, tag, score):
            btns.addWidget(b)
        btns.addStretch(1)
        self.layout.addLayout(btns)
        self.refresh()

    def _crm(self):
        from forge.crm.store import FanCRM
        return FanCRM(self.config.get_path("crm.db_path",
                                           "./forge-data/crm.db"))

    @_wrap
    def refresh(self):
        c = self._crm()
        try:
            fans = c.smart_list(self.kind.currentText())
        finally:
            c.close()
        rows = [[f["platform"], f["handle"], f"${f['total_spend']:.0f}",
                 f["message_count"], f["status"],
                 ",".join(f["tags"])] for f in fans]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(
            ["Platform", "Handle", "Spend", "Msgs", "Status", "Tags"],
            rows))
        if not fans:
            lbl = QLabel("Nobody in this segment yet.")
            lbl.setObjectName("Dim")
            self.table_holder.addWidget(lbl)

    def _who(self):
        return (self.platform.text().strip(), self.handle.text().strip())

    @_wrap
    def _fan_op(self, op: str):
        platform, handle = self._who()
        if not handle:
            W.show_error(self, "No handle", "Enter a fan handle first.")
            return
        c = self._crm()
        try:
            if op == "spend":
                try:
                    amount = float(self.amount.text().strip() or "0")
                except ValueError:
                    raise ValueError("Purchase amount must be a number.")
                fan = c.record_spend(platform, handle, amount)
                W.show_info(self, "Logged",
                            f"{handle}: ${fan['total_spend']:.2f} total.")
            elif op == "note":
                c.add_note(platform, handle, self.note.text().strip())
                W.show_info(self, "Saved", "Note added.")
            elif op == "tag":
                fan = c.add_tag(platform, handle, self.tag.text().strip())
                W.show_info(self, "Tagged",
                            f"Tags: {', '.join(fan['tags'])}")
            else:
                c.upsert_fan(platform=platform, handle=handle)
                W.show_info(self, "Added", f"{handle} is in the CRM.")
        finally:
            c.close()
        self.refresh()

    @_wrap
    def _score(self):
        platform, handle = self._who()
        if not handle:
            W.show_error(self, "No handle", "Enter a fan handle first.")
            return
        c = self._crm()
        try:
            s = c.buyer_intent(platform, handle)
        finally:
            c.close()
        reasons = "\n".join("+ " + r for r in s["reasons"]) or "(no data)"
        W.show_info(self, f"Buyer intent: {s['score']}/100",
                    f"{s['method']}\n\n{reasons}")


# -- Flows / PPV / humanizer / compliance ------------------------------------------------
class FlowsScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Message flows & tools")
        self.hint("Welcome/win-back/nudge sequences, PPV upsell drafts, "
                  "the humanizer preview, and the compliance checker. "
                  "Flows draft into the approval queue -- never auto-send.")
        self.table_holder = QVBoxLayout()
        self.layout.addLayout(self.table_holder, 1)
        form = QFormLayout()
        self.flow = QComboBox()
        self.flow.addItems(["welcome", "winback", "nudge"])
        self.platform = QLineEdit("onlyfans")
        self.handle = QLineEdit()
        self.handle.setPlaceholderText("fan handle")
        form.addRow("Flow", self.flow)
        form.addRow("Platform", self.platform)
        form.addRow("Handle", self.handle)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        enroll = QPushButton("Enroll fan")
        enroll.clicked.connect(self._enroll)
        run = QPushButton("Run due steps")
        run.clicked.connect(self._run)
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(enroll)
        row.addWidget(run)
        row.addStretch(1)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        form2 = QFormLayout()
        self.ppv_sender = QLineEdit()
        self.ppv_sender.setPlaceholderText("fan handle")
        self.ppv_text = QLineEdit()
        self.ppv_text.setPlaceholderText("their message, e.g. how much for a custom?")
        self.draft_text = QLineEdit()
        self.draft_text.setPlaceholderText("a draft to humanize / check")
        form2.addRow("PPV sender", self.ppv_sender)
        form2.addRow("PPV message", self.ppv_text)
        form2.addRow("Draft text", self.draft_text)
        self.layout.addLayout(form2)
        row2 = QHBoxLayout()
        ppv = QPushButton("Draft PPV offer")
        ppv.clicked.connect(self._ppv)
        hum = QPushButton("Preview humanizer")
        hum.setObjectName("Ghost")
        hum.clicked.connect(self._humanize)
        chk = QPushButton("Compliance check")
        chk.setObjectName("Ghost")
        chk.clicked.connect(self._check)
        for b in (ppv, hum, chk):
            row2.addWidget(b)
        row2.addStretch(1)
        self.layout.addLayout(row2)
        self.out = QLabel("")
        self.out.setWordWrap(True)
        self.out.setObjectName("Dim")
        self.layout.addWidget(self.out)
        self.refresh()

    def _flows(self):
        from forge.chat.flows import FlowRunner
        return FlowRunner(self.config.get_path("chat.flows_db",
                                               "./forge-data/chat-flows.db"))

    @_wrap
    def refresh(self):
        r = self._flows()
        try:
            pending = r.pending()
        finally:
            r.close()
        rows = [[p["flow"], p["platform"], p["handle"],
                 p["step_idx"] + 1, p["due_at"]] for p in pending]
        W.clear_layout(self.table_holder)
        self.table_holder.addWidget(W.make_table(
            ["Flow", "Platform", "Fan", "Next step", "Due"], rows))

    @_wrap
    def _enroll(self):
        handle = self.handle.text().strip()
        if not handle:
            W.show_error(self, "No handle", "Enter a fan handle first.")
            return
        r = self._flows()
        try:
            r.enroll(self.flow.currentText(),
                     self.platform.text().strip(), handle)
        finally:
            r.close()
        W.show_info(self, "Enrolled",
                    f"{handle} is in '{self.flow.currentText()}'.")
        self.refresh()

    @_wrap
    def _run(self):
        from forge.chat.flows import run_due
        engine = _load_chat_engine(self.config)
        r = self._flows()
        try:
            drafts = run_due(r, engine)
        finally:
            r.close()
        _save_chat_engine(self.config, engine)
        W.show_info(self, "Done",
                    f"Drafted {len(drafts)} step(s) for approval.")

    @_wrap
    def _ppv(self):
        from forge.chat.ppv import ppv_offer_text
        from forge.pay.links import build_payment_links
        price_menu = self.config.get_path("orders.price_menu") or \
            self.config.get_path("pay.tip_menu", []) or []
        offer = ppv_offer_text(
            fan_message=self.ppv_text.text(), price_menu=price_menu,
            pay_links=build_payment_links(self.config),
            sender=self.ppv_sender.text().strip())
        if not offer:
            self.out.setText("No buying intent detected in that message.")
            return
        engine = _load_chat_engine(self.config)
        draft = engine.queue.add(
            platform=self.platform.text().strip(),
            sender=self.ppv_sender.text().strip(),
            incoming=self.ppv_text.text(), reply=offer, trigger="ppv")
        _save_chat_engine(self.config, engine)
        self.out.setText(f"PPV draft #{draft.id} queued:\n{offer}")

    @_wrap
    def _humanize(self):
        from forge.chat.humanize import humanize
        hcfg = dict(self.config.get_path("chat.humanize", {}) or {})
        hcfg["enabled"] = True
        self.out.setText("Humanized:\n"
                         + humanize(self.draft_text.text(), hcfg))

    @_wrap
    def _check(self):
        from forge.chat.compliance import check_draft_text
        findings = check_draft_text(
            self.draft_text.text(),
            self.config.get_path("chat.compliance", {}) or {})
        if not findings:
            self.out.setText("Clean -- no compliance flags.")
        else:
            self.out.setText("\n".join(
                f"[{f['category']}] {f['match']}: {f['detail']}"
                for f in findings))


# -- Ideas & insights ----------------------------------------------------------------------
class IdeasScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Ideas & insights")
        self.hint("Post ideas = template remixes of her own catalog tags "
                  "(not generative AI). Stats reflect only what she logged.")
        self.holder = QVBoxLayout()
        self.layout.addLayout(self.holder, 1)
        row = QHBoxLayout()
        fresh = QPushButton("Fresh batch")
        fresh.clicked.connect(lambda: self.refresh(
            seed=str(__import__("time").time())))
        refresh = QPushButton("Refresh")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(lambda: self.refresh())
        row.addStretch(1)
        row.addWidget(fresh)
        row.addWidget(refresh)
        self.layout.addLayout(row)
        self.refresh()

    @_wrap
    def refresh(self, seed: str = "forge"):
        from forge.analytics.insights import (ltv_arpu,
                                              peak_posting_times,
                                              plain_english_summary)
        from forge.analytics.store import AnalyticsStore
        from forge.catalog.store import CatalogStore
        from forge.content.ideas import (catalog_tags_for_ideas,
                                        generate_ideas)
        from forge.crm.store import FanCRM
        cfg = self.config
        cstore = CatalogStore(cfg.get_path("catalog.db_path",
                                           "./forge-data/catalog.db"))
        try:
            items = cstore.list(limit=500)
        finally:
            cstore.close()
        ideas = generate_ideas(
            catalog_tags=catalog_tags_for_ideas(items), count=8,
            seed_salt=seed)
        astore = AnalyticsStore(cfg.get_path("analytics.db_path",
                                             "./forge-data/analytics.db"))
        try:
            totals = astore.totals()
            peaks = peak_posting_times(astore.post_stats(limit=1000))
        finally:
            astore.close()
        crm = FanCRM(cfg.get_path("crm.db_path", "./forge-data/crm.db"))
        try:
            fans = crm.list_fans(limit=100000)
        finally:
            crm.close()
        ltv = ltv_arpu(total_earnings=totals["total_earnings"],
                       fan_count=len(fans),
                       fan_spends=[f["total_spend"] for f in fans])
        W.clear_layout(self.holder)
        summary = QLabel(plain_english_summary(totals=totals, ltv=ltv,
                                               peaks=peaks))
        summary.setWordWrap(True)
        summary.setObjectName("Dim")
        self.holder.addWidget(summary)
        rows = [[f"{i + 1}. [{d['angle']}]", d["caption"], d["hashtags"]]
                for i, d in enumerate(ideas)]
        self.holder.addWidget(W.make_table(
            ["#", "Caption", "Hashtags"], rows))


# -- Tube uploads ------------------------------------------------------------
class TubeScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Tube uploads")
        self.hint("Pornhub, XVideos, XNXX, xHamster, RedTube, YouPorn. "
                  "Honest note: none of these sites offer an upload API, so "
                  "this builds a ready-to-paste packet (title, description, "
                  "tags, checklist) -- she publishes on each site herself.")
        from forge.tube.sites import site_keys
        form = QFormLayout()
        self.site = QComboBox()
        self.site.addItems(site_keys())
        self.video = QLineEdit()
        self.video.setPlaceholderText("video file path")
        pick = QPushButton("Browse…")
        pick.setObjectName("Ghost")
        pick.clicked.connect(self._browse)
        vrow = QHBoxLayout()
        vrow.addWidget(self.video)
        vrow.addWidget(pick)
        self.name = QLineEdit()
        self.name.setPlaceholderText("her display name")
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("custom tags, comma-separated")
        from forge.tube.metadata import TITLE_TEMPLATES
        self.template = QComboBox()
        self.template.addItems(
            [f"Template {i + 1}: {t}" for i, t in enumerate(TITLE_TEMPLATES)])
        form.addRow("Site", self.site)
        form.addRow("Video", vrow)
        form.addRow("Name", self.name)
        form.addRow("Tags", self.tags)
        form.addRow("Title template", self.template)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        preview = QPushButton("Preview metadata")
        preview.clicked.connect(self._preview)
        packet = QPushButton("Build packet")
        packet.clicked.connect(self._packet)
        row.addWidget(preview)
        row.addWidget(packet)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setObjectName("Dim")
        self.layout.addWidget(self.out)
        self.layout.addStretch(1)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick a video", "",
            "Video (*.mp4 *.mov *.webm *.m4v)")
        if path:
            self.video.setText(path)

    def _meta(self):
        from forge.pay.links import build_payment_links
        from forge.tube.metadata import generate_metadata
        from forge.tube.sites import get_site
        site = get_site(self.site.currentText())
        tags = [t.strip() for t in self.tags.text().split(",") if t.strip()]
        return site, generate_metadata(
            site, None, name=self.name.text().strip(),
            custom_tags=tags, links=build_payment_links(self.config),
            template_idx=self.template.currentIndex())

    @_wrap
    def _preview(self):
        site, meta = self._meta()
        self.out.setPlainText(
            f"TITLE ({len(meta.title)}/{site.title_limit} chars):\n"
            f"{meta.title}\n\n"
            f"TAGS ({len(meta.tags)}/{site.max_tags}):\n"
            f"{', '.join(meta.tags)}\n\n"
            f"DESCRIPTION:\n{meta.description}")

    @_wrap
    def _packet(self):
        from forge.pay.links import build_payment_links
        from forge.tube.packets import build_packet
        from forge.tube.sites import get_site
        video = self.video.text().strip()
        if not video:
            W.show_error(self, "No video", "Pick a video file first.")
            return
        site = get_site(self.site.currentText())
        tags = [t.strip() for t in self.tags.text().split(",") if t.strip()]
        dest = build_packet(
            video, site,
            self.config.get_path("post.packets_dir", "./forge-data/packets"),
            name=self.name.text().strip(), custom_tags=tags,
            links=build_payment_links(self.config),
            template_idx=self.template.currentIndex())
        W.show_info(self, "Packet ready",
                    f"Upload packet built at:\n{dest}\n\n"
                    f"Copy the title/description/tags into {site.name}'s "
                    f"upload page, then publish there.")


# -- Word bank -----------------------------------------------------------------
class LexiconScreen(_Base):
    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("Word bank")
        self.hint("Her saved dictionary: slang, signature phrases, pet "
                  "names, go-to emoji, openers, closers (+ a spicy shelf). "
                  "The chat drafts use her words first, so the bot sounds "
                  "like her.")
        from forge.chat.lexicon import CATEGORIES
        form = QFormLayout()
        self.category = QComboBox()
        self.category.addItems(list(CATEGORIES))
        self.term = QLineEdit()
        self.term.setPlaceholderText("word or phrase")
        self.note = QLineEdit()
        self.note.setPlaceholderText("note (optional)")
        form.addRow("Category", self.category)
        form.addRow("Term", self.term)
        form.addRow("Note", self.note)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        add = QPushButton("Add word")
        add.clicked.connect(self._add)
        remove = QPushButton("Remove selected")
        remove.setObjectName("Ghost")
        remove.clicked.connect(self._remove)
        adopt = QPushButton("Adopt learned words")
        adopt.setObjectName("Ghost")
        adopt.clicked.connect(self._adopt)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(adopt)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.list = QTextEdit()
        self.list.setReadOnly(True)
        self.list.setObjectName("Dim")
        self.layout.addWidget(self.list)
        self.layout.addStretch(1)
        self._refresh()

    def _lex(self):
        from forge.chat.lexicon import CustomLexicon
        return CustomLexicon.load(self.config.get_path(
            "chat.lexicon_path", "./forge-data/lexicon.json"))

    def _save(self, lex):
        lex.save(self.config.get_path(
            "chat.lexicon_path", "./forge-data/lexicon.json"))

    @_wrap
    def _refresh(self):
        lex = self._lex()
        lines = []
        for cat, items in lex.list().items():
            if items:
                lines.append(f"[{cat}]")
                lines.extend(f"  - {e.term}" + (f" ({e.note})" if e.note
                                                 else "")
                             for e in items)
        self.list.setPlainText("\n".join(lines) or
                               "Word bank is empty -- add her words above.")

    @_wrap
    def _add(self):
        term = self.term.text().strip()
        if not term:
            W.show_error(self, "No term", "Type a word or phrase first.")
            return
        lex = self._lex()
        if lex.add(self.category.currentText(), term,
                   self.note.text().strip()):
            self._save(lex)
            self.term.clear()
            self.note.clear()
        self._refresh()

    @_wrap
    def _remove(self):
        # removes the term typed in the Term box from the chosen category
        term = self.term.text().strip()
        if not term:
            W.show_error(self, "No term",
                         "Type the word to remove in the Term box first.")
            return
        lex = self._lex()
        if lex.remove(self.category.currentText(), term):
            self._save(lex)
            W.show_info(self, "Removed", term)
        else:
            W.show_error(self, "Not found", f"{term!r} isn't in "
                         f"{self.category.currentText()}.")
        self._refresh()

    @_wrap
    def _adopt(self):
        from forge.chat.style import StyleProfile
        import json
        prof_path = self.config.get_path("chat.style_profile_path",
                                         "./style-profile.json")
        p = Path(prof_path)
        if not p.is_file():
            W.show_error(self, "No style profile",
                         "Build one first: forge chat style-build.")
            return
        prof = StyleProfile.from_dict(
            json.loads(p.read_text(encoding="utf-8")))
        lex = self._lex()
        added = lex.adopt_from_profile(prof, n=10)
        self._save(lex)
        W.show_info(self, "Adopted",
                    f"Added {len(added)} word(s): "
                    f"{', '.join(added) or '(none new)'}\nReview them above.")
        self._refresh()


# -- Public AI helpers ---------------------------------------------------------
class AIScreen(_Base):
    TASKS = [
        ("ask", "Ask anything"),
        ("caption", "Captions"),
        ("titles", "Video titles"),
        ("hashtags", "Hashtags"),
        ("ideas", "Content ideas"),
        ("scene-ideas", "Scene ideas"),
        ("polish", "Polish my draft"),
        ("reply-assist", "Reply assist"),
        ("promo", "Promo lines"),
    ]

    def __init__(self, config: ForgeConfig):
        super().__init__(config)
        self.title("AI helpers")
        hint_text = ("Grok, Gemini, Claude with her own API keys. Everything "
                     "that comes back is a DRAFT for her review -- nothing "
                     "posts or sends itself. No key = a setup error, never "
                     "a fake answer.")
        try:
            from forge.ai.providers import provider_status
            missing = [p["provider"] for p in provider_status(config)
                       if not p["configured"]]
            if missing:
                hint_text += (f" Missing keys: {', '.join(missing)} "
                              f"(set ai.*_api_key in forge.yaml or env vars).")
        except Exception:
            pass
        self.hint(hint_text)
        form = QFormLayout()
        self.provider = QComboBox()
        self.provider.addItems(["grok", "gemini", "claude"])
        self.task = QComboBox()
        self.task.addItems([label for _, label in self.TASKS])
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "topic / prompt / her draft text -- depends on the task")
        form.addRow("Provider", self.provider)
        form.addRow("Task", self.task)
        form.addRow("Input", self.input)
        self.layout.addLayout(form)
        row = QHBoxLayout()
        run = QPushButton("Run")
        run.clicked.connect(self._run)
        row.addWidget(run)
        row.addStretch(1)
        self.layout.addLayout(row)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setObjectName("Dim")
        self.layout.addWidget(self.out)
        self.layout.addStretch(1)

    @_wrap
    def _run(self):
        from forge.ai import tasks as T
        from forge.ai.providers import resolve_provider
        text = self.input.text().strip()
        if not text:
            W.show_error(self, "No input", "Type something first.")
            return
        key = self.TASKS[self.task.currentIndex()][0]
        provider = resolve_provider(self.provider.currentText(), self.config)
        if key == "ask":
            resp = T.ask(provider, text)
        elif key == "caption":
            resp = T.captions(provider, text)
        elif key == "titles":
            resp = T.titles(provider, text)
        elif key == "hashtags":
            resp = T.hashtags(provider, text)
        elif key == "ideas":
            resp = T.content_ideas(provider, text)
        elif key == "scene-ideas":
            resp = T.scene_ideas(provider, text)
        elif key == "polish":
            resp = T.polish(provider, text)
        elif key == "reply-assist":
            resp = T.reply_assist(provider, text)
        else:
            parts = text.rsplit(" ", 1)
            item, price = (parts[0], parts[1]) if len(parts) == 2 else (text, "")
            resp = T.promo_text(provider, item, price)
        self.out.setPlainText(
            f"[{resp.provider} / {resp.model}] -- draft, not sent anywhere\n\n"
            f"{resp.text}")


SCREENS: list[tuple[str, type]] = [
    ("Catalog", CatalogScreen),
    ("Identity", IdentityScreen),
    ("Video", VideoScreen),
    ("Persona", PersonaScreen),
    ("Chat", ChatScreen),
    ("Post", PostScreen),
    ("Schedule", ScheduleScreen2),
    ("Pay", PayScreen),
    ("Vault", VaultScreen),
    ("Connect", ConnectScreen),
    ("Analytics", AnalyticsScreen2),
    ("Ideas", IdeasScreen),
    ("Spicy", SpicyScreen),
    ("Triage", TriageScreen),
    ("Orders", OrdersScreen),
    ("Live", LiveScreen),
    ("Stream", StreamScreen),
    ("CRM", CRMScreen),
    ("Flows", FlowsScreen),
    ("Skills", SkillsScreen),
    ("Tube", TubeScreen),
    ("Word bank", LexiconScreen),
    ("AI helpers", AIScreen),
    ("Settings", SettingsScreen),
]
