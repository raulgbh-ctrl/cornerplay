"""The web library: your games in any browser on the home network (another PC, a tablet, a
phone), served by the phone remote's server (remote.py) under /web, behind the same code.

Browse and search every game, see what is installed and what is downloading, and queue an
install, an update or "install tonight" from the sofa or the office. Starting a game from the
web is left out on purpose: whoever sits at the PC decides that.

The App keeps a snapshot of the library for it (refreshed on the UI thread whenever the
library changes), so the server thread never touches Qt objects.
"""
import json

ACTIONS = ("install", "update", "tonight", "cancel")


def routes(snapshot, act):
    """snapshot() -> {"games": [...], "downloads": [...]}; act(action, key) -> "" or an error."""

    def page(method, query, body):
        return 200, "text/html; charset=utf-8", PAGE.encode()

    def games(method, query, body):
        return 200, "application/json", json.dumps(snapshot()).encode()

    def action(method, query, body):
        if method != "POST":
            return 405, "application/json", b'{"ok":false}'
        what, key = body.get("action"), body.get("key")
        if what not in ACTIONS or not isinstance(key, str):
            return 400, "application/json", b'{"ok":false}'
        err = act(what, key)
        return 200, "application/json", json.dumps({"ok": not err, "error": err}).encode()

    return {"/web": page, "/web/api/games": games, "/web/api/act": action}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cornerplay library</title><style>
:root{--bg:#16141a;--fg:#f2eee8;--muted:#a59f99;--card:#24212a;--line:#3a3640;--accent:#f0a868;--on:#1b1b1f;--ok:#7bd88f}
@media (prefers-color-scheme: light){:root{--bg:#f6f2ec;--fg:#1d1b20;--muted:#625d58;--card:#fff;--line:#ddd5cc}}
*{box-sizing:border-box}body{margin:0;font:15px system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;z-index:2;background:var(--bg);padding:14px 16px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:10px;align-items:center}
h1{font-size:20px;margin:0 12px 0 0}input,select{font:inherit;padding:9px 12px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
input{flex:1;min-width:160px}a{color:var(--accent)}
#dl{padding:0 16px}#dl div{background:var(--card);border-radius:10px;padding:8px 12px;margin:10px 0;display:flex;gap:10px;align-items:center}
#dl progress{flex:1}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:16px;padding:16px}
.c{background:var(--card);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.c img{width:100%;aspect-ratio:2/3;object-fit:cover;background:#333;display:block}.c.off img{opacity:.6}
.c .t{padding:8px 10px 2px;font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c .s{padding:0 10px;color:var(--muted);font-size:12px}.c .s.ok{color:var(--ok)}
.c button{margin:8px 10px 10px;padding:8px;border-radius:9px;border:0;background:var(--accent);color:var(--on);font-weight:700;cursor:pointer}
.c button.ghost{background:transparent;border:1px solid var(--line);color:var(--fg)}
#msg{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:var(--card);border:1px solid var(--line);padding:10px 16px;border-radius:12px;display:none}
</style></head><body>
<header><h1>Cornerplay</h1><input id="q" placeholder="Search your games" autocomplete="off">
<select id="f"><option value="">All games</option><option value="inst">Installed</option><option value="not">Not installed</option></select>
<a href="/">Remote</a></header>
<div id="dl"></div><main id="grid"></main><div id="msg"></div>
<script>
let data={games:[],downloads:[]};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function say(t){const m=document.getElementById('msg');m.textContent=t;m.style.display='block';clearTimeout(say.t);say.t=setTimeout(()=>m.style.display='none',2500)}
async function act(action,key){const r=await (await fetch('/web/api/act',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,key})})).json();
say(r.ok?({install:'Install queued',update:'Update queued',tonight:'Installs tonight',cancel:'Cancelled'}[action]):(r.error||'Could not do that'));load()}
function render(){const q=document.getElementById('q').value.trim().toLowerCase(),f=document.getElementById('f').value;
const gs=data.games.filter(g=>(!q||g.title.toLowerCase().includes(q))&&(!f||(f==='inst')===g.installed));
document.getElementById('grid').innerHTML=gs.map(g=>{let s=g.job?(g.job+' '+Math.max(0,Math.floor(g.progress))+'%'):(g.installed?(g.update?'Update available':'Installed'):'Not installed');
let b=g.job?'<button class="ghost" data-a="cancel" data-k="'+esc(g.key)+'">Cancel</button>':g.installed?(g.update?'<button data-a="update" data-k="'+esc(g.key)+'">Update</button>':''):
(g.canInstall?'<button data-a="install" data-k="'+esc(g.key)+'">Install</button><button class="ghost" data-a="tonight" data-k="'+esc(g.key)+'">'+(g.tonight?'Tonight ✓':'Install tonight')+'</button>':'');
return '<div class="c'+(g.installed?'':' off')+'"><img loading="lazy" src="'+esc(g.cover)+'" alt=""><div class="t" title="'+esc(g.title)+'">'+esc(g.title)+'</div><div class="s'+(g.installed?' ok':'')+'">'+esc(g.store)+' · '+esc(s)+'</div>'+b+'</div>'}).join('');
document.querySelectorAll('button[data-a]').forEach(x=>x.onclick=()=>act(x.dataset.a,x.dataset.k));
document.getElementById('dl').innerHTML=data.downloads.map(d=>'<div><b>'+esc(d.title)+'</b><progress max="100" value="'+Math.max(0,d.progress)+'"></progress><span>'+esc(d.detail||'')+'</span></div>').join('')}
async function load(){try{data=await (await fetch('/web/api/games')).json();render()}catch(e){}}
document.getElementById('q').oninput=render;document.getElementById('f').onchange=render;load();setInterval(load,5000);
</script></body></html>"""
