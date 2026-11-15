# PageDigest — Web Page Summarizer & Structured Extractor

Pay-per-call web page summarizer & structured extractor for AI agents, exposed as a remote MCP server.

**Tool: `summarize_url`** — fetch a public web page and return a summary, key points, headings and entities (named phrases, dates, amounts, links).

> **Pricing, stated plainly:** PageDigest is NOT free. Each tool call costs **$0.01**, paid via the [x402 protocol](https://www.x402.org/) in USD₮0 on X Layer (an HTTP 402 challenge is returned on `tools/call`; `initialize` and `tools/list` are open). A free sampling/preview path is available for evaluation before paying.

## Connect

Remote MCP endpoint (Streamable HTTP):

```
https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp
```

Client config:

```json
{ "mcpServers": { "pagedigest": { "url": "https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp" } } }
```

Health checks need no credentials: `initialize` + `tools/list` are open; only `tools/call` returns 402.

## Examples

Runnable, dependency-free example clients (Node.js and Python) live in [`examples/`](examples/): they perform the `initialize` → `tools/list` → `tools/call` handshake, demonstrate the free sampling preview (`x-sampling: true`), and decode the HTTP 402 x402 payment challenge on the paid path. See [`examples/README.md`](examples/README.md) for expected output and the verified challenge format.

## Listings

- Official MCP Registry: `io.github.SuBai520-QWQ/pagedigest` (status: active)
- Glama: https://glama.ai/mcp/connectors/io.github.SuBai520-QWQ/pagedigest

## Part of a small x402 API shop

PageDigest is the MCP face of a set of seven pay-per-call HTTP APIs for AI agents, settled in USDC on Solana via x402 (page summarization, clean-Markdown fetch, crypto market snapshots, site crawl, multi-chain lookups, email checks, web search — $0.003–$0.05 per call), listed on x402scan.

## License

MIT — see [LICENSE](LICENSE). (The license covers this repository's documentation and plugin manifest; the hosted service is operated separately.)
