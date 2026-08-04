# Basket Watch — What This Is (Plain English)

*For anyone who isn't going to open a code editor.*

## What it does

Every Thursday, this system automatically checks live online prices at Woolworths, Coles and ALDI for a set of grocery items, and publishes three comparison pages:

1. **Overall basket** — 17 everyday items (Choice Magazine's benchmark basket), tracked weekly to see who's cheapest overall.
2. **CREST segments** — the same 15-item family basket, but priced 5 different ways depending on shopper type: Saver (cheapest home-brand), Essential, Traditional (trusted brands), Refined (premium/free-range), Conscious (organic/ethical). Shows how the "who's cheapest" answer changes depending on who's shopping.
3. **Meal-based basket** — one specific recipe (Spaghetti Bolognese), priced two ways: Traditional shopper vs Saver shopper, across all three retailers.

No humans do the price-checking. A script visits each retailer's site/API, reads the current price, and rebuilds the comparison automatically. It's a working example of **agentic AI doing a real competitive-intelligence job end to end** — not a mockup.

Live pages: basket-watch-au.netlify.app

## What it isn't (yet)

- It's not a general tool anyone can point at any category and get results — it's built around specific, hand-picked SKUs matched across three retailers' sites.
- It's not connected to any Woolworths internal system — it only reads public retailer websites, same as a customer would.
- It's a proof of concept, not a productionised team tool. It runs on Simon's own infrastructure.

## If you want something like this for your category

The interesting part isn't the code — it's the **pattern**: pick a representative basket → match SKUs across competitors → normalise pricing fairly (see note below) → segment by shopper type or use-case → automate the refresh. That pattern can be rebuilt for any category.

To scope a version for **Home & Essential Foods**, here's what would need deciding first:

| Question | Why it matters |
|---|---|
| **Which SKUs represent the category?** | Need a defined "reference basket" — e.g. 15-20 products that a category manager would consider representative, spanning price tiers. |
| **Which competitors matter?** | WW/Coles/ALDI here — but for your category it might also include Costco, Chemist Warehouse, Amazon, etc. |
| **What's the equivalent of "shopper segment"?** | For CREST it was Saver→Conscious. For your category it might be private-label vs branded, or bulk vs single-unit, or a specific use-case basket (like the Bolognese one). |
| **How often does it need refreshing?** | Weekly worked for a general awareness tool. Category management during a promo cycle might want daily. |
| **Where does it need to live?** | A public webpage (like this), or does it feed into an existing category dashboard (Tableau/Power BI/spreadsheet)? |
| **Who owns keeping SKU mappings current?** | Products get delisted, resized, and rebranded constantly — someone needs to own re-verifying the SKU list periodically. |

## The pricing-fairness rule (learned the hard way)

Anything priced by weight (chicken, mince, cheese, etc.) **must be compared on a $/kg basis across all retailers**, not pack price vs pack price — different retailers sell different pack sizes of the "same" product, so raw pack price comparisons are misleading. This was a live bug in an early version and is now enforced as a rule in the underlying tooling. Worth building in from day one for any category variant, especially one with as many by-weight items as Home & Essential Foods likely has.

---

## For Developers — building your own version without OpenClaw

None of this actually depends on OpenClaw. OpenClaw is just what calls these scripts on a schedule; every script is plain Python.

**Fully portable, zero special tooling required:**
- Coles fetching — plain `urllib` HTTP calls to Coles' public Next.js data API (`_next/data/.../search/products.json`). Runs anywhere Python runs.
- CSV → JSON schema building (`build_crest_schema.py`) — pure Python, no external dependencies at all.
- Git + Netlify publishing — fully generic; any machine with `git` installed can do this.

**Needs browser automation, but nothing OpenClaw-specific:**
- ALDI — uses [Playwright](https://playwright.dev) directly (`pip install playwright`), a standard open-source browser automation library. No special access required.
- Woolworths — the one exception. This repo uses `browser-harness`, a small standalone CLI that drives a real Chrome tab over CDP (Chrome DevTools Protocol) specifically to get past Woolworths' Akamai bot-detection, which blocks plain HTTP requests and even blocks some headless-browser fingerprints. A developer without that tool has two options:
  1. Install `browser-harness` independently (it's a standalone package, not bundled inside OpenClaw), or
  2. Rewrite the WW fetch using plain Playwright with a real (non-headless) browser profile, the same pattern used for ALDI — more fragile against Akamai, but workable, especially at low request volumes.

**What's actually OpenClaw-specific: just the scheduling.**
The only OpenClaw-dependent piece is the trigger that runs `python3 script.py && python3 script2.py && git push` every Thursday morning. Anyone rebuilding this without OpenClaw has two straightforward alternatives:
- A plain `cron` entry on any machine that's reliably powered on, or
- A **GitHub Actions scheduled workflow** (`on: schedule`) — free for public repos, runs entirely on GitHub's infrastructure, no local machine required at all. Probably the easiest option for a category team without a dedicated always-on server.

**Bottom line for a developer inheriting this:** the pattern is 100% forkable — fetch script per retailer → normalise to a common unit basis (see pricing-fairness rule above) → render to static HTML → push → auto-deploy. Swap in your category's SKUs, swap Woolworths' fetch method if Akamai is a blocker, and point the scheduler at GitHub Actions instead of a personal cron job.
