import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = {
    title: "Docs | SigilX",
    description: "How to call SigilX as an OKX Agent Service Provider (ASP) — via REST/x402 or MCP.",
}

function Code({ children }: { children: string }) {
    return (
        <pre className="overflow-x-auto rounded-lg border border-border bg-muted/30 p-4 font-mono text-xs leading-relaxed text-foreground">
            <code>{children}</code>
        </pre>
    )
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
    return (
        <section id={id} className="scroll-mt-32 border-t border-dashed border-border py-10 first:border-t-0 first:pt-0">
            <h2 className="text-xl font-semibold md:text-2xl">{title}</h2>
            <div className="mt-4 flex flex-col gap-4 text-muted-foreground">{children}</div>
        </section>
    )
}

const REFERENCES = [
    { title: "ASP Overview", href: "https://web3.okx.com/onchainos/dev-docs/okxai/asp" },
    { title: "A2MCP Guide", href: "https://web3.okx.com/onchainos/dev-docs/okxai/howtomcp" },
    { title: "ASP Registration", href: "https://web3.okx.com/onchainos/dev-docs/okxai/registerasp" },
    { title: "Payments Overview", href: "https://web3.okx.com/onchainos/dev-docs/payments/overview" },
    { title: "x402 Seller Integration", href: "https://web3.okx.com/onchainos/dev-docs/payments/service-seller" },
    { title: "Market API", href: "https://web3.okx.com/onchainos/dev-docs/market/market-api-introduction" },
    { title: "X Layer Network", href: "https://web3.okx.com/onchainos/dev-docs/xlayer/developer/build-on-xlayer/network-information" },
    { title: "Agent Installation Guide", href: "https://web3.okx.com/onchainos/dev-docs/okxai/agent-installation-guide" },
]

export default function DocsPage() {
    return (
        <main className="mx-auto max-w-3xl px-6 pb-24 pt-32 md:pt-40">
            <h1 className="text-3xl font-semibold md:text-4xl">Docs</h1>
            <p className="mt-3 text-muted-foreground">
                SigilX is registered on OKX.AI as an Agent Service Provider (ASP) — a service any AI agent
                can discover and call, either over plain REST behind an x402 payment gate, or as a tool
                over MCP (Model Context Protocol) for agent frameworks like Claude.
            </p>

            <nav className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <a href="#rest" className="text-foreground underline underline-offset-4">REST API</a>
                <a href="#mcp" className="text-foreground underline underline-offset-4">MCP / Claude</a>
                <a href="#x402" className="text-foreground underline underline-offset-4">x402 payments</a>
                <a href="#references" className="text-foreground underline underline-offset-4">References</a>
            </nav>

            <Section id="rest" title="REST API">
                <p>
                    The core service is a FastAPI app (<code className="font-mono text-foreground">services/api</code>).
                    Run it locally with:
                </p>
                <Code>{`pip install -r requirements.txt
uvicorn services.api.main:app --reload --port 8000`}</Code>
                <p>Endpoints:</p>
                <ul className="ml-4 list-disc space-y-1">
                    <li><code className="font-mono text-foreground">POST /generate</code> — analyze a wallet, render its Chain Portrait. x402-gated.</li>
                    <li><code className="font-mono text-foreground">POST /mint</code> — mint a previously generated portrait as an ERC-721 on X Layer.</li>
                    <li><code className="font-mono text-foreground">GET /portrait/{"{id}"}</code> — fetch a cached portrait. No payment required.</li>
                    <li><code className="font-mono text-foreground">GET /mint/{"{id}"}/status</code> — check whether a portrait has been minted.</li>
                    <li><code className="font-mono text-foreground">GET /chains</code> — list supported chains.</li>
                    <li><code className="font-mono text-foreground">GET /health</code> — service health check.</li>
                </ul>
                <p>Example call (with the demo bypass — see below):</p>
                <Code>{`curl -X POST http://localhost:8000/generate \\
  -H "Content-Type: application/json" \\
  -H "X-Demo-Key: $DEMO_API_KEY" \\
  -d '{"wallet_address":"0x742d35Cc6634C0532925a3b844Bc454e4438f44e","chain":"eth-mainnet"}'`}</Code>
            </Section>

            <Section id="mcp" title="MCP / Claude">
                <p>
                    SigilX also ships an MCP server (<code className="font-mono text-foreground">services/api/mcp_server.py</code>,
                    built on FastMCP) that exposes a single tool, <code className="font-mono text-foreground">generate_chain_portrait</code>,
                    directly to any MCP-capable agent — no HTTP client code required on the agent's side.
                </p>
                <Code>{`# Start the MCP server (SSE transport, default port 8001)
python -m services.api.mcp_server`}</Code>
                <p>Tool signature:</p>
                <Code>{`generate_chain_portrait(wallet_address: str, chain: str = "eth-mainnet") -> {
  portrait_id: str
  svg: str
  features: dict[str, float]   # 8-dimension behavioral fingerprint
  metadata: dict
}`}</Code>
                <p>To connect it to Claude Code as a remote MCP server:</p>
                <Code>{`claude mcp add sigilx --transport sse http://localhost:8001/sse`}</Code>
                <p>
                    Once added, ask Claude to generate a portrait for a wallet address directly — it will call
                    <code className="font-mono text-foreground"> generate_chain_portrait</code> as a tool, the same
                    way it calls any other MCP tool. For Claude Desktop or other stdio-only MCP clients, bridge
                    the SSE endpoint with <code className="font-mono text-foreground">mcp-remote</code> in your
                    client's server config.
                </p>
            </Section>

            <Section id="x402" title="x402 payments">
                <p>
                    <code className="font-mono text-foreground">POST /generate</code> is gated behind{" "}
                    <a href="https://github.com/coinbase/x402" target="_blank" rel="noreferrer" className="text-foreground underline underline-offset-4">x402</a>,
                    the same protocol OKX's Onchain OS Payment SDK is built on. An unpaid request gets back an
                    HTTP 402 listing payment requirements; a paid retry carries an{" "}
                    <code className="font-mono text-foreground">X-PAYMENT</code> header — a base64-encoded,
                    EIP-712-signed EIP-3009 <code className="font-mono text-foreground">transferWithAuthorization</code>{" "}
                    payload — which OKX&apos;s facilitator (the &quot;Broker&quot;) verifies and settles on-chain.
                </p>
                <p>
                    For local development and judge testing, set{" "}
                    <code className="font-mono text-foreground">DEMO_MODE=true</code> and{" "}
                    <code className="font-mono text-foreground">DEMO_API_KEY</code> in <code className="font-mono text-foreground">.env</code>,
                    then pass <code className="font-mono text-foreground">X-Demo-Key</code> matching that value —
                    this bypasses the payment gate entirely so the full generate → mint flow can be exercised
                    without a funded wallet.
                </p>
            </Section>

            <Section id="references" title="References">
                <ul className="ml-4 list-disc space-y-1">
                    {REFERENCES.map((r) => (
                        <li key={r.href}>
                            <Link href={r.href} target="_blank" rel="noreferrer" className="text-foreground underline underline-offset-4">
                                {r.title}
                            </Link>
                        </li>
                    ))}
                </ul>
            </Section>
        </main>
    )
}
