# Basket Watch 🛒

Weekly online supermarket basket comparison across Woolworths, Coles, ALDI and IGA.

Based on Choice Magazine's 17-item quarterly benchmark basket, re-run weekly using live online prices.

## How it works

- `scripts/generate_site.py` runs the basket tracker, generates `public/index.html` + `data/latest.json`
- Runs every Thursday via cron on Simon's Mac Mini
- Netlify auto-deploys on push to `main`

## Running manually

```bash
python3 scripts/generate_site.py
```

## Architecture

- Woolworths: direct JSON API (no browser)
- Coles: Next.js `_next/data` API (no browser)
- ALDI: browser automation
- IGA: HTTP + `__NEXT_DATA__` scrape

## Methodology

Online prices only — not an in-store survey. Fresh produce priced as sold online (per-each or per-pack).
See the live site for full methodology notes.
