#!/usr/bin/env python3
"""
Bolognese Basket Page Generator
Runs persona_basket_tracker.py against bolognese_basket.json (Traditional/Saver
personas across Woolworths, Coles, ALDI) and writes public/bolognese.html.

Run manually:
  python3 scripts/generate_bolognese.py

Called by cron each Thursday (as part of basket-watch-weekly job):
  python3 /Users/simontracey/basket-watch-au/scripts/generate_bolognese.py >> /tmp/basket-watch-bolognese-cron.log 2>&1
"""

import sys, json
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPO_DIR    = Path(__file__).parent.parent
PUBLIC_DIR  = REPO_DIR / 'public'
AEST        = ZoneInfo('Australia/Sydney')

GC_SCRIPTS  = Path('/Users/simontracey/.openclaw/workspace/skills/grocery-compare/scripts')
BASKET_CFG  = GC_SCRIPTS / 'bolognese_basket.json'
RESULTS_OUT = Path('/Users/simontracey/.openclaw/workspace/skills/grocery-compare/.bolognese-results.json')

sys.path.insert(0, str(GC_SCRIPTS))
from persona_basket_tracker import run_persona_basket  # noqa: E402

PUBLIC_DIR.mkdir(exist_ok=True)

# ── Run the persona basket tracker (live prices, all retailers) ──────────────
print(f"[{datetime.now(AEST).strftime('%Y-%m-%d %H:%M %Z')}] Running bolognese persona basket...")
basket_cfg = json.loads(BASKET_CFG.read_text())
results = run_persona_basket(basket_cfg)

# Persist raw results (same location the manual runs used)
RESULTS_OUT.write_text(json.dumps(results, indent=2))
print(f"  ✓ Raw results written: {RESULTS_OUT}")

run_date_utc = results.get('run_date', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
try:
    dt = datetime.strptime(run_date_utc, '%Y-%m-%d %H:%M UTC')
    dt_aest = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(AEST)
    run_display = dt_aest.strftime('%-d %B %Y')
except Exception:
    run_display = run_date_utc

# ── Transform tracker output into the JS data blob shape ─────────────────────
def to_cell(raw):
    if raw is None:
        return {"notFound": True}
    if raw.get("na"):
        return {"na": True, "label": raw.get("product_name", "")}
    label = raw.get("name") or raw.get("product_name") or ""
    qty = raw.get("qty", 1)
    price = raw.get("price")
    cell = {"price": price, "label": label}
    if raw.get("isSpecial"):
        cell["isSpecial"] = True
    if qty and qty > 1 and price is not None:
        cell["qty"] = qty
        cell["unitPrice"] = round(price / qty, 2)
    return cell

RETAILER_KEY = {"woolworths": "ww", "coles": "coles", "aldi": "aldi"}

personas_blob = {}
ww_live_count = 0
ww_total_count = 0
for persona_key, cfg in basket_cfg["personas"].items():
    rows = results["personas"].get(persona_key, [])
    items = []
    for row in rows:
        item = {"name": row["name"]}
        for retailer, jskey in RETAILER_KEY.items():
            raw = row["prices"].get(retailer)
            item[jskey] = to_cell(raw)
            if retailer == "woolworths":
                ww_total_count += 1
                if raw is not None and raw.get("price") is not None:
                    ww_live_count += 1
        items.append(item)
    personas_blob[persona_key] = {
        "label": cfg["label"],
        "description": cfg.get("description", ""),
        "items": items,
    }

ww_note = (
    f"<strong>ℹ️ Woolworths prices:</strong> Live — fetched {run_display} via CDP harness."
    if ww_total_count and ww_live_count == ww_total_count
    else f"<strong>ℹ️ Woolworths prices:</strong> {ww_live_count}/{ww_total_count} live-fetched {run_display}; "
         f"remaining items fell back to last verified capture (WW API/harness partially unavailable)."
)

data_json = json.dumps({"runDate": run_display, "personas": personas_blob}, indent=2, ensure_ascii=False)

# ── Static shell (CSS + markup + render JS) — identical across runs ──────────
html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Basket Watch — Spaghetti Bolognese Persona Baskets</title>
<meta name="description" content="How much does Spaghetti Bolognese cost? Compare Traditional (brand-loyal) vs Saver (own-brand) shopping across Woolworths, Coles and ALDI.">
<style>
  :root {{
    --green:  #007837;
    --red:    #e01523;
    --yellow: #ffc72c;
    --blue:   #004f9f;
    --bg:     #f8f9fa;
    --card:   #ffffff;
    --border: #dee2e6;
    --text:   #212529;
    --muted:  #6c757d;
    --cheapest-bg: #d4edda;
    --dearest-bg:  #f8d7da;
    --na-bg:       #e9ecef;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }}
  header {{ background: var(--text); color: #fff; padding: 1.5rem 1rem; text-align: center; }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
  header p  {{ color: #adb5bd; font-size: 0.9rem; margin-top: 0.25rem; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
  .back-link {{ display: inline-block; font-size: 0.85rem; color: var(--muted); text-decoration: none; margin-bottom: 1.25rem; }}
  .back-link:hover {{ color: var(--text); }}

  .persona-toggle {{ display: flex; gap: 0.6rem; margin-bottom: 0.75rem; }}
  .persona-btn {{
    padding: 0.55rem 1.4rem; border-radius: 999px; border: 2px solid var(--border);
    background: var(--card); color: var(--muted); font-size: 0.95rem; font-weight: 600;
    cursor: pointer; transition: all 0.15s;
  }}
  .persona-btn:hover {{ border-color: var(--text); color: var(--text); }}
  .persona-btn.active {{ background: var(--text); border-color: var(--text); color: #fff; }}
  .persona-desc {{ font-size: 0.88rem; color: var(--muted); margin-bottom: 1.25rem; min-height: 1.4em; }}

  .hero {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--card); border-radius: 10px; padding: 1rem; border: 1px solid var(--border); text-align: center; }}
  .card.winner {{ border-color: var(--green); box-shadow: 0 0 0 2px var(--green); }}
  .card .retailer {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.25rem; }}
  .card .basket-total {{ font-size: 1.8rem; font-weight: 700; }}
  .card .found {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }}

  .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); background: var(--card); margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{ background: var(--text); color: #fff; padding: 0.6rem 0.75rem; text-align: center; font-weight: 600; font-size: 0.8rem; }}
  th:first-child {{ text-align: left; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: center; vertical-align: top; }}
  td:first-child {{ text-align: left; font-size: 0.85rem; }}
  tr:last-child td {{ border-bottom: none; }}
  td.cheapest {{ background: var(--cheapest-bg); font-weight: 600; }}
  td.dearest  {{ background: var(--dearest-bg); }}
  td.na       {{ background: var(--na-bg); color: var(--muted); font-size: 0.85rem; }}
  td.total    {{ font-weight: 700; font-size: 1rem; }}
  td.total.winner {{ background: var(--cheapest-bg); }}
  td.total.dearest-total {{ background: var(--dearest-bg); }}
  .price-main {{ font-variant-numeric: tabular-nums; }}
  .price-note {{ display: block; font-size: 0.72rem; color: var(--muted); font-weight: 400; margin-top: 0.1rem; }}
  .price-note.special {{ color: #b45309; }}
  .item-name {{ font-weight: 500; }}

  .legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.75rem; }}
  .legend span {{ display: flex; align-items: center; gap: 0.3rem; }}
  .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
  .dot-cheap {{ background: var(--cheapest-bg); border: 1px solid #a8d5b5; }}
  .dot-dear  {{ background: var(--dearest-bg);  border: 1px solid #f5c2c7; }}
  .dot-na    {{ background: var(--na-bg);        border: 1px solid #ced4da; }}

  .note-box {{ background: #fff8e1; border: 1px solid #ffe082; border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.82rem; color: #6c5100; margin-bottom: 1.25rem; }}
  .methodology {{ background: var(--card); border-radius: 10px; padding: 1rem 1.25rem; border: 1px solid var(--border); font-size: 0.82rem; color: var(--muted); margin-bottom: 1.5rem; }}
  .methodology h3 {{ font-size: 0.9rem; color: var(--text); margin-bottom: 0.5rem; }}
  .methodology li {{ margin-left: 1.2rem; margin-bottom: 0.2rem; }}
  footer {{ text-align: center; padding: 2rem 1rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
  footer a {{ color: var(--muted); }}
  h2 {{ font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 0.75rem; }}
</style>
</head>
<body>

<header>
  <h1>🛒 Basket Watch</h1>
  <p>Weekly online supermarket basket comparison &mdash; updated every Thursday</p>
</header>

<div class="container">

  <a class="back-link" href="/">← Back to basket comparison</a>

  <h2>🍝 Spaghetti Bolognese — Persona Baskets</h2>
  <p style="font-size:0.9rem;color:var(--muted);margin-bottom:1.25rem;">
    Same meal, different shopping mindset. How much does Bolognese really cost depending on who you are?
  </p>

  <div class="persona-toggle">
    <button class="persona-btn active" data-persona="saver" onclick="setPersona('saver')">🛒 Saver</button>
    <button class="persona-btn" data-persona="traditional" onclick="setPersona('traditional')">🍽️ Traditional</button>
  </div>
  <div class="persona-desc" id="persona-desc"></div>

  <div class="hero" id="summary-cards"></div>

  <div class="legend">
    <span><span class="dot dot-cheap"></span> Cheapest</span>
    <span><span class="dot dot-dear"></span> Most expensive</span>
    <span><span class="dot dot-na"></span> — Not stocked / N/A</span>
    <span>⭐ On special</span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>🟢 Woolworths</th>
          <th>🔴 Coles</th>
          <th>🟡 ALDI</th>
        </tr>
      </thead>
      <tbody id="items-tbody"></tbody>
    </table>
  </div>

  <div class="note-box" id="ww-note"></div>

  <div class="methodology">
    <h3>About this data</h3>
    <ul>
      <li>10-item Spaghetti Bolognese meal basket — ingredients for a family dinner (serves 4)</li>
      <li><strong>Traditional</strong>: prefers familiar name brands, doesn't switch for price</li>
      <li><strong>Saver</strong>: chooses own-brand / cheapest available per item</li>
      <li>Prices fetched live at {run_display} — Woolworths via CDP harness, Coles &amp; ALDI via search/product API</li>
      <li>N/A = product genuinely not stocked at that retailer for that persona</li>
      <li>Basket totals include only priced items (N/A items excluded)</li>
    </ul>
  </div>

</div>

<footer>
  <p>Basket Watch &mdash; built by <a href="https://sjtracey.com">Simon Tracey</a> &mdash; data captured {run_display}</p>
  <p style="margin-top:0.4rem;">Prices are online prices only. Not affiliated with any supermarket.</p>
</footer>

<script>
window.BOLOGNESE_DATA = {data_json};

// ── Render logic ────────────────────────────────────────────────────────────
const RETAILERS = ['ww', 'coles', 'aldi'];
const RETAILER_LABELS = {{ww: '🟢 WW', coles: '🔴 Coles', aldi: '🟡 ALDI'}};

let currentPersona = 'saver';

function fmt(n) {{
  return '$' + n.toFixed(2);
}}

function setPersona(persona) {{
  currentPersona = persona;
  document.querySelectorAll('.persona-btn').forEach(b => {{
    b.classList.toggle('active', b.dataset.persona === persona);
  }});
  render();
}}

function render() {{
  const data = window.BOLOGNESE_DATA.personas[currentPersona];

  document.getElementById('persona-desc').textContent = data.description;

  const totals = {{ww: 0, coles: 0, aldi: 0}};
  const counts  = {{ww: 0, coles: 0, aldi: 0}};
  for (const item of data.items) {{
    for (const r of RETAILERS) {{
      const cell = item[r];
      if (cell && !cell.na && !cell.notFound && cell.price != null) {{
        totals[r] += cell.price;
        counts[r]++;
      }}
    }}
  }}

  const validRetailers = RETAILERS.filter(r => counts[r] > 0);
  const minTotal = Math.min(...validRetailers.map(r => totals[r]));
  const cardsHTML = RETAILERS.map(r => {{
    const isWinner = totals[r] === minTotal && counts[r] > 0;
    return `<div class="card ${{isWinner ? 'winner' : ''}}">
      <div class="retailer">${{RETAILER_LABELS[r]}}</div>
      <div class="basket-total">${{counts[r] > 0 ? fmt(totals[r]) : '—'}}</div>
      <div class="found">${{counts[r]}}/${{data.items.length}} items</div>
    </div>`;
  }}).join('');
  document.getElementById('summary-cards').innerHTML = cardsHTML;

  const rows = data.items.map(item => {{
    const prices = RETAILERS
      .map(r => ({{ r, p: (item[r] && !item[r].na && !item[r].notFound && item[r].price != null) ? item[r].price : null }}))
      .filter(x => x.p !== null);

    const minPrice = prices.length ? Math.min(...prices.map(x => x.p)) : null;
    const maxPrice = prices.length ? Math.max(...prices.map(x => x.p)) : null;

    const cells = RETAILERS.map(r => {{
      const cell = item[r];
      if (!cell || cell.na || cell.notFound) {{
        const cls = 'na';
        const title = cell && cell.label ? ` title="${{cell.label}}"` : '';
        const note = (cell && cell.notFound) ? '<span class="price-note">not found</span>' : '';
        return `<td class="${{cls}}"${{title}}>—${{note}}</td>`;
      }}
      const price = cell.price;
      let cls = '';
      if (prices.length >= 2 && price !== null) {{
        if (price === minPrice && minPrice < maxPrice) cls = 'cheapest';
        else if (price === maxPrice && minPrice < maxPrice) cls = 'dearest';
      }}
      const special = cell.isSpecial ? ' ⭐' : '';
      const qtyNote = (cell.qty && cell.qty > 1)
        ? `<span class="price-note">(${{cell.qty}}×${{fmt(cell.unitPrice)}}ea)</span>` : '';
      const nameNote = cell.label
        ? `<span class="price-note">${{cell.label}}</span>` : '';
      const specialNote = cell.isSpecial
        ? `<span class="price-note special">⭐ on special</span>` : '';
      return `<td class="${{cls}}"><span class="price-main">${{fmt(price)}}${{special}}</span>${{qtyNote}}${{nameNote}}${{specialNote}}</td>`;
    }}).join('');

    return `<tr>
      <td class="item-name">${{item.name}}</td>
      ${{cells}}
    </tr>`;
  }}).join('');

  const totalCells = RETAILERS.map(r => {{
    if (counts[r] === 0) return `<td class="total">—</td>`;
    const isWinner = totals[r] === minTotal;
    const isDearest = totals[r] === Math.max(...validRetailers.map(x => totals[x]));
    let cls = 'total';
    if (isWinner && validRetailers.length > 1) cls += ' winner';
    else if (isDearest && validRetailers.length > 1) cls += ' dearest-total';
    const naCount = data.items.filter(item => {{
      const c = item[r];
      return c && (c.na || c.notFound);
    }}).length;
    const naNote = naCount > 0 ? `<span class="price-note">${{naCount}} N/A excl.</span>` : '';
    return `<td class="${{cls}}">${{fmt(totals[r])}}${{naNote}}</td>`;
  }}).join('');

  document.getElementById('items-tbody').innerHTML = rows +
    `<tr style="border-top:2px solid var(--border)">
      <td style="font-weight:600;">Basket Total</td>
      ${{totalCells}}
    </tr>`;

  document.getElementById('ww-note').innerHTML =
    `{ww_note}`;
}}

// Initial render
render();
</script>

</body>
</html>
'''

(PUBLIC_DIR / 'bolognese.html').write_text(html)
print(f"  ✓ Written: {PUBLIC_DIR / 'bolognese.html'}")
print(f"  Run date: {run_display} | WW live: {ww_live_count}/{ww_total_count}")
