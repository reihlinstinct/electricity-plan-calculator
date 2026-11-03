"""Minimal MCP server over stdio. Zero dependencies, local files only.

Speaks newline-delimited JSON-RPC 2.0, pinned to MCP protocol version
2025-06-18 (initialize, notifications/initialized, ping, tools/list,
tools/call). Every tool call reads the given local CSV path, computes and
forgets: no state, no retention, and no network access except the explicit
`weather` opt-in on analyze_csv (Open-Meteo, experimental, same disclosure
as the CLI --weather flag). stdout carries protocol messages only; logs go
to stderr at WARNING unless MCP_DEBUG is set.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from . import analysis, cost, insights, report, tariffs, weather
from . import parser as csv_parser
from .i18n import t as _t

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "iec-calc", "version": "0.1.0"}

PRIVACY_NOTE = "Reads the local CSV at `path` only; nothing is sent anywhere or kept after the call."

TOOLS = [
    {
        "name": "analyze_csv",
        "description": (
            "Consumption profile of an IEC export: totals, base load, peaks, "
            "night/weekend and Shabbat split. "
            + PRIVACY_NOTE
            + " `weather=true` adds an EXPERIMENTAL weather-sensitivity estimate "
            "and makes a one-off network call to Open-Meteo (opt-in, off by "
            "default)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local path of the IEC CSV export."},
                "weather": {
                    "type": "boolean",
                    "default": False,
                    "description": "Experimental weather correlation; calls Open-Meteo over the network.",
                },
                "lat": {"type": "number", "default": 31.7683},
                "lon": {"type": "number", "default": 35.2137},
            },
            "required": ["path"],
        },
    },
    {
        "name": "rank_plans",
        "description": (
            "Rank Israeli electricity plans (flat, Taoz, suppliers) by annual "
            "cost on the user's real 15-minute consumption. "
            + PRIVACY_NOTE
            + " Gas/HOT-customer conditional plans are excluded unless gas/hot "
            "are set to true."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local path of the IEC CSV export."},
                "phase": {"type": "string", "enum": ["single", "three"], "default": "single"},
                "gas": {"type": "boolean", "default": False, "description": "Amisragas gas customer."},
                "hot": {"type": "boolean", "default": False, "description": "HOT/NEXT customer."},
                "smart_meter": {"type": "boolean", "default": True},
                "current_plan": {
                    "type": "string",
                    "description": "Substring of the user's current plan label, to mark it in the ranking.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "explain_insights",
        "description": (
            "Descriptive observations over the file (peak hours, Shabbat "
            "split, Taoz peak share) plus probabilistic appliance-signature "
            "detection with confidence levels. Observations only, no causal "
            "claims. " + PRIVACY_NOTE
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local path of the IEC CSV export."},
                "lat": {"type": "number", "default": 31.7683},
                "lon": {"type": "number", "default": 35.2137},
            },
            "required": ["path"],
        },
    },
]


def _error(code: int, message: str, msg_id) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


_BOOL_ARGS = ("weather", "gas", "hot", "smart_meter")
_NUM_ARGS = ("lat", "lon")


def _parse_args(arguments: dict) -> tuple[str, dict]:
    """Validate and normalize the shared path argument."""
    path = arguments.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("missing required argument: path")
    return path, arguments


def _validate_args(arguments: dict) -> None:
    """Reject wrong-typed optional arguments before they reach the engine."""
    for key in _BOOL_ARGS:
        if key in arguments and not isinstance(arguments[key], bool):
            raise ValueError(f"argument {key!r} must be a boolean")
    for key in _NUM_ARGS:
        value = arguments.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError(f"argument {key!r} must be a number")
    if "phase" in arguments and arguments["phase"] not in ("single", "three"):
        raise ValueError("argument 'phase' must be 'single' or 'three'")
    if "current_plan" in arguments and not isinstance(arguments["current_plan"], str):
        raise ValueError("argument 'current_plan' must be a string")


def _call_tool(name: str, arguments: dict) -> dict:
    path, args = _parse_args(arguments or {})
    _validate_args(args)
    intervals = csv_parser.parse(Path(path))
    summary = analysis.summarize(intervals)
    catalog = tariffs.load_catalog(None)

    if name == "analyze_csv":
        out = [report.format_analysis(summary)]
        if args.get("weather"):
            temps = weather.fetch_daily_temps(
                args.get("lat", 31.7683),
                args.get("lon", 35.2137),
                min(summary.daily),
                max(summary.daily),
            )
            w = weather.sensitivity(summary.daily, temps)
            out.append(report.format_weather(w) if w is not None else _t("report.weather_no_overlap"))
        return _text_result("\n\n".join(out))

    if name == "rank_plans":
        current = args.get("current_plan")
        if current:
            labels = [cost.FLAT_LABEL, cost.TAOZ_LABEL] + [p.label for p in catalog.plans]
            matches = [lbl for lbl in labels if current in lbl]
            if len(matches) != 1:
                raise ValueError(
                    f"current_plan must match exactly one plan label ({len(matches)} matches for {current!r})"
                )
        customer = cost.Customer(
            smart_meter=args.get("smart_meter", True),
            gas_customer=args.get("gas", False),
            hot_customer=args.get("hot", False),
        )
        costs = cost.rank_plans(
            intervals,
            catalog,
            summary.days,
            phase=args.get("phase", "single"),
            customer=customer,
        )
        excluded = cost.unavailable_plans(catalog, customer)
        return _text_result(report.format_ranking(costs, summary.days, catalog, excluded, current))

    if name == "explain_insights":
        ins = insights.build_insights(
            intervals,
            summary,
            catalog,
            lat=args.get("lat", 31.7683),
            lon=args.get("lon", 35.2137),
        )
        return _text_result(report.format_insights(ins, catalog.flat_rate))

    raise ValueError(f"unknown tool: {name}")


def handle(message: dict, out) -> None:
    """Handle one parsed JSON-RPC message; notifications get no response."""
    if not isinstance(message, dict):
        out.write(json.dumps(_error(-32600, "invalid request", None)) + "\n")
        return
    msg_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        if msg_id is not None:
            out.write(json.dumps(_error(-32600, "invalid request", msg_id)) + "\n")
        return
    if method == "initialize":
        out.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": SERVER_INFO,
                    },
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return  # notification: never respond
    if method == "ping":
        out.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}}) + "\n")
        return
    if method == "tools/list":
        out.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS},
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        return
    if method == "tools/call":
        params = message.get("params")
        arguments = params.get("arguments") if isinstance(params, dict) else None
        if not isinstance(params, dict) or (arguments is not None and not isinstance(arguments, dict)):
            if msg_id is not None:
                out.write(json.dumps(_error(-32602, "invalid params", msg_id)) + "\n")
            return
        try:
            result = _call_tool(params.get("name", ""), arguments or {})
            out.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": result,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        except Exception as exc:  # never let one bad call kill the stdio loop
            log.debug("tools/call failed: %s", type(exc).__name__)
            out.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": _text_result(f"error: {exc}", is_error=True),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return
    if msg_id is not None:
        out.write(json.dumps(_error(-32601, f"method not found: {method}", msg_id)) + "\n")


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG if _debug_enabled() else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    log.debug("mcp server starting (protocol %s)", PROTOCOL_VERSION)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_error(-32700, "parse error", None)) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(message, dict):
            sys.stdout.write(json.dumps(_error(-32600, "invalid request", None)) + "\n")
            sys.stdout.flush()
            continue
        handle(message, sys.stdout)
        sys.stdout.flush()
    return 0


def _debug_enabled() -> bool:
    import os

    return os.environ.get("MCP_DEBUG", "").lower() in ("1", "true", "yes")


if __name__ == "__main__":
    sys.exit(main())
