# PageDigest MCP — example clients

Two dependency-free example clients that walk through the full life cycle of
the PageDigest remote MCP server:

| File | Runtime | Dependencies |
| --- | --- | --- |
| [`node-client.mjs`](node-client.mjs) | Node.js ≥ 18 | none (global `fetch`) |
| [`python-client.py`](python-client.py) | Python ≥ 3.8 | none (standard library `urllib`) |

Both do exactly the same four steps:

1. **`initialize`** — open, no payment. Returns the server info
   (`a2mcp-summarizer`, version `0.1.0`, protocol `2025-03-26`).
2. **`tools/list`** — open, no payment. Returns the single tool
   `summarize_url` and its input schema (`url` required, optional
   `maxSentences` 1–10, default 5).
3. **`tools/call` with the free sampling header** — a real, unpaid preview
   result (see "Free sampling" below).
4. **`tools/call` without the sampling header** — the paid path. The server
   answers **HTTP 402** with an x402 payment challenge; the examples decode
   and print the challenge, then stop. They never pay, and they never touch
   a wallet, a private key, or any credential.

## Run

```bash
# Node.js
node examples/node-client.mjs                 # summarizes https://example.com
node examples/node-client.mjs https://en.wikipedia.org/wiki/Model_Context_Protocol

# Python
python3 examples/python-client.py             # summarizes https://example.com
python3 examples/python-client.py https://en.wikipedia.org/wiki/Model_Context_Protocol
```

Set `PAGEDIGEST_MCP_URL` to point at a different endpoint. The default is
`https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp`.

## Expected output

Verified against the live server on 2026-11-15 (both clients produce the
same output; page content is the summary of https://example.com):

```text
── 1. initialize ─────────────────────────────────────────────
server:            a2mcp-summarizer 0.1.0
protocolVersion:   2025-03-26

── 2. tools/list ─────────────────────────────────────────────
tool:        summarize_url — Web Page Summarizer & Structured Extractor
description: Fetch a web page URL and return a concise summary, key points, ...
inputSchema: {"type":"object","properties":{"url":{...},"maxSentences":{...}},"required":["url"]}

── 3. tools/call with sampling header (free preview) ─────────
request header: x-sampling: true
title:       Example Domain
summary:     This domain is for use in documentation examples without needing permission. ...
keyPoints:   ["This domain is for use in documentation examples without needing permission.", ...]
entities:    {"named":[],"dates":[],"amounts":[],"urls":[]}
stats:       {"wordCount":13,"sentenceCount":2,"paragraphCount":1}

── 4. tools/call without sampling header (paid path) ─────────
HTTP 402 Payment Required — as expected.
x402Version: 2
accepts[0]:
  scheme:            exact
  network:           eip155:196 (X Layer, chain id 196)
  amount:            10000 (smallest unit) = 0.01 USD₮0
  asset (token):     0x779ded0c9e1022225f8e0630b35a9b54be713736
  payTo:             0xae5a69d9869a40447d83bdfab8010f9bad2d3a1c
  maxTimeoutSeconds: 300
```

## Free sampling (verified)

Send the HTTP header

```text
x-sampling: true
```

with your `tools/call` request and the server returns a real result without
payment — this is the documented "free sampling available" evaluation path,
verified live: a sampled call for https://example.com returned the full
structured summary (title, summary, key points, entities, headings, stats).

Notes, all verified by probing the live endpoint:

- The value must be exactly `true`. `x-sampling: 1` is ignored and the call
  is answered with 402 like any other unpaid call.
- Sampling is a server-side courtesy for evaluation; treat it as
  best-effort, not a free tier — production use is the paid path below.

## The 402 payment challenge (verified)

An unpaid `tools/call` returns **HTTP 402** with:

- a `Payment-Required` response header: a base64-encoded x402 v2 challenge
  JSON. Decoded (live values, 2026-11-15):

  ```json
  {
    "x402Version": 2,
    "error": "Payment required",
    "resource": { "url": "...", "description": "Summarize a web page ...", "mimeType": "application/json" },
    "accepts": [{
      "scheme": "exact",
      "network": "eip155:196",
      "amount": "10000",
      "asset": "0x779ded0c9e1022225f8e0630b35a9b54be713736",
      "payTo": "0xae5a69d9869a40447d83bdfab8010f9bad2d3a1c",
      "maxTimeoutSeconds": 300,
      "extra": { "name": "USD₮0", "version": "1" }
    }],
    "extensions": { "bazaar": { "...": "..." } }
  }
  ```

  `amount` is in the token's smallest unit; USD₮0 has 6 decimals, so
  `10000` = **0.01 USD₮0** per call. `network: eip155:196` is X Layer
  mainnet. `asset` is the USD₮0 contract on X Layer.

- a JSON body carrying the `extensions.bazaar` discovery metadata (tool
  name, input schema, and an output example) — handy for marketplaces,
  not needed to pay.

To actually pay, an x402-compatible client signs a payment for the
`accepts[0]` terms and retries the same `tools/call` with the payment
payload. **These examples intentionally do not implement that step** — no
wallet code, no keys, nothing to steal. They exist to show the protocol
surface: handshake, discovery, free preview, and the exact shape of the
challenge a paying client must answer.
