"""MCP tool implementations for the ai-research server.

Each tool module exposes:

- `TOOL`: an `mcp.types.Tool` definition (name + JSON schema).
- `handle(arguments)`: an async handler that validates inputs, invokes
  the underlying toolkit verb, and returns a JSON-able structured result.
- `register(server, registry)`: wires the tool into the shared dispatch
  registry consumed by `server.list_tools` / `server.call_tool`.
"""
