"""Command line interface: iec-calc analyze|plans|report EXPORT.csv [--weather]."""
from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, analysis, cost, report, tariffs, weather
from . import parser as csv_parser

log = logging.getLogger(__name__)

DEFAULT_LAT, DEFAULT_LON = 31.78, 35.21  # Jerusalem


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="iec-calc",
        description="Analyze an IEC consumption export and rank Israeli electricity plans by your real usage.",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--debug", action="store_true", help="verbose diagnostic logging to stderr (off by default)")
    ap.add_argument("--tariffs", metavar="JSON", help="override data/tariffs.json")
    sub = ap.add_subparsers(dest="command", required=True)

    def add_file_arg(p):
        p.add_argument("csv", help="IEC consumption export (CSV)")

    a = sub.add_parser("analyze", help="consumption profile: totals, base load, peaks, night/weekend split")
    add_file_arg(a)
    a.add_argument("--weather", action="store_true", help="correlate with temperature (Open-Meteo)")
    a.add_argument("--lat", type=float, default=DEFAULT_LAT)
    a.add_argument("--lon", type=float, default=DEFAULT_LON)
    a.add_argument("--cooling-base", type=float, default=weather.DEFAULT_COOLING_BASE,
                   help="cooling degree-day base temperature (default: %(default)s)")
    a.add_argument("--heating-base", type=float, default=weather.DEFAULT_HEATING_BASE,
                   help="heating degree-day base temperature (default: %(default)s)")

    def add_phase_arg(sp):
        sp.add_argument("--phase", choices=["single", "three"], default="single",
                        help="meter phase for fixed-fee calculation (default: single)")

    def add_eligibility_args(sp):
        sp.add_argument("--no-smart-meter", dest="smart_meter", action="store_false",
                        help="exclude plans that require a smart meter")
        sp.add_argument("--no-gas", dest="gas_customer", action="store_false",
                        help="exclude gas-customer-only plans (Amisragas)")
        sp.add_argument("--no-hot", dest="hot_customer", action="store_false",
                        help="exclude HOT/NEXT-customer-only plans")
        sp.add_argument("--current-plan", metavar="LABEL",
                        help="label (or substring) of your current plan, to show savings vs it")

    p = sub.add_parser("plans", help="rank all electricity plans by annual cost on your data")
    add_file_arg(p)
    add_phase_arg(p)
    add_eligibility_args(p)

    r = sub.add_parser("report", help="full report: analysis + plan ranking")
    add_file_arg(r)
    add_phase_arg(r)
    add_eligibility_args(r)
    r.add_argument("--weather", action="store_true")
    r.add_argument("--lat", type=float, default=DEFAULT_LAT)
    r.add_argument("--lon", type=float, default=DEFAULT_LON)
    r.add_argument("--cooling-base", type=float, default=weather.DEFAULT_COOLING_BASE)
    r.add_argument("--heating-base", type=float, default=weather.DEFAULT_HEATING_BASE)
    return ap


def _configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    log.debug("debug logging enabled")


def _weather_block(args, summary) -> str:
    temps = weather.fetch_daily_temps(
        args.lat, args.lon,
        min(summary.daily), max(summary.daily),
    )
    w = weather.sensitivity(summary.daily, temps)
    hvac = weather.hvac_split(
        summary.daily, temps, args.cooling_base, args.heating_base
    )
    blocks = []
    blocks.append(
        report.format_weather(w)
        if w is not None
        else "רגישות למזג אוויר: לא נמצאו מספיק ימים חופפים."
    )
    if hvac is not None:
        blocks.append(report.format_hvac(hvac))
    else:
        log.debug("no hvac split for this period")
    return "\n\n".join(blocks)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _configure_logging(args.debug)
    catalog = None
    if args.command in ("plans", "report"):
        catalog = tariffs.load_catalog(args.tariffs)
        if args.current_plan:
            labels = [cost.FLAT_LABEL, cost.TAOZ_LABEL] + [p.label for p in catalog.plans]
            matches = [lbl for lbl in labels if args.current_plan in lbl]
            if len(matches) != 1:
                valid = "\n".join(f"  {lbl}" for lbl in labels)
                reason = (
                    f"no plan matches '{args.current_plan}'"
                    if not matches
                    else f"'{args.current_plan}' is ambiguous ({len(matches)} matches: "
                         + "; ".join(matches) + ")"
                )
                print(f"error: {reason}. valid labels:\n{valid}", file=sys.stderr)
                return 2
    try:
        intervals = csv_parser.parse(args.csv)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = analysis.summarize(intervals)
    out = []
    if args.command in ("analyze", "report"):
        out.append(report.format_analysis(summary))
        if getattr(args, "weather", False):
            out.append(_weather_block(args, summary))
    if args.command in ("plans", "report"):
        customer = cost.Customer(
            smart_meter=args.smart_meter,
            gas_customer=args.gas_customer,
            hot_customer=args.hot_customer,
        )
        log.debug("customer eligibility: %s", customer)
        costs = cost.rank_plans(
            intervals, catalog, summary.days, phase=args.phase, customer=customer
        )
        excluded = cost.unavailable_plans(catalog, customer)
        out.append(
            report.format_ranking(
                costs, summary.days, catalog, excluded, args.current_plan
            )
        )
    print("\n\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
