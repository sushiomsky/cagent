# Stdio adapter

`cagent serve-stdio` starts a dependency-free, line-delimited JSON-RPC adapter over stdin/stdout.

It is intentionally conservative: it exposes project-state and safety tools first, not arbitrary shell or write access.

## Start

```bash
cagent serve-stdio
```

Each request is one JSON object per line. Responses are one JSON object per line.

## Initialize

```json
{"jsonrpc":"2.0","id":1,"method":"initialize"}
```

## List tools

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

Exposed tools:

```text
cagent.resume
cagent.verify
cagent.secret_scan
cagent.trust_status
cagent.trust
cagent.final_report
cagent.manifest
```

## Call a tool

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"cagent.resume","arguments":{"workspace":"."}}}
```

Secret scan:

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"cagent.secret_scan","arguments":{"workspace":".","max_files":1000}}}
```

Generate final report:

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"cagent.final_report","arguments":{"workspace":".","notes":"Generated from adapter."}}}
```

## Shutdown

```json
{"jsonrpc":"2.0","id":9,"method":"shutdown"}
```

## Notes

This adapter follows the same basic JSON-RPC interaction shape used by many tool protocols, but it is not yet a full SDK-backed MCP server. The point of this phase is to make `cagent` externally invokable and testable without adding a runtime dependency. A later phase can wrap the same tool functions with a full MCP SDK implementation.
