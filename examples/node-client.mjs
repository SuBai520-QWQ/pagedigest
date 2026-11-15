#!/usr/bin/env node
/**
 * PageDigest MCP — minimal Node.js example client (zero dependencies).
 *
 * Walks through the full life cycle of the PageDigest remote MCP server:
 *
 *   1. initialize          (open, no payment)
 *   2. tools/list          (open, no payment)
 *   3. tools/call          with the free sampling header `x-sampling: true`
 *                          -> a real, unpaid preview result
 *   4. tools/call          without the sampling header
 *                          -> HTTP 402 + an x402 payment challenge, which we
 *                             decode and print (amount, network, payTo, ...)
 *
 * The example deliberately stops at step 4. It does NOT pay the challenge
 * and never touches a wallet, a private key, or any credential. Paying an
 * x402 challenge is left to a real x402-aware client.
 *
 * Requires Node.js >= 18 (global fetch). No npm install needed.
 *
 * Usage:
 *   node examples/node-client.mjs [url-to-summarize]
 *
 * Environment:
 *   PAGEDIGEST_MCP_URL   override the MCP endpoint
 *                        (default: https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp)
 */

const ENDPOINT =
  process.env.PAGEDIGEST_MCP_URL ??
  "https://4021-agqz5x3ybel4f5yrdnvpaqbzgi.instabox.tech/mcp";
const TARGET_URL = process.argv[2] ?? "https://example.com";

let nextId = 1;

/** Parse a Streamable HTTP response body: plain JSON or SSE (`data:` lines). */
function parseRpcBody(text) {
  const trimmed = text.trim();
  if (trimmed.startsWith("{")) return JSON.parse(trimmed);
  let last = null;
  for (const line of trimmed.split("\n")) {
    if (line.startsWith("data:")) {
      try {
        last = JSON.parse(line.slice(5).trim());
      } catch {
        /* keep scanning */
      }
    }
  }
  if (last) return last;
  throw new Error(`Unparseable response body: ${trimmed.slice(0, 200)}`);
}

/**
 * Send one JSON-RPC message. Returns { status, headers, rpc } where `rpc`
 * is the parsed JSON-RPC response (or null for empty bodies, e.g. acks).
 */
async function rpc(method, params, extraHeaders = {}) {
  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      ...extraHeaders,
    },
    body: JSON.stringify({ jsonrpc: "2.0", id: nextId++, method, params }),
  });
  const text = await res.text();
  return {
    status: res.status,
    headers: res.headers,
    rpc: text ? parseRpcBody(text) : null,
    rawBody: text,
  };
}

/** Send a JSON-RPC notification (no id, no response expected). */
async function notify(method) {
  await fetch(ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    },
    body: JSON.stringify({ jsonrpc: "2.0", method }),
  }).catch(() => {});
}

function die(step, detail) {
  console.error(`\n[error] ${step} failed: ${detail}`);
  process.exit(1);
}

console.log(`PageDigest MCP endpoint: ${ENDPOINT}`);
console.log(`Page to summarize:       ${TARGET_URL}\n`);

// ---------------------------------------------------------------- 1. init
console.log("── 1. initialize ─────────────────────────────────────────────");
const init = await rpc("initialize", {
  protocolVersion: "2025-03-26",
  capabilities: {},
  clientInfo: { name: "pagedigest-example-node", version: "1.0.0" },
});
if (init.status !== 200 || !init.rpc?.result) {
  die("initialize", `HTTP ${init.status}: ${init.rawBody.slice(0, 300)}`);
}
const { serverInfo, protocolVersion } = init.rpc.result;
console.log(`server:            ${serverInfo.name} ${serverInfo.version}`);
console.log(`protocolVersion:   ${protocolVersion}`);
await notify("notifications/initialized");

// ----------------------------------------------------------- 2. tools/list
console.log("\n── 2. tools/list ─────────────────────────────────────────────");
const list = await rpc("tools/list", {});
if (list.status !== 200 || !list.rpc?.result) {
  die("tools/list", `HTTP ${list.status}: ${list.rawBody.slice(0, 300)}`);
}
for (const tool of list.rpc.result.tools) {
  console.log(`tool:        ${tool.name} — ${tool.title ?? ""}`);
  console.log(`description: ${tool.description}`);
  console.log(`inputSchema: ${JSON.stringify(tool.inputSchema)}`);
}

// ------------------------------------------- 3. tools/call, free sampling
console.log("\n── 3. tools/call with sampling header (free preview) ─────────");
console.log("request header: x-sampling: true");
const sampled = await rpc(
  "tools/call",
  { name: "summarize_url", arguments: { url: TARGET_URL } },
  { "x-sampling": "true" },
);
if (sampled.status !== 200 || !sampled.rpc?.result) {
  die(
    "tools/call (sampling)",
    `HTTP ${sampled.status}: ${sampled.rawBody.slice(0, 300)}`,
  );
}
const summary = sampled.rpc.result.structuredContent ?? null;
if (summary) {
  console.log(`title:       ${summary.title}`);
  console.log(`summary:     ${summary.summary}`);
  console.log(`keyPoints:   ${JSON.stringify(summary.keyPoints)}`);
  console.log(`entities:    ${JSON.stringify(summary.entities)}`);
  console.log(`stats:       ${JSON.stringify(summary.stats)}`);
} else {
  console.log(JSON.stringify(sampled.rpc.result, null, 2));
}

// --------------------------------- 4. tools/call, no sampling -> HTTP 402
console.log("\n── 4. tools/call without sampling header (paid path) ─────────");
const paid = await rpc("tools/call", {
  name: "summarize_url",
  arguments: { url: TARGET_URL },
});
if (paid.status !== 402) {
  console.log(
    `Unexpected: expected HTTP 402, got HTTP ${paid.status}. ` +
      "The server may have changed its pricing behaviour.",
  );
  console.log(paid.rawBody.slice(0, 500));
  process.exit(0);
}
console.log("HTTP 402 Payment Required — as expected.");
const challengeHeader = paid.headers.get("payment-required");
if (!challengeHeader) die("402 handling", "no Payment-Required header found");
const challenge = JSON.parse(
  Buffer.from(challengeHeader, "base64").toString("utf8"),
);
console.log(`x402Version: ${challenge.x402Version}`);
for (const accept of challenge.accepts ?? []) {
  const decimals = 6; // USD₮0 uses 6 decimals
  const human = Number(accept.amount) / 10 ** decimals;
  console.log("accepts[0]:");
  console.log(`  scheme:            ${accept.scheme}`);
  console.log(`  network:           ${accept.network} (X Layer, chain id 196)`);
  console.log(`  amount:            ${accept.amount} (smallest unit) = ${human} ${accept.extra?.name ?? ""}`);
  console.log(`  asset (token):     ${accept.asset}`);
  console.log(`  payTo:             ${accept.payTo}`);
  console.log(`  maxTimeoutSeconds: ${accept.maxTimeoutSeconds}`);
}
console.log(
  "\nThis example stops here: it does not pay the challenge. " +
    "A production client would sign the payment with an x402-compatible " +
    "wallet and retry the same tools/call with the payment payload.",
);
