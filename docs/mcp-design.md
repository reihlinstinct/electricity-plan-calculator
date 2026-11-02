# MCP server design (issue #34)

Goal: expose the calculator to MCP clients without changing its privacy posture.

- **Transport:** stdio only, newline-delimited JSON-RPC 2.0, MCP protocol version `2025-06-18` (initialize, notifications/initialized, ping, tools/list, tools/call). No sockets, no HTTP listener.
- **Zero new dependencies.** The project has no runtime dependencies and the whole protocol surface we need is ~100 lines, so the protocol is implemented in-repo (`src/iec_calc/mcp_server.py`) instead of pulling the official SDK (MIT) with its dependency tree. If the spec grows beyond tools, swapping to the official SDK is a contained change.
- **Tools:** `analyze_csv` (optional `weather=true`, the only network path: Open-Meteo, experimental, same disclosure as CLI `--weather`), `rank_plans` (`phase`, `gas`, `hot`, `smart_meter`, `current_plan`; conditional plans excluded unless flagged, same as the CLI), `explain_insights`. All take a local `path`; output is the same Hebrew text the CLI prints.
- **Trust boundary:** local stdio only. The server reads any path the caller passes - there is no path allowlist or traversal limit, and tool-error text echoes the caller-supplied path back to that same caller. It inherits the launching client's filesystem permissions, so only launch it from a trusted local MCP client.

- **Privacy:** stateless — each call reads the file, computes, forgets. Nothing is written or retained; stdout carries protocol messages only, logs go to stderr at WARNING (`MCP_DEBUG=1` for debug). Tool errors return `isError: true` results; file contents never appear in logs.
- **Testing:** in-process `handle()` tests for every method and error path, plus a subprocess stdio smoke test. Ranking output asserted identical to the CLI.
- **Publishing:** none. No registry uploads without explicit owner approval.
