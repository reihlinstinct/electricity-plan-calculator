"""Tests for the stdio MCP server: protocol handling in-process + stdio smoke test."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

from iec_calc import mcp_server

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_consumption.csv"


def call(message: dict) -> list[dict]:
    """Run one JSON-RPC message through handle() and collect written lines."""
    out = io.StringIO()
    mcp_server.handle(message, out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def call_tool(name: str, arguments: dict, msg_id: int = 7) -> dict:
    res = call(
        {"jsonrpc": "2.0", "id": msg_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    )
    assert len(res) == 1
    return res[0]["result"]


def test_initialize_handshake():
    res = call(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "t", "version": "0"},
            },
        }
    )
    assert res[0]["result"]["protocolVersion"] == "2025-06-18"
    assert res[0]["result"]["serverInfo"]["name"] == "iec-calc"
    assert "tools" in res[0]["result"]["capabilities"]


def test_notifications_get_no_response():
    assert call({"jsonrpc": "2.0", "method": "notifications/initialized"}) == []
    assert call({"jsonrpc": "2.0", "method": "notifications/cancelled"}) == []


def test_ping():
    res = call({"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert res == [{"jsonrpc": "2.0", "id": 2, "result": {}}]


def test_tools_list():
    res = call({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    names = [t["name"] for t in res[0]["result"]["tools"]]
    assert names == ["analyze_csv", "rank_plans", "explain_insights"]
    for tool in res[0]["result"]["tools"]:
        assert "path" in tool["inputSchema"]["required"]
        assert tool["inputSchema"]["properties"]["path"]["type"] == "string"


def test_analyze_csv():
    result = call_tool("analyze_csv", {"path": str(SAMPLE)})
    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert "ימים" in text and "קוט" in text
    assert "מזג אוויר" not in text  # weather is opt-in


def test_rank_plans_matches_cli():
    import contextlib

    from iec_calc import cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["plans", str(SAMPLE)])
    cli_out = buf.getvalue()

    result = call_tool("rank_plans", {"path": str(SAMPLE)})
    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert text in cli_out  # same engine, same ranking
    ranked = [ln for ln in text.splitlines() if " | " in ln]
    assert not any("אמישראגז" in ln for ln in ranked)  # conditional plans off by default


def test_rank_plans_opt_in_flags():
    result = call_tool("rank_plans", {"path": str(SAMPLE), "gas": True})
    text = result["content"][0]["text"]
    ranked = [ln for ln in text.splitlines() if " | " in ln]
    assert any("אמישראגז" in ln for ln in ranked)


def test_rank_plans_bad_current_plan():
    result = call_tool("rank_plans", {"path": str(SAMPLE), "current_plan": "no-such-plan"})
    assert result["isError"] is True
    assert "current_plan" in result["content"][0]["text"]


def test_explain_insights():
    result = call_tool("explain_insights", {"path": str(SAMPLE)})
    assert result["isError"] is False
    assert "כיסוי" in result["content"][0]["text"]


def test_missing_file_is_tool_error():
    result = call_tool("analyze_csv", {"path": "/nonexistent/none.csv"})
    assert result["isError"] is True


def test_missing_path_argument():
    result = call_tool("analyze_csv", {})
    assert result["isError"] is True
    assert "path" in result["content"][0]["text"]


def test_unknown_method():
    res = call({"jsonrpc": "2.0", "id": 9, "method": "resources/list"})
    assert res[0]["error"]["code"] == -32601


def test_unknown_tool():
    result = call_tool("nope", {"path": str(SAMPLE)})
    assert result["isError"] is True


def test_invalid_request():
    res = call({"jsonrpc": "2.0", "id": 5})
    assert res[0]["error"]["code"] == -32600


def test_stdio_smoke():
    """The real stdio loop: newline-delimited JSON, parse error recovery."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "iec_calc.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
    )
    proc.stdin.write("not json\n")
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n")
    proc.stdin.flush()
    err = json.loads(proc.stdout.readline())
    assert err["error"]["code"] == -32700
    pong = json.loads(proc.stdout.readline())
    assert pong["result"] == {}
    proc.stdin.close()
    assert proc.wait(timeout=10) == 0


def test_main_loop(monkeypatch, capsys):
    lines = iter(["not json", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}), ""])
    monkeypatch.setattr("sys.stdin", lines)
    assert mcp_server.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert json.loads(out[0])["error"]["code"] == -32700
    assert json.loads(out[1])["result"] == {}


def test_non_object_json_line(monkeypatch, capsys):
    lines = iter(["[1, 2]", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}), ""])
    monkeypatch.setattr("sys.stdin", lines)
    assert mcp_server.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert json.loads(out[0])["error"]["code"] == -32600
    assert json.loads(out[1])["result"] == {}


def test_wrong_typed_arguments():
    bad = (
        {"path": str(SAMPLE), "lat": "a"},
        {"path": str(SAMPLE), "lat": True},
        {"path": str(SAMPLE), "weather": 1},
        {"path": str(SAMPLE), "gas": "yes"},
        {"path": str(SAMPLE), "phase": 5},
        {"path": str(SAMPLE), "phase": "quad"},
        {"path": str(SAMPLE), "current_plan": 3},
    )
    for args in bad:
        assert call_tool("analyze_csv", args)["isError"] is True


def test_non_dict_arguments_and_params():
    res = call({"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "analyze_csv", "arguments": "x"}})
    assert res[0]["error"]["code"] == -32602
    res = call({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": "nope"})
    assert res[0]["error"]["code"] == -32602


def test_stays_alive_after_error():
    out = io.StringIO()
    mcp_server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "analyze_csv", "arguments": {"path": str(SAMPLE), "lat": "a"}},
        },
        out,
    )
    mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"}, out)
    lines = out.getvalue().splitlines()
    assert json.loads(lines[0])["result"]["isError"] is True
    assert json.loads(lines[1])["result"] == {}
