# MCP server setup — Claude Desktop

`ai-research-mcp` is a local, read-only [Model Context Protocol](https://modelcontextprotocol.io) server that exposes your wiki to Claude Desktop (and any MCP-aware client) over stdio. Claude Desktop spawns it as a subprocess; there is no network listener, no daemon, and no mutation surface.

Four tools are advertised: `ask`, `search`, `list_pages`, `get_page`. See [Epic-06](stories/epic-06-mcp-server.md) for the full design.

## Prerequisites

- `ai-research` installed via `uv tool install .` (or `uv tool install -e .` during development), so both `ai-research` and `ai-research-mcp` are on your `PATH`.
- A populated vault at some absolute path — i.e. a directory containing `wiki/` and `.ai-research/`.
- Claude Desktop ≥ the version that supports MCP (any current release).

Confirm the binary is resolvable before touching Claude Desktop:

```bash
which ai-research-mcp
ai-research-mcp --help 2>/dev/null || true   # it may only speak MCP over stdio; `which` is the real check
```

## Configure Claude Desktop

Edit (or create) `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ai-research": {
      "command": "ai-research-mcp",
      "env": {
        "AI_RESEARCH_ROOT": "/absolute/path/to/your/ai-research/repo"
      }
    }
  }
}
```

Then fully quit and relaunch Claude Desktop (Cmd+Q, not just close the window). The four `ai-research` tools should appear in the tool picker.

If you already have other MCP servers configured, merge the `"ai-research"` key into your existing `mcpServers` object — don't overwrite the file.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `AI_RESEARCH_ROOT` | Yes (in Claude Desktop) | Absolute path to the vault root — the directory containing `wiki/` and `.ai-research/`. Claude Desktop launches the subprocess with an unhelpful `cwd`, so set this explicitly. |

When running `ai-research-mcp` directly from a shell, the server falls back to the current working directory if `AI_RESEARCH_ROOT` is unset.

## Confirm it works

1. In Claude Desktop, start a new chat.
2. Click the tool/attachments icon — you should see `ask`, `search`, `list_pages`, `get_page` under an `ai-research` group.
3. Ask a question you know the wiki can answer, e.g. "use the ai-research ask tool to summarise [a concept you've ingested]".
4. Expect an answer with `[[page-name]]` citations that match real files under `wiki/`.

Cross-check the same question via `claude -p "/ask '<question>'" --output-format json` — the MCP answer should be consistent with the CLI path.

## Troubleshooting

### Server doesn't appear in the tool picker

1. **Check the MCP log** — Claude Desktop writes per-server logs to `~/Library/Logs/Claude/mcp-server-ai-research.log`. `bat` it for recent errors:
   ```bash
   bat ~/Library/Logs/Claude/mcp-server-ai-research.log
   ```
2. **Verify the binary is on `PATH`** — `which ai-research-mcp`. If empty, re-run `uv tool install .` and confirm `~/.local/bin` (or your `uv tool` bin dir) is on the `PATH` seen by Claude Desktop. GUI apps on macOS often have a narrower `PATH` than your shell; using the absolute path in `"command"` is a safe fallback:
   ```json
   "command": "/Users/you/.local/bin/ai-research-mcp"
   ```
3. **Validate JSON** — a missing comma in `claude_desktop_config.json` silently disables all MCP servers. Run `jq . ~/Library/Application\ Support/Claude/claude_desktop_config.json` — non-zero exit means the file is malformed.
4. **Fully quit Claude Desktop** — `Cmd+Q`. Closing the window does not restart the MCP host.

### "Vault not found" / empty results

- Confirm `AI_RESEARCH_ROOT` is absolute and contains both `wiki/` and `.ai-research/index.md`. Run `ai-research index-rebuild` in the repo if the index is missing.
- The env var is set in the JSON config, not inherited from your shell — double-check you edited `"env"` and not `"args"`.

### Tools list shows only some tools

The server advertises all four unconditionally. Partial lists usually mean the server crashed mid-`initialize` — check the log (step 1 above) for a stack trace, often a missing dependency or a bad `AI_RESEARCH_ROOT`.

## Uninstall

Remove the `"ai-research"` key from `claude_desktop_config.json` and restart Claude Desktop. `uv tool uninstall ai-research` drops both binaries.
