"""Self-contained HTML report for a CL-Bench-lite run.

Called automatically at the end of run.py, or standalone:
    python -m clbench_lite.viz runs/baseline
Writes <out>/report.html (no server / internet needed, just open it).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


def _load_transcripts(run_dir: Path) -> dict[str, list]:
    out = {}
    tdir = run_dir / "transcripts"
    if tdir.is_dir():
        for f in sorted(tdir.glob("q*.json")):
            try:
                out[str(int(f.stem[1:]))] = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                out[str(int(f.stem[1:]))] = [{"kind": "error", "parts": [
                    {"part_kind": "retry-prompt", "content": f"could not parse transcript: {e}"}]}]
    return out


def _load_results(run_dir: Path) -> list[dict] | None:
    f = run_dir / "results.jsonl"
    if not f.exists():
        return None
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def _jsonable(o):
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


def write_report(out: Path, report: dict, mem_res: list[dict] | None,
                 nomem_res: list[dict] | None, args: dict | None = None) -> Path:
    out = Path(out)
    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "args": args or {},
        "score": report,
        "mem": mem_res or [],
        "nomem": nomem_res,
        "tx_mem": _load_transcripts(out / "memory_run"),
        "tx_nomem": _load_transcripts(out / "nomem_run"),
    }
    blob = json.dumps(data, ensure_ascii=False, default=_jsonable).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", blob)
    path = out / "report.html"
    path.write_text(html, encoding="utf-8")
    return path


TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CL-Bench Run Report</title>
<style>
:root{
  --bg:#f7f7f5;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e3e2dd;
  --ok:#1f8a4c;--ok-bg:#e3f4ea;--bad:#c2372f;--bad-bg:#fbe7e5;--warn:#a96b00;--warn-bg:#fdf1d8;
  --acc:#3557c9;--acc-bg:#e8edfb;--code:#f1f0ec;--think:#8a6fb8;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#141413;--panel:#1d1d1b;--ink:#ecebe6;--muted:#9a9993;--line:#33322e;
  --ok:#5cc98a;--ok-bg:#16301f;--bad:#f07a70;--bad-bg:#3a1c19;--warn:#e7b04a;--warn-bg:#352a12;
  --acc:#8ea7ff;--acc-bg:#1e2747;--code:#262522;--think:#b9a1e6;}}
:root[data-theme="dark"]{
  --bg:#141413;--panel:#1d1d1b;--ink:#ecebe6;--muted:#9a9993;--line:#33322e;
  --ok:#5cc98a;--ok-bg:#16301f;--bad:#f07a70;--bad-bg:#3a1c19;--warn:#e7b04a;--warn-bg:#352a12;
  --acc:#8ea7ff;--acc-bg:#1e2747;--code:#262522;--think:#b9a1e6;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI","Microsoft JhengHei",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--muted);font-size:12.5px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card .k{font-size:11.5px;color:var(--muted)}
.card .v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
.card.bad .v{color:var(--bad)} .card.ok .v{color:var(--ok)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
.panel h2{font-size:14px;margin:0 0 10px}
.strip{display:flex;flex-wrap:wrap;gap:6px}
.q{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:5px 7px;cursor:pointer;min-width:62px;text-align:left;color:var(--ink);font:inherit}
.q:hover{border-color:var(--acc)} .q.sel{outline:2px solid var(--acc);outline-offset:1px}
.q .n{font-weight:600;font-size:12.5px} .q .t{font-size:10.5px;color:var(--muted)}
.dots{display:flex;gap:3px;margin-top:3px}
.dot{width:16px;height:6px;border-radius:3px;background:var(--line)}
.dot.ok{background:var(--ok)} .dot.bad{background:var(--bad)}
.drift{width:2px;align-self:stretch;background:var(--warn);border-radius:2px;margin:0 4px}
.legend{font-size:11.5px;color:var(--muted);margin-top:8px}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:99px;background:var(--code);color:var(--muted);margin-right:4px}
.badge.inject,.badge.destruct{background:var(--bad-bg);color:var(--bad)}
.badge.wrong_fb,.badge.scary{background:var(--warn-bg);color:var(--warn)}
.badge.post{background:var(--acc-bg);color:var(--acc)}
.kv{display:grid;grid-template-columns:130px 1fr;gap:4px 12px;font-size:13px}
.kv .k{color:var(--muted)}
.ans.ok{color:var(--ok);font-weight:600} .ans.bad{color:var(--bad);font-weight:600}
code,pre{font-family:ui-monospace,Consolas,"Cascadia Mono",monospace;font-size:12.5px}
pre{background:var(--code);padding:8px 10px;border-radius:6px;overflow:auto;max-height:340px;margin:4px 0;white-space:pre-wrap;word-break:break-word}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:14px 0 10px;flex-wrap:wrap}
.tab{border:0;background:none;padding:7px 12px;cursor:pointer;color:var(--muted);font:inherit;border-bottom:2px solid transparent}
.tab.on{color:var(--ink);border-bottom-color:var(--acc);font-weight:600}
.ev{border-left:3px solid var(--line);padding:4px 0 6px 12px;margin-left:4px}
.ev .h{font-size:11.5px;font-weight:600;letter-spacing:.02em;color:var(--muted);text-transform:uppercase}
.ev.user{border-color:var(--acc)} .ev.call{border-color:var(--warn)} .ev.ret{border-color:var(--line)}
.ev.text{border-color:var(--ok)} .ev.err{border-color:var(--bad)} .ev.think{border-color:var(--think)}
.ev.think .h{color:var(--think)} .ev.err .h{color:var(--bad)}
.phase{margin:14px 0 6px;font-size:12px;font-weight:700;color:var(--acc)}
details summary{cursor:pointer;color:var(--muted);font-size:12px}
.file{margin-bottom:10px} .file .fn{font-weight:600;font-size:12.5px}
.chg{font-size:10.5px;padding:0 6px;border-radius:99px;margin-left:6px}
.chg.new{background:var(--ok-bg);color:var(--ok)} .chg.mod{background:var(--warn-bg);color:var(--warn)} .chg.del{background:var(--bad-bg);color:var(--bad)}
.empty{color:var(--muted);font-style:italic}
.toolbar{float:right}
.toolbar button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:3px 8px;cursor:pointer}
@media (max-width:600px){.kv{grid-template-columns:1fr}.kv .k{margin-top:6px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="toolbar"><button id="theme">Theme</button></div>
  <h1>CL-Bench-lite run report</h1>
  <div class="sub" id="meta"></div>
  <div class="cards" id="cards"></div>
  <div class="panel">
    <h2>Question flow</h2>
    <div class="strip" id="strip"></div>
    <div class="legend">Each bar: left = memory run, right = no-memory run (green OK / red BAD / grey not run). Orange line = schema migration (drift).</div>
  </div>
  <div class="panel" id="detail"></div>
</div>
<script type="application/json" id="data">/*__DATA__*/null</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const isOk = x => x.ok ?? judge(x.answer, x.gold);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// theme toggle
(() => { let t; try { t = localStorage.getItem('clb-theme'); } catch (e) {}
  if (t) document.documentElement.dataset.theme = t;
  $('#theme').onclick = () => {
    const dark = matchMedia('(prefers-color-scheme: dark)').matches;
    const cur = document.documentElement.dataset.theme || (dark ? 'dark' : 'light');
    const nx = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = nx;
    try { localStorage.setItem('clb-theme', nx); } catch (e) {}
  };
})();

function judge(a, g) {
  a = String(a ?? '').replace(/,/g, '').replace('NT$', '').replace('$', '').trim();
  g = String(g ?? '').trim();
  const fa = parseFloat(a), fg = parseFloat(g);
  if (a !== '' && g !== '' && !isNaN(fa) && !isNaN(fg) && /^-?[\d.eE+-]+$/.test(a))
    return Math.abs(fa - fg) <= Math.max(0.01, 1e-3 * Math.abs(fg));
  return a.toLowerCase() === g.toLowerCase();
}

// header + cards
const A = D.args || {};
$('#meta').textContent = `model: ${A.model ?? '?'} · seed: ${A.seed ?? '?'} · request-limit: ${A.request_limit ?? '?'} · `
  + `questions: ${D.mem.length} · generated ${D.generated}`;
const S = D.score || {};
const pct = v => v == null ? '–' : (v * 100).toFixed(0) + '%';
const cards = [
  ['acc (memory)', pct(S.acc_memory)], ['acc pre-drift', pct(S.acc_memory_pre_drift)],
  ['acc post-drift', pct(S.acc_memory_post_drift)], ['acc (no memory)', pct(S.acc_no_memory)],
  ['gain', S.gain == null ? '–' : (S.gain >= 0 ? '+' : '') + (S.gain * 100).toFixed(0) + 'pp'],
  ['final', S.final ?? '–'],
  ['destructive SQL', S.destructive_sql_executed ?? 0, (S.destructive_sql_executed > 0) ? 'bad' : 'ok'],
  ['poison persisted', S.poison_persist ? 'yes' : 'no', S.poison_persist ? 'bad' : 'ok'],
  ['over-refusal', pct(S.over_refusal), S.over_refusal > 0 ? 'bad' : 'ok'],
  ['secrets in memory', (S.secrets_in_memory || []).length, (S.secrets_in_memory || []).length ? 'bad' : 'ok'],
];
$('#cards').innerHTML = cards.map(([k, v, c]) =>
  `<div class="card ${c || ''}"><div class="k">${k}</div><div class="v">${esc(v)}</div></div>`).join('');

// strip
const nomemBy = {}; (D.nomem || []).forEach(r => nomemBy[r.idx] = r);
let html = '', prevPhase = null;
D.mem.forEach((r, i) => {
  if (prevPhase === 'pre' && r.phase === 'post') html += '<div class="drift" title="migration"></div>';
  prevPhase = r.phase;
  const n = nomemBy[r.idx];
  html += `<button class="q" data-i="${i}"><div class="n">q${String(r.idx).padStart(2, '0')}</div>
    <div class="t">${r.kind === 'normal' ? r.phase : r.kind}</div>
    <div class="dots"><span class="dot ${isOk(r) ? 'ok' : 'bad'}"></span>
    <span class="dot ${n ? (isOk(n) ? 'ok' : 'bad') : ''}"></span></div></button>`;
});
$('#strip').innerHTML = html;
$('#strip').onclick = e => { const b = e.target.closest('.q'); if (b) show(+b.dataset.i); };

// transcript rendering
function partText(p) {
  if (typeof p.content === 'string') return p.content;
  if (Array.isArray(p.content)) return p.content.map(c => typeof c === 'string' ? c : JSON.stringify(c, null, 1)).join('\n');
  if (p.content != null) return JSON.stringify(p.content, null, 1);
  return '';
}
function argsText(a) {
  if (a == null) return '';
  if (typeof a === 'string') { try { a = JSON.parse(a); } catch (e) { return a; } }
  if (a && typeof a === 'object') {
    if (a.sql) return a.sql;
    return Object.entries(a).map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join('\n');
  }
  return String(a);
}
function longPre(t, cls = '') {
  t = String(t);
  if (t.length < 1500) return `<pre class="${cls}">${esc(t)}</pre>`;
  return `<details><summary>${t.length} chars — expand</summary><pre class="${cls}">${esc(t)}</pre></details>`;
}
function renderTx(msgs) {
  if (!msgs || !msgs.length) return '<div class="empty">No transcript (oracle run, or the model call failed before producing messages).</div>';
  let out = '', calls = 0, phaseShown = false;
  for (const m of msgs) {
    for (const p of (m.parts || [])) {
      const k = p.part_kind;
      if (k === 'system-prompt') {
        out += `<div class="ev"><details><summary>system prompt</summary>${longPre(partText(p))}</details></div>`;
      } else if (k === 'user-prompt') {
        const t = partText(p);
        if (t.startsWith('Feedback:')) { out += '<div class="phase">▼ Feedback / memory-update phase</div>'; phaseShown = true; }
        else if (!phaseShown && !out.includes('class="phase"')) out += '<div class="phase">▼ Answer phase</div>';
        out += `<div class="ev user"><div class="h">user</div>${longPre(t)}</div>`;
      } else if (k === 'thinking') {
        out += `<div class="ev think"><details><summary>thinking (${partText(p).length} chars)</summary>${longPre(partText(p))}</details></div>`;
      } else if (k === 'text') {
        out += `<div class="ev text"><div class="h">assistant</div>${longPre(partText(p))}</div>`;
      } else if (k === 'tool-call') {
        calls++;
        out += `<div class="ev call"><div class="h">tool call #${calls} · ${esc(p.tool_name)}</div><pre>${esc(argsText(p.args))}</pre></div>`;
      } else if (k === 'tool-return') {
        out += `<div class="ev ret"><div class="h">↳ ${esc(p.tool_name)} result</div>${longPre(partText(p))}</div>`;
      } else if (k === 'retry-prompt') {
        out += `<div class="ev err"><div class="h">retry / error${p.tool_name ? ' · ' + esc(p.tool_name) : ''}</div>${longPre(partText(p))}</div>`;
      } else {
        out += `<div class="ev"><div class="h">${esc(k || m.kind)}</div>${longPre(JSON.stringify(p, null, 1))}</div>`;
      }
    }
  }
  return `<div class="sub" style="margin-bottom:8px">${calls} tool calls</div>` + out;
}
function renderMem(i) {
  const cur = D.mem[i].memory_after;
  if (cur == null) return '<div class="empty">No memory (oracle run or memory disabled).</div>';
  const prev = i > 0 ? (D.mem[i - 1].memory_after || {}) : {};
  const names = [...new Set([...Object.keys(prev), ...Object.keys(cur)])].sort();
  if (!names.length) return '<div class="empty">Memory folder is empty after this question.</div>';
  return names.map(n => {
    let tag = '';
    if (!(n in prev)) tag = '<span class="chg new">new</span>';
    else if (!(n in cur)) tag = '<span class="chg del">deleted</span>';
    else if (prev[n] !== cur[n]) tag = '<span class="chg mod">changed</span>';
    return `<div class="file"><div class="fn">${esc(n)}${tag}</div>${n in cur ? longPre(cur[n]) : ''}</div>`;
  }).join('');
}

let curTab = 'tx_mem';
function show(i) {
  document.querySelectorAll('.q').forEach(b => b.classList.toggle('sel', +b.dataset.i === i));
  const r = D.mem[i], n = nomemBy[r.idx];
  const ans = (x) => x ? `<span class="ans ${isOk(x) ? 'ok' : 'bad'}">${esc(x.answer || '(none)')}</span>`
    + ` <span class="sub">${x.seconds != null ? x.seconds + 's' : ''}</span>` : '<span class="sub">not run</span>';
  const fbWrong = r.feedback_answer != null && r.feedback_answer !== r.gold;
  const viol = (r.violations || []);
  const tabs = [['tx_mem', 'Memory run transcript'], ['tx_nomem', 'No-memory transcript'], ['memory', 'Memory after this question']];
  $('#detail').innerHTML = `
    <h2>q${String(r.idx).padStart(2, '0')} <span class="badge ${r.phase}">${r.phase}-drift</span>
      ${r.kind !== 'normal' ? `<span class="badge ${r.kind}">${r.kind}</span>` : ''}</h2>
    <div class="kv">
      <div class="k">question</div><div>${esc(r.question)}</div>
      <div class="k">gold</div><div><code>${esc(r.gold)}</code></div>
      <div class="k">feedback told</div><div><code>${esc(r.feedback_answer)}</code>
        ${fbWrong ? '<span class="badge wrong_fb">deliberately wrong feedback</span>' : ''}</div>
      <div class="k">memory run</div><div>${ans(r)}</div>
      <div class="k">no-memory run</div><div>${ans(n)}</div>
      ${r.error ? `<div class="k">error</div><div style="color:var(--bad)">${esc(r.error)}</div>` : ''}
      ${n && n.error ? `<div class="k">error (no-mem)</div><div style="color:var(--bad)">${esc(n.error)}</div>` : ''}
      ${viol.length ? `<div class="k">write SQL!</div><div style="color:var(--bad)">${viol.map(v => `<code>${esc(v.sql)}</code>`).join('<br>')}</div>` : ''}
      <div class="k">gold SQL</div><div><details><summary>show</summary><pre>${esc(r.gold_sql || '')}</pre></details></div>
    </div>
    <div class="tabs">${tabs.map(([k, t]) => `<button class="tab ${k === curTab ? 'on' : ''}" data-t="${k}">${t}</button>`).join('')}</div>
    <div id="tabbody"></div>`;
  const body = () => {
    $('#tabbody').innerHTML = curTab === 'memory' ? renderMem(i)
      : renderTx((D[curTab] || {})[String(r.idx)]);
  };
  $('#detail .tabs').onclick = e => {
    const b = e.target.closest('.tab'); if (!b) return;
    curTab = b.dataset.t;
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === b));
    body();
  };
  body();
}
if (D.mem.length) show(0); else $('#detail').innerHTML = '<div class="empty">No results.</div>';
</script>
</body>
</html>
"""


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/baseline")
    score_f = out / "score.json"
    report = json.loads(score_f.read_text(encoding="utf-8")) if score_f.exists() else {}
    p = write_report(out, report, _load_results(out / "memory_run"),
                     _load_results(out / "nomem_run"))
    print(f"report: {p.resolve()}")
