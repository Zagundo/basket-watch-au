# Basket Watch 🛒

Weekly online supermarket basket comparison across Woolworths, Coles and ALDI (plus IGA on the main basket).

Three baskets, each answering a different question:

| Page | Basket | Question it answers |
|---|---|---|
| [`/`](https://basket-watch-au.netlify.app/) | 17-item Choice Magazine benchmark basket | Who's cheapest overall this week — WW, Coles, ALDI, IGA? |
| [`/crest.html`](https://basket-watch-au.netlify.app/crest.html) | 15-item "Choice Family" basket × 5 CREST shopper segments | How does the answer change by shopper type — Saver, Essential, Traditional, Refined, Conscious? |
| [`/bolognese.html`](https://basket-watch-au.netlify.app/bolognese.html) | 10-item Spaghetti Bolognese meal basket | What does one specific meal cost, Traditional (brand-loyal) vs Saver (own-brand)? |

Based on Choice Magazine's quarterly supermarket benchmark, re-run weekly using **live online prices** (not an in-store survey).

## How it works

All three run automatically every **Thursday 7am** via a single cron job on Simon's Mac Mini:

1. `scripts/generate_site.py` — runs the main basket tracker, writes `public/index.html` + `data/latest.json`
2. `../BasketWatch/fetch_crest_prices.py` — fetches live prices for the CREST basket's ~27 unique WW/Coles/ALDI products
3. `../BasketWatch/build_crest_schema.py` — maps live prices onto the 5-segment CSV structure, computes per-segment totals
4. `scripts/generate_crest.py` — renders `public/crest.html` from the CREST schema
5. `scripts/generate_bolognese.py` — runs the persona basket tracker (Traditional/Saver × 3 retailers), renders `public/bolognese.html`
6. Git commit + push → Netlify auto-deploys on push to `main`
7. A visual sanity check runs against the rendered pages (Gemma4 vision model) before the run is considered complete

## Running manually

```bash
# Main basket
python3 scripts/generate_site.py

# CREST basket (segments)
python3 ../.openclaw/workspace/BasketWatch/fetch_crest_prices.py
python3 ../.openclaw/workspace/BasketWatch/build_crest_schema.py
python3 scripts/generate_crest.py

# Bolognese basket (personas)
python3 scripts/generate_bolognese.py
```

## Architecture

- **Woolworths**: Chrome CDP browser harness (bypasses Akamai bot protection) — falls back to direct JSON API where possible
- **Coles**: Next.js `_next/data` API (no browser needed)
- **ALDI**: HTTP fetch + JSON-LD product schema scraping
- **IGA** (main basket only): HTTP + `__NEXT_DATA__` scrape

## Methodology

- Online prices only — not an in-store survey. Fresh produce priced as sold online (per-each or per-pack).
- **Variable-weight items are always compared on a normalised $/kg basis.** For categories like chicken breast, beef mince, cheese, carrots, onions, apples, frozen peas and tinned tomatoes, every retailer's unit price is extracted from its own unit-pricing string (e.g. Woolworths `CupString`, Coles `pricing.unit.price`, ALDI's on-page "$X.XX per 1 kg") rather than multiplying pack price × quantity. This avoids comparing a per-kg price at one retailer against a differently-sized pack price at another.
- CREST segments (Saver / Essential / Traditional / Refined / Conscious) map each grocery category to a different product tier per shopper archetype — e.g. Saver buys home-brand, Refined buys free-range/organic.
- ⭐ = item on special at time of capture. Red/asterisked prices on the CREST page indicate a WW-proxy price used where ALDI has no equivalent product for that segment.
- See each live page for full per-basket methodology notes.

## Repo layout

```
basket-watch-au/
├── public/              # rendered HTML — what Netlify serves
│   ├── index.html       # main basket
│   ├── crest.html       # CREST segments basket
│   └── bolognese.html   # Bolognese persona basket
├── data/latest.json     # raw main-basket data
├── scripts/
│   ├── generate_site.py       # main basket generator (runs tracker + renders + commits/pushes)
│   ├── generate_crest.py      # renders crest.html from crest_basket_latest.json
│   └── generate_bolognese.py  # runs persona tracker + renders bolognese.html
└── netlify.toml
```

The CREST fetch/schema scripts (`fetch_crest_prices.py`, `build_crest_schema.py`) and the underlying basket configs (`basket_tracker_v2.py`, `bolognese_basket.json`, `persona_basket_tracker.py`) live outside this repo in Simon's OpenClaw workspace, since they're shared with other grocery-comparison tooling.
