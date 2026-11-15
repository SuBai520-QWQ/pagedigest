#!/usr/bin/env python3
"""PageDigest MCP — minimal Python example client (standard library only).

Walks through the full life cycle of the PageDigest remote MCP server:

  1. initialize   (open, no payment)
  2. tools/list   (open, no payment)
  3. tools/call   with the free sampling header ``x-sampling: true``
                  -> a real, unpaid preview result
  4. tools/call   without the sampling header
                  -> HTTP 402 + an x402 payment challenge, which we decode
                     and print (amount, network, payTo, ...)

The example deliberately stops at step 4. It does NOT pay the challenge and
never touches a wallet, a private key, or any credential. Paying an x402
challenge is left to a real x402-aware client.

Requires Python >= 3.8. No pip install needed.

Usage:
    python3 examples/python-client.py [url-to-summarize]

Environment:
    PAGEDIGEST_MCP_URL   override the MCP endpoint
                         (default: https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp)
"""

import base64
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get(
    "PAGEDIGEST_MCP_URL",
    "https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp",
)
TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"

_next_id = 1


def _parse_rpc_body(text):
    """Parse a Streamable HTTP response body: plain JSON or SSE data lines."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    last = None
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                last = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
    if last is not None:
        return last
    raise ValueError(f"Unparseable response body: {text[:200]}")


def rpc(method, params=None, extra_headers=None):
    """Send one JSON-RPC message; return (status, headers, rpc, raw_body).

    urllib raises for non-2xx, so HTTP 402 lands in the except branch —
    which is exactly where the payment challenge lives.
    """
    global _next_id
    payload = {"jsonrpc": "2.0", "id": _next_id, "method": method,
               "params": params or {}}
    _next_id += 1
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    # One retry on dropped connections: hosted dev boxes (and some proxies)
    # occasionally cut an idle TLS connection mid-request.
    last_exc = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read().decode()
                return (res.status, res.headers,
                        _parse_rpc_body(raw) if raw else None, raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                parsed = _parse_rpc_body(raw) if raw else None
            except ValueError:
                parsed = None
            return e.code, e.headers, parsed, raw
        except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
            last_exc = e
            if attempt == 0:
                time.sleep(2)
    raise last_exc


def notify(method):
    """Send a JSON-RPC notification (no id, no response expected)."""
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"jsonrpc": "2.0", "method": method}).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass


def die(step, detail):
    print(f"\n[error] {step} failed: {detail}", file=sys.stderr)
    sys.exit(1)


def main():
    print(f"PageDigest MCP endpoint: {ENDPOINT}")
    print(f"Page to summarize:       {TARGET_URL}\n")

    # 1. initialize ------------------------------------------------------
    print("── 1. initialize ─────────────────────────────────────────────")
    status, _, init, raw = rpc("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "pagedigest-example-python", "version": "1.0.0"},
    })
    if status != 200 or not init or "result" not in init:
        die("initialize", f"HTTP {status}: {raw[:300]}")
    result = init["result"]
    print(f"server:            {result['serverInfo']['name']} "
          f"{result['serverInfo']['version']}")
    print(f"protocolVersion:   {result['protocolVersion']}")
    notify("notifications/initialized")

    # 2. tools/list ------------------------------------------------------
    print("\n── 2. tools/list ─────────────────────────────────────────────")
    status, _, listing, raw = rpc("tools/list")
    if status != 200 or not listing or "result" not in listing:
        die("tools/list", f"HTTP {status}: {raw[:300]}")
    for tool in listing["result"]["tools"]:
        print(f"tool:        {tool['name']} — {tool.get('title', '')}")
        print(f"description: {tool['description']}")
        print(f"inputSchema: {json.dumps(tool['inputSchema'])}")

    # 3. tools/call with the free sampling header ------------------------
    print("\n── 3. tools/call with sampling header (free preview) ─────────")
    print("request header: x-sampling: true")
    status, _, sampled, raw = rpc(
        "tools/call",
        {"name": "summarize_url", "arguments": {"url": TARGET_URL}},
        {"x-sampling": "true"},
    )
    if status != 200 or not sampled or "result" not in sampled:
        die("tools/call (sampling)", f"HTTP {status}: {raw[:300]}")
    summary = sampled["result"].get("structuredContent")
    if summary:
        print(f"title:       {summary.get('title')}")
        print(f"summary:     {summary.get('summary')}")
        print(f"keyPoints:   {json.dumps(summary.get('keyPoints'))}")
        print(f"entities:    {json.dumps(summary.get('entities'))}")
        print(f"stats:       {json.dumps(summary.get('stats'))}")
    else:
        print(json.dumps(sampled["result"], indent=2))

    # 4. tools/call without sampling -> HTTP 402 challenge ---------------
    print("\n── 4. tools/call without sampling header (paid path) ─────────")
    status, headers, _, raw = rpc(
        "tools/call",
        {"name": "summarize_url", "arguments": {"url": TARGET_URL}},
    )
    if status != 402:
        print(f"Unexpected: expected HTTP 402, got HTTP {status}. "
              "The server may have changed its pricing behaviour.")
        print(raw[:500])
        return
    print("HTTP 402 Payment Required — as expected.")
    challenge_header = headers.get("Payment-Required")
    if not challenge_header:
        die("402 handling", "no Payment-Required header found")
    challenge = json.loads(base64.b64decode(challenge_header).decode())
    print(f"x402Version: {challenge.get('x402Version')}")
    for accept in challenge.get("accepts", []):
        human = int(accept["amount"]) / 10 ** 6  # USD₮0 uses 6 decimals
        print("accepts[0]:")
        print(f"  scheme:            {accept['scheme']}")
        print(f"  network:           {accept['network']} (X Layer, chain id 196)")
        print(f"  amount:            {accept['amount']} (smallest unit) = "
              f"{human} {accept.get('extra', {}).get('name', '')}")
        print(f"  asset (token):     {accept['asset']}")
        print(f"  payTo:             {accept['payTo']}")
        print(f"  maxTimeoutSeconds: {accept['maxTimeoutSeconds']}")
    print(
        "\nThis example stops here: it does not pay the challenge. "
        "A production client would sign the payment with an x402-compatible "
        "wallet and retry the same tools/call with the payment payload."
    )


if __name__ == "__main__":
    main()
