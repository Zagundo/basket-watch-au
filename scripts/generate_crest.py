#!/usr/bin/env python3
"""
CREST Basket Page Generator
Reads crest_basket_latest.json → writes public/crest.html
"""
import json, re, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

REPO_DIR   = Path(__file__).parent.parent
DATA_PATH  = Path('/Users/simontracey/.openclaw/workspace/BasketWatch/crest_basket_latest.json')
OUTPUT     = REPO_DIR / 'public' / 'crest.html'
AEST       = ZoneInfo('Australia/Sydney')

basket = json.loads(DATA_PATH.read_text())

SEGMENTS = basket['segments']
STORES   = basket['stores']
CATS     = basket['categories']
totals   = basket['totals']
items    = basket['basket']

run_date = basket.get('run_date', '')
# Parse and reformat date
try:
    dt = datetime.strptime(run_date, '%Y-%m-%d %H:%M UTC')
    dt_aest = dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(AEST)
    run_display = dt_aest.strftime('%A %-d %B %Y')
except Exception:
    run_display = run_date

SEGMENT_DESC = {
    'Saver':       'Own-brand focus — best value, no-frills choices across all categories.',
    'Essential':   'Budget-conscious staples — reliable home-brand products for everyday needs.',
    'Traditional': 'Brand-loyal shoppers — trusted household names like Cheer, McCain and Twinings.',
    'Refined':     'Quality seekers — free-range, premium-tier products (Macro, Abbott\'s, Barilla).',
    'Conscious':   'Values-driven — organic, ethical and free-range choices where available.',
}

STORE_COLOR = {
    'Woolworths': '#007837',
    'Coles':      '#e01523',
    'Aldi':       '#004f9f',
}
STORE_EMOJI = {'Woolworths': '🟢', 'Coles': '🔴', 'Aldi': '🔵'}

def fmt(price, red=False):
    if price is None:
        return '<span class="na">—</span>'
    s = f'${price:.2f}'
    if red:
        return f'<span class="proxy-price">{s}*</span>'
    return s

def build_segment_data():
    """Build JS data blob embedded in page."""
    out = {}
    for seg in SEGMENTS:
        seg_totals = totals[seg]
        winner_store = min(STORES, key=lambda s: seg_totals[s]['total'])
        out[seg] = {
            'totals': {s: seg_totals[s]['total'] for s in STORES},
            'winner': winner_store,
            'ww_proxy_count': {s: seg_totals[s].get('ww_proxy_count', 0) for s in STORES},
            'rows': [],
        }
        for cat in CATS:
            row = {'cat': cat, 'prices': {}}
            for store in STORES:
                item = items.get(seg, {}).get(cat, {}).get(store, {})
                ep = item.get('evaluated_price')
                row['prices'][store] = {
                    'price':     ep,
                    'sku':       item.get('sku', ''),
                    'url':       item.get('url'),
                    'is_special':item.get('is_special', False),
                    'ww_proxy':  item.get('ww_proxy', False),
                    'cup':       item.get('cup_string'),
                    'qty':       item.get('qty', 1),
                }
            # Find cheapest price for this row
            prices = [row['prices'][s]['price'] for s in STORES if row['prices'][s]['price'] is not None]
            row['min_price'] = min(prices) if prices else None
            row['max_price'] = max(prices) if prices else None
            out[seg]['rows'].append(row)
    return json.dumps(out, ensure_ascii=False)

js_data = build_segment_data()

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Basket Watch — CREST Family Basket Comparison</title>
<meta name="description" content="How Australian supermarket prices vary by shopper type. Comparing Woolworths, Coles and ALDI across five CREST customer segments.">
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
    --proxy-bg:    #fff3cd;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }}
  header {{ background: var(--text); color: #fff; padding: 1.5rem 1rem; text-align: center; }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
  header p  {{ color: #adb5bd; font-size: 0.9rem; margin-top: 0.25rem; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem; }}
  .back-link {{ display: inline-block; font-size: 0.85rem; color: var(--muted); text-decoration: none; margin-bottom: 1.25rem; }}
  .back-link:hover {{ color: var(--text); }}

  /* ── Segment toggle ── */
  .seg-toggle {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.75rem; }}
  .seg-btn {{
    padding: 0.5rem 1.1rem; border-radius: 999px; border: 2px solid var(--border);
    background: var(--card); color: var(--muted); font-size: 0.88rem; font-weight: 600;
    cursor: pointer; transition: all 0.15s;
  }}
  .seg-btn:hover {{ border-color: var(--text); color: var(--text); }}
  .seg-btn.active {{ background: var(--text); border-color: var(--text); color: #fff; }}
  .seg-desc {{ font-size: 0.88rem; color: var(--muted); margin-bottom: 1.25rem; min-height: 1.4em; }}

  /* ── Hero cards ── */
  .hero {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--card); border-radius: 10px; padding: 1rem; border: 1px solid var(--border); text-align: center; }}
  .card.winner {{ border-color: var(--green); box-shadow: 0 0 0 2px var(--green); }}
  .card .retailer {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.25rem; }}
  .card .basket-total {{ font-size: 1.9rem; font-weight: 700; }}
  .card .badge {{ font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; padding: 0.1rem 0.5rem; border-radius: 999px; display: inline-block; margin-top: 0.4rem; }}
  .badge.cheapest {{ background: var(--cheapest-bg); color: #155724; }}
  .badge.dearest  {{ background: var(--dearest-bg);  color: #721c24; }}
  .card .proxy-note {{ font-size: 0.72rem; color: var(--muted); margin-top: 0.25rem; }}

  /* ── Item table ── */
  h2 {{ font-size: 1.05rem; font-weight: 600; margin: 1.5rem 0 0.75rem; }}
  .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); background: var(--card); margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{ background: var(--text); color: #fff; padding: 0.6rem 0.75rem; text-align: center; font-weight: 600; font-size: 0.8rem; }}
  th:first-child {{ text-align: left; width: 36%; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: center; vertical-align: top; }}
  td:first-child {{ text-align: left; font-size: 0.85rem; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f1f3f5; }}
  td.price {{ font-variant-numeric: tabular-nums; font-weight: 500; }}
  td.cheapest {{ background: var(--cheapest-bg); font-weight: 700; }}
  td.dearest  {{ background: var(--dearest-bg); }}
  td.total-row {{ font-weight: 700; font-size: 1rem; border-top: 2px solid var(--border); }}
  td.total-row.winner {{ background: var(--cheapest-bg); }}
  td.total-row.dearest {{ background: var(--dearest-bg); }}
  .sku-name {{ font-size: 0.78rem; color: var(--muted); display: block; margin-top: 0.1rem; max-width: 200px; }}
  .special-tag {{ font-size: 0.68rem; color: var(--green); font-weight: 600; display: block; }}
  span.proxy-price {{ color: var(--red); font-weight: 600; }}
  .proxy-asterisk {{ font-size: 0.72rem; color: var(--muted); display: block; }}

  /* ── Methodology note ── */
  .methodology {{ background: var(--card); border-radius: 10px; padding: 1rem 1.25rem; border: 1px solid var(--border); font-size: 0.82rem; color: var(--muted); margin-bottom: 1.5rem; }}
  .methodology h3 {{ font-size: 0.9rem; color: var(--text); margin-bottom: 0.5rem; }}
  .methodology li {{ margin-left: 1.2rem; margin-bottom: 0.25rem; line-height: 1.4; }}

  /* ── Legend ── */
  .legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.75rem; align-items: center; }}
  .dot {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; margin-right: 3px; }}
  .dot-cheap {{ background: var(--cheapest-bg); border: 1px solid #a8d5b5; }}
  .dot-dear  {{ background: var(--dearest-bg);  border: 1px solid #f5c2c7; }}

  footer {{ text-align: center; padding: 2rem 1rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
  footer a {{ color: var(--muted); }}
</style>
</head>
<body>

<header>
  <h1>🛒 Basket Watch — CREST</h1>
  <p>15-item family basket &bull; Five shopper segments &bull; Woolworths vs Coles vs ALDI</p>
</header>

<div class="container">
  <a class="back-link" href="index.html">← Back to Basket Watch</a>

  <div class="seg-toggle" id="segToggle">
    {''.join(f'<button class="seg-btn{" active" if i==0 else ""}" data-seg="{seg}" onclick="setSeg(this)">{seg}</button>' for i,seg in enumerate(SEGMENTS))}
  </div>
  <p class="seg-desc" id="segDesc">{SEGMENT_DESC[SEGMENTS[0]]}</p>

  <!-- Hero totals -->
  <div class="hero" id="heroCards"><!-- rendered by JS --></div>

  <!-- Item breakdown -->
  <h2>Item breakdown</h2>
  <div class="legend">
    <span><span class="dot dot-cheap"></span> Cheapest</span>
    <span><span class="dot dot-dear"></span> Most expensive</span>
    <span style="color:var(--red);font-weight:600;">$x.xx*</span><span>&nbsp;Aldi N/A — Woolworths price used</span>
  </div>
  <div class="table-wrap">
    <table id="itemTable">
      <thead>
        <tr>
          <th>Category</th>
          <th>🟢 Woolworths</th>
          <th>🔴 Coles</th>
          <th>🔵 ALDI</th>
        </tr>
      </thead>
      <tbody id="itemBody"><!-- rendered by JS --></tbody>
    </table>
  </div>

  <div class="methodology">
    <h3>Methodology</h3>
    <ul>
      <li><strong>15-category family basket</strong> priced online across Woolworths, Coles and ALDI.</li>
      <li><strong>CREST segments</strong> reflect different shopper philosophies: Saver and Essential use home-brand; Traditional uses trusted household names; Refined and Conscious use premium and ethically-sourced products.</li>
      <li><strong>ALDI N/A items</strong> (shown in red*): where ALDI doesn't stock an equivalent product, the Woolworths regular price is used. This reflects the real cost to the shopper — they'd need to visit WW to complete the basket.</li>
      <li><strong>Variable-weight items</strong> (chicken breast) are normalised to a per-kg price using the in-store cup price.</li>
      <li><strong>Prices are live</strong> — fetched directly from retailer websites on {run_display}. Sale prices use the regular (was) price for fairness.</li>
    </ul>
  </div>
</div>

<footer>
  <p>Data fetched {run_display} &bull; <a href="index.html">Basket Watch</a> &bull; Not affiliated with any retailer</p>
</footer>

<script>
const DATA = {js_data};
const SEGS = {json.dumps(SEGMENTS)};
const STORES = {json.dumps(STORES)};
const CATS = {json.dumps(CATS)};
const DESCS = {json.dumps(SEGMENT_DESC)};
const STORE_COLORS = {json.dumps(STORE_COLOR)};

let activeSeg = SEGS[0];

function setSeg(btn) {{
  document.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeSeg = btn.dataset.seg;
  document.getElementById('segDesc').textContent = DESCS[activeSeg];
  render();
}}

function render() {{
  const d = DATA[activeSeg];
  const winner = d.winner;
  const loser  = STORES.reduce((a,s) => d.totals[s] > d.totals[a] ? s : a, STORES[0]);

  // Hero cards
  const hero = document.getElementById('heroCards');
  hero.innerHTML = STORES.map(store => {{
    const total = d.totals[store];
    const isWinner = store === winner;
    const isLoser  = store === loser && store !== winner;
    const proxyCt  = d.ww_proxy_count[store] || 0;
    const diff     = (total - d.totals[winner]).toFixed(2);
    let badge = '';
    if (isWinner) badge = '<span class="badge cheapest">✓ Cheapest</span>';
    else if (isLoser) badge = '<span class="badge dearest">Most expensive</span>';
    let proxyNote = proxyCt > 0 ? `<div class="proxy-note">Incl. ${{proxyCt}} WW price(s) for missing Aldi items</div>` : '';
    let diffTxt = !isWinner ? `<div style="font-size:0.82rem;color:#c0392b;margin-top:0.2rem">+${{diff}} vs WW</div>` : '';
    return `<div class="card${{isWinner ? ' winner' : ''}}">
      <div class="retailer">${{store}}</div>
      <div class="basket-total">$${{total.toFixed(2)}}</div>
      ${{badge}}${{diffTxt}}${{proxyNote}}
    </div>`;
  }}).join('');

  // Item table
  const tbody = document.getElementById('itemBody');
  const rows = d.rows.map(row => {{
    const cells = STORES.map(store => {{
      const p = row.prices[store];
      if (p.price === null || p.price === undefined) return `<td class="price na">—</td>`;
      const isMin = Math.abs(p.price - row.min_price) < 0.005;
      const isMax = Math.abs(p.price - row.max_price) < 0.005 && row.max_price > row.min_price;
      const cls = isMin ? ' cheapest' : (isMax ? ' dearest' : '');
      const special = p.is_special ? `<span class="special-tag">🏷 On special</span>` : '';
      const skuName = p.sku && p.sku !== 'N/A' ? `<span class="sku-name">${{p.sku.replace(/[|]/g,'').trim()}}</span>` : '';
      const priceStr = p.ww_proxy
        ? `<span class="proxy-price">$${{p.price.toFixed(2)}}*</span>`
        : `$${{p.price.toFixed(2)}}`;
      return `<td class="price${{cls}}">${{priceStr}}${{special}}${{skuName}}</td>`;
    }}).join('');
    return `<tr><td>${{row.cat}}</td>${{cells}}</tr>`;
  }}).join('');

  // Totals row
  const totCells = STORES.map(store => {{
    const t = d.totals[store];
    const isWinner = store === winner;
    const isLoser  = store === loser && store !== winner;
    const cls = isWinner ? ' winner' : (isLoser ? ' dearest' : '');
    return `<td class="total-row${{cls}}">$${{t.toFixed(2)}}</td>`;
  }}).join('');
  tbody.innerHTML = rows + `<tr><td class="total-row"><strong>Total</strong></td>${{totCells}}</tr>`;
}}

render();
</script>
</body>
</html>'''

OUTPUT.write_text(html)
print(f"✓ Written: {OUTPUT}")
print(f"  Segments: {len(SEGMENTS)} | Categories: {len(CATS)} | Run date: {run_display}")
