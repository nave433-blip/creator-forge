"""CreatorForge dashboard web UI: server-rendered HTML pages with
progressive-enhancement JS.

The JSON API stays the contract for the mobile app; these pages give the
browser (and the PWA) a real interface on top of it. All data loads via
``fetch()`` against the JSON endpoints, so every page has explicit
loading, error, and empty states.

Auth: if ``dashboard.api_token`` is configured, the JS prompts once for
the token, keeps it in ``sessionStorage``, and sends it as a Bearer
header. Without a token configured (default localhost), everything just
works.
"""

from __future__ import annotations

CSS = """
:root{--bg:#0d0f14;--card:rgba(255,255,255,.06);--card2:rgba(255,255,255,.1);
--text:#f2f4f8;--dim:#9aa3b2;--acc:#7c5cff;--acc2:#00d4ff;--ok:#34d399;
--warn:#fbbf24;--bad:#f87171;--radius:16px}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
Helvetica,Arial,sans-serif;background:radial-gradient(1200px 800px at 20% -10%,
#1a1440 0%,var(--bg) 55%) fixed,var(--bg);color:var(--text);
min-height:100vh;-webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:20px 16px 64px}
header.top{display:flex;align-items:center;gap:12px;margin-bottom:18px}
header.top h1{font-size:22px;margin:0}
header.top .sub{color:var(--dim);font-size:13px}
nav.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 20px}
nav.tabs a{padding:9px 14px;border-radius:999px;background:var(--card);
color:var(--text);text-decoration:none;font-size:14px;border:1px solid transparent}
nav.tabs a.active{background:linear-gradient(135deg,var(--acc),var(--acc2));
color:#0b0b12;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
gap:14px}
.card{background:var(--card);border:1px solid rgba(255,255,255,.08);
border-radius:var(--radius);padding:16px;backdrop-filter:blur(12px)}
.card h3{margin:0 0 6px;font-size:14px;color:var(--dim);font-weight:500}
.card .big{font-size:30px;font-weight:700}
.card .ok{color:var(--ok)}.card .bad{color:var(--bad)}.card .warn{color:var(--warn)}
.card p{margin:8px 0 0;font-size:13px;color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:10px 8px;border-bottom:1px solid rgba(255,255,255,.07);
vertical-align:top}
th{color:var(--dim);font-weight:500;font-size:12px;text-transform:uppercase;
letter-spacing:.04em}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;
background:var(--card2)}
.badge.pending{background:rgba(251,191,36,.18);color:var(--warn)}
.badge.approved{background:rgba(52,211,153,.15);color:var(--ok)}
.badge.sent{background:rgba(0,212,255,.15);color:var(--acc2)}
.badge.rejected{background:rgba(248,113,113,.15);color:var(--bad)}
.btn{border:0;border-radius:10px;padding:9px 14px;font-size:14px;cursor:pointer;
color:#0b0b12;background:linear-gradient(135deg,var(--acc),var(--acc2));
font-weight:600}
.btn.ghost{background:var(--card2);color:var(--text);border:1px solid
rgba(255,255,255,.12)}
.btn.danger{background:rgba(248,113,113,.16);color:var(--bad);
border:1px solid rgba(248,113,113,.35)}
.btn:disabled{opacity:.5;cursor:default}
.btnrow{display:flex;gap:8px;flex-wrap:wrap}
input[type=text],input[type=search],input[type=password],select{
width:100%;padding:10px 12px;border-radius:10px;border:1px solid
rgba(255,255,255,.14);background:rgba(0,0,0,.35);color:var(--text);font-size:15px}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.toolbar .grow{flex:1;min-width:180px}
.state{padding:34px 16px;text-align:center;color:var(--dim);font-size:15px}
.state .spin{display:inline-block;width:22px;height:22px;border:3px solid
rgba(255,255,255,.15);border-top-color:var(--acc2);border-radius:50%;
animation:sp 1s linear infinite;vertical-align:-5px;margin-right:8px}
@keyframes sp{to{transform:rotate(360px)}}
.state.error{color:var(--bad)}
.reply{white-space:pre-wrap;background:rgba(0,0,0,.3);border-radius:10px;
padding:10px 12px;margin:8px 0 0;font-size:14px}
.mut{color:var(--dim);font-size:12.5px}
.pager{display:flex;gap:10px;align-items:center;justify-content:center;margin:18px 0}
.msg{white-space:pre-wrap}
@media (max-width:640px){
  table.resp thead{display:none}
  table.resp tr{display:block;margin-bottom:12px;background:var(--card);
  border-radius:var(--radius);padding:6px 10px}
  table.resp td{display:block;border:0;padding:6px 4px}
  table.resp td::before{content:attr(data-l);display:block;color:var(--dim);
  font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .card .big{font-size:26px}
}
"""

# Shared JS: token handling + api() helper with loading/error states.
JS = """
(function(){
var tok = sessionStorage.getItem('forge_token') || '';
window.forgeApi = function(path, opts){
  opts = opts || {};
  var headers = Object.assign({'Accept':'application/json'}, opts.headers||{});
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  return fetch(path, Object.assign({}, opts, {headers: headers}))
    .then(function(r){
      if (r.status === 401) return needToken().then(function(){ return window.forgeApi(path, opts); });
      if (!r.ok) return r.text().then(function(t){
        var e = new Error('HTTP '+r.status+': '+t.slice(0,200)); e.status=r.status; throw e; });
      return r.json();
    });
};
function needToken(){
  return new Promise(function(res){
    var box = document.getElementById('tokenbox');
    if (box) { box.style.display='block'; }
    var f = document.getElementById('tokenform');
    var go = function(ev){ if(ev) ev.preventDefault();
      var v = document.getElementById('tokeninput').value.trim();
      if (v) { tok = v; sessionStorage.setItem('forge_token', v); }
      if (box) box.style.display='none';
      res();
    };
    if (f) f.onsubmit = go;
    var b = document.getElementById('tokengo');
    if (b) b.onclick = go;
  });
}
window.forgeState = function(el, kind, msg){
  if (kind === 'loading') el.innerHTML = '<div class="state"><span class="spin"></span>Loading…</div>';
  else if (kind === 'error') el.innerHTML = '<div class="state error">⚠️ '+escapeHtml(msg||'Something went wrong.')+'</div>';
  else if (kind === 'empty') el.innerHTML = '<div class="state">'+escapeHtml(msg||'Nothing here yet.')+'</div>';
};
window.escapeHtml = function(s){
  return String(s==null?'':s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; });
};
})();
"""

_TOKENBOX = """
<div id="tokenbox" class="card" style="display:none;margin-bottom:16px">
  <h3>Dashboard token required</h3>
  <p>This dashboard has an API token set. Paste it once — it stays in this
  tab's session storage only.</p>
  <form id="tokenform" class="toolbar">
    <input id="tokeninput" type="password" class="grow" placeholder="API token" autocomplete="off">
    <button id="tokengo" class="btn" type="submit">Unlock</button>
  </form>
</div>
"""

_NAV = """
<nav class="tabs">
<a href="/ui/" data-p="home">🏠 Home</a>
<a href="/ui/chat" data-p="chat">💬 Chat queue</a>
<a href="/ui/catalog" data-p="catalog">🗂 Catalog</a>
<a href="/ui/promo" data-p="promo">🔗 Promo</a>
<a href="/ui/schedule" data-p="schedule">🗓 Schedule</a>
</nav>
"""


def _shell(title: str, active: str, body: str, extra_js: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — CreatorForge</title>
<meta name="theme-color" content="#0d0f14">
<link rel="manifest" href="/static/manifest.json">
<link rel="icon" type="image/png" sizes="192x192" href="/static/icons/icon-192.png">
<link rel="apple-touch-icon" href="/static/icons/icon-192.png">
<style>{CSS}</style>
</head><body>
<div class="wrap">
<header class="top"><h1>⚒️ CreatorForge</h1><span class="sub">local creator dashboard</span></header>
{_NAV}
{_TOKENBOX}
{body}
</div>
<script>{JS}</script>
<script>
document.querySelectorAll('nav.tabs a').forEach(function(a){{
  if (a.getAttribute('data-p') === {active!r}) a.classList.add('active');
}});
{extra_js}
</script>
<script>
if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('/static/sw.js').catch(function(){{}});
}}
</script>
</body></html>"""


def home_page() -> str:
    body = """
<div class="grid" id="cards"></div>
<div class="card" style="margin-top:16px">
<h3>Quick links</h3>
<div class="btnrow" style="margin-top:10px">
<a class="btn ghost" style="text-decoration:none" href="/ui/chat">Review chat queue</a>
<a class="btn ghost" style="text-decoration:none" href="/ui/catalog">Browse catalog</a>
<a class="btn ghost" style="text-decoration:none" href="/ui/promo">Promo links</a>
<a class="btn ghost" style="text-decoration:none" href="/docs">API docs</a>
</div></div>
"""
    js = """
var el = document.getElementById('cards');
forgeState(el, 'loading');
forgeApi('/api/status').then(function(s){
  function card(label, big, cls, note){
    return '<div class="card"><h3>'+label+'</h3><div class="big '+(cls||'')+'">'
      +big+'</div>'+(note?'<p>'+note+'</p>':'')+'</div>';
  }
  var idn = s.identity || {};
  var idCls = idn.status==='valid' ? 'ok' : (idn.status==='invalid' ? 'bad' : 'warn');
  var idTxt = idn.status==='valid' ? '✓ valid' : (idn.status==='invalid' ? '✗ invalid' : '○ missing');
  el.innerHTML =
    card('Identity / consent', idTxt, idCls, escapeHtml(idn.detail||idn.name||'')) +
    card('Chat drafts pending', s.chat.pending, s.chat.pending>0?'warn':'ok',
         'approval queue — nothing sends itself') +
    card('Catalog items', s.catalog.count, '', escapeHtml(s.catalog.note||'')) +
    card('Telegram bot', s.telegram.configured?'configured':'not set',
         s.telegram.configured?'ok':'warn', 'announcements + Stars paywall') +
    card('Promo campaigns', s.promo.campaigns, '',
         s.promo.links+' links · '+s.promo.clicks+' clicks · $'+s.promo.earnings+' attributed');
}).catch(function(e){ forgeState(el, 'error', e.message); });
"""
    return _shell("Home", "home", body, js)


def chat_page() -> str:
    body = """
<div class="toolbar">
  <button class="btn ghost" id="refresh">↻ Refresh</button>
  <span class="mut" id="count"></span>
</div>
<div id="list"></div>
"""
    js = """
var el = document.getElementById('list');
function load(){
  forgeState(el, 'loading');
  forgeApi('/chat/queue').then(function(q){
    var rows = (q.pending||[]);
    document.getElementById('count').textContent = rows.length + ' pending · ' +
      (q.all||[]).length + ' total';
    if (!rows.length) { forgeState(el, 'empty', 'Queue is clear — no drafts waiting. 🎉'); return; }
    var h = '<table class="resp"><thead><tr><th>From</th><th>Draft reply</th><th>Trigger</th><th>Actions</th></tr></thead><tbody>';
    rows.forEach(function(d){
      h += '<tr>'
        + '<td data-l="From"><b>'+escapeHtml(d.sender)+'</b><br><span class="mut">'
        + escapeHtml(d.platform)+' · #'+d.id
        + (d.escalated?' · ⚠️ ' + escapeHtml((d.escalation_categories||[]).join(', ')):'')
        + '</span><div class="msg" style="margin-top:6px">'+escapeHtml(d.incoming)+'</div></td>'
        + '<td data-l="Draft reply"><div class="reply">'+escapeHtml(d.reply)+'</div></td>'
        + '<td data-l="Trigger"><span class="badge pending">'+escapeHtml(d.trigger||'—')+'</span></td>'
        + '<td data-l="Actions"><div class="btnrow">'
        + '<button class="btn" data-act="approve" data-id="'+d.id+'">✓ Approve</button>'
        + '<button class="btn ghost" data-act="sent" data-id="'+d.id+'">Sent</button>'
        + '<button class="btn danger" data-act="reject" data-id="'+d.id+'">✕ Reject</button>'
        + '</div></td></tr>';
    });
    h += '</tbody></table>';
    el.innerHTML = h;
    el.querySelectorAll('button[data-act]').forEach(function(b){
      b.onclick = function(){
        b.disabled = true;
        var act = b.getAttribute('data-act'), id = b.getAttribute('data-id');
        forgeApi('/chat/'+act+'/'+id, {method:'POST'}).then(load).catch(function(e){
          alert('Failed: '+e.message); b.disabled = false; });
      };
    });
  }).catch(function(e){ forgeState(el, 'error', e.message); });
}
document.getElementById('refresh').onclick = load;
load();
"""
    return _shell("Chat queue", "chat", body, js)


def catalog_page() -> str:
    body = """
<div class="toolbar">
  <input id="q" type="search" class="grow" placeholder="Search path, notes, tags…">
  <select id="kind" style="max-width:160px">
    <option value="">all kinds</option>
    <option value="photo">photo</option>
    <option value="video">video</option>
    <option value="audio">audio</option>
    <option value="other">other</option>
  </select>
  <button class="btn" id="go">Search</button>
</div>
<div id="list"></div>
<div class="pager" id="pager" style="display:none">
  <button class="btn ghost" id="prev">← Prev</button>
  <span class="mut" id="pinfo"></span>
  <button class="btn ghost" id="next">Next →</button>
</div>
"""
    js = """
var el = document.getElementById('list'), pager = document.getElementById('pager');
var limit = 24, offset = 0, total = 0;
function load(){
  forgeState(el, 'loading'); pager.style.display = 'none';
  var q = document.getElementById('q').value.trim();
  var kind = document.getElementById('kind').value;
  var url = '/catalog?limit='+limit+'&offset='+offset
    + (q ? '&q='+encodeURIComponent(q) : '')
    + (kind ? '&kind='+encodeURIComponent(kind) : '');
  forgeApi(url).then(function(r){
    total = r.total || 0;
    var items = r.items || [];
    if (!items.length) { forgeState(el, 'empty', 'No items match.'); return; }
    var h = '<table class="resp"><thead><tr><th>Path</th><th>Kind</th><th>Tags</th></tr></thead><tbody>';
    items.forEach(function(it){
      h += '<tr><td data-l="Path" class="msg">'+escapeHtml(it.path)+'</td>'
        + '<td data-l="Kind"><span class="badge">'+escapeHtml(it.kind||'?')+'</span></td>'
        + '<td data-l="Tags" class="mut">'+escapeHtml(it.tags||'')+'</td></tr>';
    });
    el.innerHTML = h + '</tbody></table>';
    pager.style.display = 'flex';
    document.getElementById('pinfo').textContent =
      (offset+1) + '–' + Math.min(offset+limit, total) + ' of ' + total;
    document.getElementById('prev').disabled = offset === 0;
    document.getElementById('next').disabled = offset + limit >= total;
  }).catch(function(e){ forgeState(el, 'error', e.message); });
}
document.getElementById('go').onclick = function(){ offset = 0; load(); };
document.getElementById('q').addEventListener('keydown', function(e){
  if (e.key === 'Enter') { offset = 0; load(); } });
document.getElementById('prev').onclick = function(){ offset = Math.max(0, offset-limit); load(); };
document.getElementById('next').onclick = function(){ offset += limit; load(); };
load();
"""
    return _shell("Catalog", "catalog", body, js)


def promo_page() -> str:
    body = """
<div class="toolbar">
  <button class="btn ghost" id="refresh">↻ Refresh</button>
  <span class="mut">Clicks count only hits through your short links
  (<span class="mut">/promo/go/&lt;code&gt;</span>) — raw hits, not uniques.</span>
</div>
<div id="list"></div>
"""
    js = """
var el = document.getElementById('list');
function load(){
  forgeState(el, 'loading');
  Promise.all([forgeApi('/promo/links'), forgeApi('/promo/report')]).then(function(r){
    var links = r[0].links || [], rep = r[1].campaigns || [];
    if (!links.length) { forgeState(el, 'empty', 'No promo links yet. Create one with: forge promo link-create --url … --campaign …'); return; }
    var h = '<table class="resp"><thead><tr><th>Code</th><th>Campaign</th><th>Clicks</th><th>Short link</th></tr></thead><tbody>';
    var jobs = links.map(function(l){
      return forgeApi('/promo/clicks/'+l.code).then(function(c){ l._clicks = c.clicks; })
        .catch(function(){ l._clicks = '?'; });
    });
    Promise.all(jobs).then(function(){
      links.forEach(function(l){
        h += '<tr><td data-l="Code"><b>'+escapeHtml(l.code)+'</b></td>'
          + '<td data-l="Campaign">'+escapeHtml(l.campaign)+'</td>'
          + '<td data-l="Clicks">'+l._clicks+'</td>'
          + '<td data-l="Short link" class="mut">/promo/go/'+escapeHtml(l.code)+'</td></tr>';
      });
      h += '</tbody></table>';
      if (rep.length) {
        h += '<h3 style="margin-top:20px">Per-campaign</h3><table class="resp"><thead><tr><th>Campaign</th><th>Links</th><th>Clicks</th><th>Earnings</th></tr></thead><tbody>';
        rep.forEach(function(c){
          h += '<tr><td data-l="Campaign">'+escapeHtml(c.campaign)+'</td>'
            + '<td data-l="Links">'+c.links+'</td>'
            + '<td data-l="Clicks">'+(c.clicks||0)+'</td>'
            + '<td data-l="Earnings">$'+Number(c.earnings||0).toFixed(2)+'</td></tr>';
        });
        h += '</tbody></table>';
      }
      el.innerHTML = h;
    });
  }).catch(function(e){ forgeState(el, 'error', e.message); });
}
document.getElementById('refresh').onclick = load;
load();
"""
    return _shell("Promo links", "promo", body, js)


def schedule_page() -> str:
    body = """
<div class="toolbar">
  <button class="btn ghost" id="refresh">↻ Refresh</button>
  <span class="mut" id="count"></span>
</div>
<div id="list"></div>
<p class="mut" style="margin-top:12px">Manual-assist only: post these yourself in each app when due.</p>
"""
    js = """
var el = document.getElementById('list');
function load(){
  forgeState(el, 'loading');
  forgeApi('/schedule').then(function(r){
    var items = r.scheduled || [];
    document.getElementById('count').textContent = (r.due_count||0) + ' due · ' + items.length + ' scheduled';
    if (!items.length) { forgeState(el, 'empty', 'Nothing scheduled — the calendar is clear.'); return; }
    var h = '<table class="resp"><thead><tr><th>When</th><th>Title</th><th>Platform</th><th>Status</th><th></th></tr></thead><tbody>';
    items.forEach(function(it){
      h += '<tr><td data-l="When">'+escapeHtml(it.scheduled_for||'')+'</td>'
        + '<td data-l="Title"><b>'+escapeHtml(it.title||'')+'</b>'
        + (it.is_due?' <span class="badge pending">due</span>':'')+'</td>'
        + '<td data-l="Platform"><span class="badge">'+escapeHtml(it.platform||'')+'</span></td>'
        + '<td data-l="Status" class="mut">'+escapeHtml(it.status||'')+'</td>'
        + '<td data-l="">' + (it.status==='done' ? '' :
            '<button class="btn ghost" data-id="'+it.id+'">Mark done</button>') + '</td></tr>';
    });
    el.innerHTML = h + '</tbody></table>';
    el.querySelectorAll('button[data-id]').forEach(function(b){
      b.onclick = function(){
        b.disabled = true;
        forgeApi('/schedule/mark/'+b.getAttribute('data-id')+'?status=done', {method:'POST'})
          .then(load).catch(function(e){ alert('Failed: '+e.message); b.disabled=false; });
      };
    });
  }).catch(function(e){ forgeState(el, 'error', e.message); });
}
document.getElementById('refresh').onclick = load;
load();
"""
    return _shell("Schedule", "schedule", body, js)
