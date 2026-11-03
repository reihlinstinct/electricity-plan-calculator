# iec-calc — electricity-plan-calculator

Analyze an **Israel Electric Corp (IEC) consumption export** (the hourly /
15-minute CSV from the IEC website) and rank every electricity plan available
in Israel — the regulated flat tariff, regulated time-of-use (תעו"ז / Taoz),
and all private supplier discount plans — by **your actual usage**, with
annual NIS cost estimates. The most worthwhile plan is marked in the output.

## Install

```sh
pip install .
# dev (tests, lint, audit):
pip install -e '.[dev]'
```

## Quickstart

New to the IEC export? `docs/download-iec-csv.md` is an illustrated Hebrew guide (also available as a page on the site).

```sh
iec-calc report path/to/your-iec-export.csv            # analysis + plan ranking + insights
#                                                       (observations only: peak hours, baseline,
#                                                       Taoz peak share, probabilistic appliance
#                                                       signatures - no causal claims)
iec-calc analyze path/to/your-iec-export.csv           # consumption profile only
iec-calc analyze path/to/your-iec-export.csv --weather # + temperature sensitivity
iec-calc plans  path/to/your-iec-export.csv            # plan ranking only
iec-calc --debug report export.csv                     # diagnostic logging (off by default)
```

Try it on the synthetic sample: `iec-calc report data/sample_consumption.csv`

## Useful flags

- `--lang {he,en,ar,ru,am}` - output language (default: he). The web page switches with `?lang=` instead
- `--phase {single,three}` - meter phase for the fixed-fee calculation (default: single)
- `--no-smart-meter` - exclude smart-meter plans; `--gas` / `--hot` - OPT IN to gas-customer (Amisragas) / HOT-customer plans (excluded by default)
- `--current-plan LABEL` - mark your current plan (substring match; flat tariff and Taoz
  labels work too) and see the top plan's saving versus it
- `--weather` [--lat/--lon] - opt-in (off by default, makes a network call to Open-Meteo);
  an experimental temperature-sensitivity estimate only - never used in the plan ranking,
  plus a cooling/heating degree-day split with per-month attribution
- `--cooling-base` / `--heating-base` - degree-day base temperatures (defaults: 22/18 C)

## What you get

- **Consumption profile**: totals, daily/hourly shape, base load, peak,
  night vs day, weekday vs Fri-Sat, anomaly days, annualized estimate.
- **Weather sensitivity** (optional, Open-Meteo): correlation and
  kWh-per-degree with the weekend effect controlled.
- **Plan ranking**: annual cost for the flat tariff, Taoz, and all 20
  private supplier plans, computed interval-by-interval from your data,
  cheapest first. Discount windows follow Israeli conventions
  (workdays = Sunday-Thursday; night windows wrap midnight).

## MCP server

`iec-calc-mcp` exposes the same engine to MCP clients over stdio (newline-delimited JSON-RPC, protocol 2025-06-18, no dependencies). Tools: `analyze_csv`, `rank_plans`, `explain_insights` - each takes a local CSV path; nothing is sent anywhere or retained. Conditional plans stay off unless `gas`/`hot` are passed, and the weather estimate stays an opt-in (`weather: true` on `analyze_csv`, experimental, one Open-Meteo call). It reads any path the caller gives (no allowlist; error text echoes that path back) and inherits the launching client's filesystem permissions - launch it only from a trusted local MCP client. Design notes: `docs/mcp-design.md`. No registry publishing.

## Tariff data

All rates, discounts, eligibility notes, source URLs and verification dates
live in [`data/tariffs.json`](data/tariffs.json). Updating prices = editing
that one file. Sources: Electricity Authority tariff book (January 2026),
IEC/EA cross-checks, and supplier-site-verified plan data (2026-09-27).

## Privacy

- Real exports are never committed: `.gitignore` excludes `*.csv`;
  `data/sample_consumption.csv` is synthetic and whitelisted.
- CI runs `scripts/privacy_scan.sh`, which fails on contract-number and
  meter-id patterns and on customer metadata outside the sample.
- Customer metadata (name/address/contract/meter) is never printed or logged.

## CSV input

The CLI and browser share synthetic conformance cases in
`tests/fixtures/parser_cases.json`. The browser reads quoted CSV records
(including commas, escaped quotes and embedded newlines), ignores metadata and
non-consumption rows, accepts an omitted feed-in column, rejects impossible
calendar dates and sorts intervals. Valid `24:00` means next-day midnight;
other invalid clock values are skipped. Energy values must be finite and
nonnegative; malformed numeric tokens are skipped instead of being partially
parsed or changed to zero. Blank energy/feed cells retain the export convention
of zero. This does not imply support for every nonstandard export.

## Caveats

- Annualization scales your measured window to 365 days; a single-season
  export skews summer/winter estimates. Use a 12-month export for decisions.
- Annual costs include fixed fees (incl. VAT): identical for flat and supplier plans (single/three-phase via `--phase`); Taoz's fixed fee is higher and included explicitly.
- Taoz currently uses one regulated fixed-fee amount for both meter phases; a separate three-phase Taoz fixed-fee variant is not modeled. `--phase` changes the flat/supplier fixed fees only.
- The bundled Taoz yom-tov dates cover 2026 and 2027 (Israel). Both yearly Hebcal API URLs are listed in `data/tariffs.json`; their holiday dates were cross-checked on 2026-11-03.
- The Shabbat split (Friday sunset to Saturday nightfall) uses fixed Jerusalem coordinates with a NOAA sunset approximation; times can differ from local calendars by a few minutes.
- The night base load is labelled "רצפת צריכה (בסיס)" with a plain-language explanation (fridge always on + many always-plugged devices, each drawing little).
- Efficiency context compares measured patterns to typical-technology benchmarks from `data/benchmarks.json` (washer kWh/cycle vs a modern A-rated eco 40-60 cycle; conditional inverter-AC field-study range; fridge floor context) - context only, never a verdict, no brand/model, sources with access dates on the Sources page (`web/sources.html`).
- Shabbat-observance detection is statistical and opt-out by silence: it combines an elevated Shabbat-night base (plate/urn signature) with near-absence of appliance starts on Shabbat, shows "נראה שבמשק הבית שומרים שבת" only above its confidence threshold with the supporting numbers, stays neutral below it, and never concludes non-observance.

## Translations (i18n)

All user-visible strings live in one file: `i18n/strings.json`
(`key -> { he, ... }`). Python and the web page read the same file (the web
bundle `web/i18n-data.js` is generated - run `scripts/gen_web_data.py` after
editing). Available languages: Hebrew (default),
English, Arabic (pending native-speaker review), Russian (pending
native-speaker review), and Amharic (pending native-speaker review). IEC supplier plan names stay in their original Hebrew form in every
language - they are proper nouns from the tariff catalog, not UI text. Adding a language means adding its entry under every key and in the
`languages` map; tests enforce completeness and matching placeholders. The
site switches language with a `?lang=` URL parameter (no cookies, no network);
Hebrew is the default. The cautious/probabilistic phrasing of the insight
texts must survive translation exactly - every language needs a careful
review, ideally by a native speaker.

## Development

`scripts/generate_og_assets.py` regenerates the share/favicon PNGs in `web/` from the synthetic sample data (needs Pillow and Noto Sans Hebrew at `/usr/share/fonts/truetype/noto/`; the PNGs are committed, so CI does not run it).

```sh
pytest --cov          # tests + coverage gate (>= 80%)
ruff check src tests scripts  # lint
ruff format --check src tests scripts  # formatting (also enforced in CI)
pip-audit             # dependency vulnerabilities
man -l man/iec-calc.1 # man page
```

Rules: design doc first (DESIGN.md), an issue per change, small signed
commits, PRs merged only with green CI and an independent review.
