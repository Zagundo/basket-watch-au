#!/usr/bin/env python3
"""
Basket Watch — Site Generator
Runs basket_tracker_v2.py, writes results to data/latest.json,
then renders public/index.html from the results.

Run manually:
  python3 scripts/generate_site.py

Called by cron each Thursday:
  0 7 * * 4 python3 /Users/simontracey/basket-watch-au/scripts/generate_site.py >> /tmp/basket-watch-cron.log 2>&1
"""

import sys, json, subprocess, os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_DIR   = Path(__file__).parent.parent
DATA_DIR   = REPO_DIR / 'data'
PUBLIC_DIR = REPO_DIR / 'public'
TRACKER    = Path('/Users/simontracey/.openclaw/workspace/skills/grocery-compare/scripts/basket_tracker_v2.py')
AEST       = ZoneInfo('Australia/Sydney')

DATA_DIR.mkdir(exist_ok=True)
PUBLIC_DIR.mkdir(exist_ok=True)

# ── Run the basket tracker ────────────────────────────────
print(f"[{datetime.now(AEST).strftime('%Y-%m-%d %H:%M %Z')}] Running basket tracker...")
subprocess.run(['python3', str(TRACKER)], timeout=300)
raw = json.loads(Path('/tmp/basket-tracker-v2-latest.json').read_text())

run_date_utc = raw.get('run_date', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
results      = raw.get('results', {})

# ── Write data/latest.json ────────────────────────────────
(DATA_DIR / 'latest.json').write_text(json.dumps(raw, indent=2))
print(f"  ✓ data/latest.json written")

# ── Compute display data ──────────────────────────────────
BASKET_IDS = [
    'chicken_breast','carrots','apples','bananas','strawberries','blueberries',
    'milk','yoghurt','cheese_slices','ham','weetbix','sultanas','chips',
    'tuna','bread','vegemite','cucumbers'
]
BASKET_NAMES = {
    'chicken_breast': 'Chicken Breast ~1kg',
    'carrots':        'Carrots 1kg',
    'apples':         'Royal Gala Apples 1kg',
    'bananas':        'Bananas ×5 each',
    'strawberries':   'Strawberries 250g',
    'blueberries':    'Blueberries 125g',
    'milk':           'Full Cream Milk 2L',
    'yoghurt':        'Vaalia Kids Yoghurt 140g',
    'cheese_slices':  'Bega Tasty Cheese Slices 500g',
    'ham':            'Primo Leg Ham 100g',
    'weetbix':        'Sanitarium Weet-Bix 375g',
    'sultanas':       'Sunbeam Sultanas 6-pack',
    'chips':          'Variety Chips Multipack 20pk',
    'tuna':           'Sirena Tuna in Oil 425g',
    'bread':          'Tip Top Wholemeal Bread 700g',
    'vegemite':       'Vegemite 380g',
    'cucumbers':      'Baby Cucumbers 250g',
}
BASKET_QTY = {'bananas': 5}
RETAILERS = [
    ('woolworths', '🟢', 'Woolworths'),
    ('coles',      '🔴', 'Coles'),
    ('aldi',       '🟡', 'ALDI'),
    ('iga',        '🔵', 'IGA'),
]
CHOICE_BENCHMARK = {
    'woolworths': 90.08, 'coles': 90.90, 'aldi': 75.98, 'iga': 101.84
}

totals = {}
for rid, _, _ in RETAILERS:
    items = results.get(rid, {})
    qty_map = BASKET_QTY
    total = 0
    found = 0
    specials = 0
    for iid in BASKET_IDS:
        v = items.get(iid)
        if v and v.get('price') and not v.get('inStoreOnly') and not v.get('weightedOnly') and not v.get('notListed'):
            qty = 1 if v.get('qty_override') else qty_map.get(iid, 1)
            total += v['price'] * qty
            found += 1
            if v.get('isSpecial'):
                specials += 1
    totals[rid] = {'total': round(total, 2), 'found': found, 'specials': specials}

run_dt = datetime.now(AEST)
run_display = run_dt.strftime('%-d %B %Y')

# ── Render HTML ───────────────────────────────────────────
def eff_qty(v, iid):
    """Effective qty — respects qty_override for banana-calc items."""
    if v and v.get('qty_override'):
        return 1
    return BASKET_QTY.get(iid, 1)

def eff_price(v, iid):
    if not v or not v.get('price'):
        return None
    return round(v['price'] * eff_qty(v, iid), 2)

def price_cell(rid, iid):
    v = (results.get(rid) or {}).get(iid)
    if not v:
        return '<td class="na">—</td>'
    if v.get('inStoreOnly'):
        return '<td class="na" title="In-store only">🏪</td>'
    if v.get('weightedOnly') or v.get('notListed'):
        return '<td class="na" title="Not listed online">—</td>'
    if not v.get('price'):
        return '<td class="na">—</td>'
    price = eff_price(v, iid)
    special = ' <span class="special" title="On special">⭐</span>' if v.get('isSpecial') else ''
    return f'<td class="price">${price:.2f}{special}</td>'

def total_row():
    cells = ''
    sorted_r = sorted(RETAILERS, key=lambda x: totals[x[0]]['total'])
    winner = sorted_r[0][0]
    for rid, emoji, label in RETAILERS:
        t = totals[rid]
        bench = CHOICE_BENCHMARK.get(rid, 0)
        diff = t['total'] - bench
        diff_str = f'▲${diff:.2f}' if diff > 0 else f'▼${abs(diff):.2f}'
        diff_cls = 'up' if diff > 0 else 'down'
        winner_cls = ' winner' if rid == winner else ''
        cells += f'<td class="total{winner_cls}">${t["total"]:.2f}<br><span class="bench {diff_cls}">{diff_str} vs Dec \'25</span></td>'
    return cells

rows = ''
for iid in BASKET_IDS:
    name = BASKET_NAMES.get(iid, iid)
    row = f'<tr><td class="item-name">{name}</td>'
    prices = []
    for rid, _, _ in RETAILERS:
        v = (results.get(rid) or {}).get(iid)
        if v and v.get('price') and not v.get('inStoreOnly') and not v.get('weightedOnly') and not v.get('notListed'):
            ep = eff_price(v, iid)
            if ep: prices.append((rid, ep))
    if prices:
        min_price = min(p for _, p in prices)
        max_price = max(p for _, p in prices)
    else:
        min_price = max_price = None
    for rid, _, _ in RETAILERS:
        v = (results.get(rid) or {}).get(iid)
        if not v:
            row += '<td class="na">—</td>'
        elif v.get('inStoreOnly'):
            row += '<td class="na" title="In-store only">🏪</td>'
        elif v.get('weightedOnly') or v.get('notListed'):
            row += '<td class="na" title="Not listed online">—</td>'
        elif not v.get('price'):
            row += '<td class="na">—</td>'
        else:
            price = eff_price(v, iid)
            special = ' <span class="special">⭐</span>' if v.get('isSpecial') else ''
            cheapest = ' cheapest' if min_price and price == min_price and min_price < max_price else ''
            dearest  = ' dearest'  if max_price and price == max_price and min_price < max_price else ''
            row += f'<td class="price{cheapest}{dearest}">${price:.2f}{special}</td>'
    row += '</tr>'
    rows += row

sorted_totals = sorted(RETAILERS, key=lambda x: totals[x[0]]['total'])
cheapest_r, cheapest_emoji, cheapest_label = sorted_totals[0]
dearest_r,  dearest_emoji,  dearest_label  = sorted_totals[-1]
saving = totals[dearest_r]['total'] - totals[cheapest_r]['total']

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Basket Watch — Weekly Online Supermarket Comparison</title>
<meta name="description" content="Weekly online supermarket basket comparison across Woolworths, Coles, ALDI and IGA. Updated every Thursday.">
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
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }}
  header {{ background: var(--text); color: #fff; padding: 1.5rem 1rem; text-align: center; }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
  header p {{ color: #adb5bd; font-size: 0.9rem; margin-top: 0.25rem; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
  .hero {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
  @media (min-width: 600px) {{ .hero {{ grid-template-columns: repeat(4, 1fr); }} }}
  .card {{ background: var(--card); border-radius: 10px; padding: 1rem; border: 1px solid var(--border); text-align: center; }}
  .card.winner {{ border-color: var(--green); box-shadow: 0 0 0 2px var(--green); }}
  .card .retailer {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.25rem; }}
  .card .basket-total {{ font-size: 1.8rem; font-weight: 700; }}
  .card .found {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }}
  .card .diff {{ font-size: 0.8rem; margin-top: 0.3rem; }}
  .card .diff.up {{ color: #c0392b; }}
  .card .diff.down {{ color: var(--green); }}
  .summary {{ background: var(--card); border-radius: 10px; padding: 1rem 1.25rem; border: 1px solid var(--border); margin-bottom: 1.5rem; font-size: 0.95rem; }}
  .summary strong {{ color: var(--green); }}
  h2 {{ font-size: 1.1rem; font-weight: 600; margin: 1.5rem 0 0.75rem; }}
  .table-wrap {{ overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); background: var(--card); margin-bottom: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{ background: var(--text); color: #fff; padding: 0.6rem 0.75rem; text-align: center; font-weight: 600; font-size: 0.8rem; }}
  th:first-child {{ text-align: left; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: center; }}
  td:first-child {{ text-align: left; font-size: 0.85rem; color: var(--text); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f1f3f5; }}
  td.price {{ font-variant-numeric: tabular-nums; }}
  td.na {{ color: var(--muted); font-size: 0.8rem; }}
  td.cheapest {{ background: var(--cheapest-bg); font-weight: 600; }}
  td.dearest  {{ background: var(--dearest-bg); }}
  td.total {{ font-weight: 700; font-size: 1rem; vertical-align: middle; }}
  td.total.winner {{ background: var(--cheapest-bg); }}
  .bench {{ font-size: 0.7rem; font-weight: 400; display: block; }}
  .bench.up {{ color: #c0392b; }}
  .bench.down {{ color: var(--green); }}
  span.special {{ font-size: 0.7rem; }}
  .methodology {{ background: var(--card); border-radius: 10px; padding: 1rem 1.25rem; border: 1px solid var(--border); font-size: 0.82rem; color: var(--muted); margin-bottom: 1.5rem; }}
  .methodology h3 {{ font-size: 0.9rem; color: var(--text); margin-bottom: 0.5rem; }}
  .methodology li {{ margin-left: 1.2rem; margin-bottom: 0.2rem; }}
  footer {{ text-align: center; padding: 2rem 1rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
  footer a {{ color: var(--muted); }}
  .legend {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.75rem; }}
  .legend span {{ display: flex; align-items: center; gap: 0.3rem; }}
  .dot-cheap {{ width: 10px; height: 10px; border-radius: 2px; background: var(--cheapest-bg); border: 1px solid #a8d5b5; display: inline-block; }}
  .dot-dear  {{ width: 10px; height: 10px; border-radius: 2px; background: var(--dearest-bg); border: 1px solid #f5c2c7; display: inline-block; }}
</style>
</head>
<body>

<header>
  <h1>🛒 Basket Watch</h1>
  <p>Weekly online supermarket basket comparison &mdash; updated every Thursday</p>
</header>

<div class="container">

  <div class="hero">
    {''.join(f"""<div class="card {'winner' if rid == cheapest_r else ''}">
      <div class="retailer">{emoji} {label}</div>
      <div class="basket-total">${totals[rid]['total']:.2f}</div>
      <div class="found">{totals[rid]['found']}/17 items</div>
      <div class="diff {'down' if totals[rid]['total'] - CHOICE_BENCHMARK[rid] < 0 else 'up'}">
        {'▲' if totals[rid]['total'] - CHOICE_BENCHMARK[rid] > 0 else '▼'}${abs(totals[rid]['total'] - CHOICE_BENCHMARK[rid]):.2f} vs Dec '25
      </div>
    </div>""" for rid, emoji, label in RETAILERS)}
  </div>

  <div class="summary">
    {cheapest_emoji} <strong>{cheapest_label}</strong> is cheapest this week at <strong>${totals[cheapest_r]['total']:.2f}</strong> &mdash;
    save <strong>${saving:.2f}</strong> vs {dearest_emoji} {dearest_label} (${totals[dearest_r]['total']:.2f}).
    &nbsp; Run: {run_display}.
  </div>

  <h2>Item-by-item breakdown</h2>

  <div class="legend">
    <span><span class="dot-cheap"></span> Cheapest this week</span>
    <span><span class="dot-dear"></span> Most expensive</span>
    <span>⭐ On special</span>
    <span>— Not listed online</span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>🟢 Woolworths</th>
          <th>🔴 Coles</th>
          <th>🟡 ALDI</th>
          <th>🔵 IGA</th>
        </tr>
      </thead>
      <tbody>
        {rows}
        <tr style="border-top: 2px solid var(--border);">
          <td style="font-weight:600;">Basket Total</td>
          {total_row()}
        </tr>
      </tbody>
    </table>
  </div>

  <div class="methodology">
    <h3>About this data</h3>
    <ul>
      <li>17-item basket based on Choice Magazine's quarterly supermarket benchmark</li>
      <li>Prices are <strong>online prices</strong> as at {run_display} — may differ from in-store</li>
      <li>Fresh produce priced as sold online (per-each or per-pack, not per-kg)</li>
      <li>Bananas: ×5 each — Woolworths, Coles &amp; ALDI priced per-each; IGA priced per-kg (×900g equivalent)</li>
      <li>Variable-weight items (chicken breast) shown at per-kg price for like-for-like comparison</li>
      <li>— = product not listed in online store (e.g. IGA strawberries)</li>
      <li>⭐ = item was on special at time of capture</li>
      <li>Choice benchmark: ALDI $75.98 · Woolworths $90.08 · Coles $90.90 · IGA $101.84 (Dec 2025)</li>
    </ul>
  </div>

</div>

<footer>
  <p>Basket Watch &mdash; built by <a href="https://sjtracey.com">Simon Tracey</a> &mdash; data captured {run_display}</p>
  <p style="margin-top:0.4rem;">Prices are online prices only. Not affiliated with any supermarket.</p>
</footer>

</body>
</html>"""

(PUBLIC_DIR / 'index.html').write_text(html)
print(f"  ✓ public/index.html written")

# ── Git commit and push ───────────────────────────────────
import subprocess as sp
repo = str(REPO_DIR)
sp.run(['git', '-C', repo, 'add', '-A'], check=True)
sp.run(['git', '-C', repo, 'commit', '-m', f'Basket Watch update — {run_display}'], check=True)
sp.run(['git', '-C', repo, 'push', 'origin', 'main'], check=True)
print(f"  ✓ Pushed to GitHub")
print(f"\n✅ Basket Watch site updated — {run_display}")
