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

## Tariff data

All rates, discounts, eligibility notes, source URLs and verification dates
live in [`data/tariffs.json`](data/tariffs.json). Updating prices = editing
that one file. Sources: Electricity Authority tariff book (July 2026),
IEC/EA cross-checks, and supplier-site-verified plan data (2026-09-27).

## Privacy

- Real exports are never committed: `.gitignore` excludes `*.csv`;
  `data/sample_consumption.csv` is synthetic and whitelisted.
- CI runs `scripts/privacy_scan.sh`, which fails on contract-number and
  meter-id patterns and on customer metadata outside the sample.
- Customer metadata (name/address/contract/meter) is never printed or logged.

## Caveats

- Annualization scales your measured window to 365 days; a single-season
  export skews summer/winter estimates. Use a 12-month export for decisions.
- Annual costs include fixed fees (incl. VAT): identical for flat and supplier plans (single/three-phase via `--phase`); Taoz's fixed fee is higher and included explicitly.
- The Shabbat split (Friday sunset to Saturday nightfall) uses fixed Jerusalem coordinates with a NOAA sunset approximation; times can differ from local calendars by a few minutes.

## Development

`scripts/generate_og_assets.py` regenerates the share/favicon PNGs in `web/` from the synthetic sample data (needs Pillow; the PNGs are committed, so CI does not run it).

```sh
pytest --cov          # tests + coverage gate (>= 80%)
ruff check src tests  # lint
pip-audit             # dependency vulnerabilities
man -l man/iec-calc.1 # man page
```

Rules: design doc first (DESIGN.md), an issue per change, small signed
commits, PRs merged only with green CI and an independent review.
