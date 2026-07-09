'use client'

import { useState, type FormEvent } from "react"
import { Button } from "@/components/ui/button"
import { PortraitView } from "@/components/portrait-view"
import { generatePortrait, SigilXApiError, type Portrait } from "@/lib/api"

const CHAINS = [
    { id: "eth-mainnet", label: "Ethereum" },
    { id: "polygon-mainnet", label: "Polygon" },
    { id: "bsc-mainnet", label: "BNB Chain" },
    { id: "xlayer-mainnet", label: "X Layer" },
    { id: "arbitrum-mainnet", label: "Arbitrum" },
    { id: "optimism-mainnet", label: "Optimism" },
    { id: "base-mainnet", label: "Base" },
]

const ADDRESS_RE = /^0x[a-fA-F0-9]{40}$/

export function WalletForm() {
    const [address, setAddress] = useState("")
    const [chain, setChain] = useState("eth-mainnet")
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [portrait, setPortrait] = useState<Portrait | null>(null)

    async function handleSubmit(e: FormEvent) {
        e.preventDefault()
        setError(null)

        if (!ADDRESS_RE.test(address.trim())) {
            setError("Enter a valid EVM address (0x followed by 40 hex characters).")
            return
        }

        setLoading(true)
        setPortrait(null)
        try {
            const result = await generatePortrait(address.trim(), chain)
            setPortrait(result)
        } catch (err) {
            if (err instanceof SigilXApiError && err.body?.error === "insufficient_history") {
                setError(
                    `This wallet only has ${err.body.tx_count} transactions — at least ${err.body.minimum_required} are needed to generate a portrait.`
                )
            } else {
                setError(err instanceof Error ? err.message : "Something went wrong.")
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="mx-auto max-w-3xl px-6 py-16">
            <div className="text-center">
                <h1 className="text-4xl font-semibold text-balance md:text-5xl">
                    Turn a wallet into art
                </h1>
                <p className="text-muted-foreground mx-auto mt-4 max-w-xl text-pretty">
                    SigilX analyzes a wallet&apos;s on-chain transaction history with entropy
                    and chaos math, then renders the result as a unique, deterministic
                    generative artwork. Same wallet, same art, every time.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="mx-auto mt-10 flex max-w-xl flex-col gap-3 sm:flex-row">
                <input
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="0x…"
                    spellCheck={false}
                    className="border-input bg-background flex-1 rounded-md border px-3 py-2 font-mono text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                />
                <select
                    value={chain}
                    onChange={(e) => setChain(e.target.value)}
                    className="border-input bg-background rounded-md border px-3 py-2 text-sm outline-none"
                >
                    {CHAINS.map((c) => (
                        <option key={c.id} value={c.id}>
                            {c.label}
                        </option>
                    ))}
                </select>
                <Button type="submit" disabled={loading}>
                    {loading ? "Generating…" : "Generate"}
                </Button>
            </form>

            {error && <p className="text-destructive mt-4 text-center text-sm">{error}</p>}

            {portrait && (
                <div className="mt-16">
                    <PortraitView portrait={portrait} />
                </div>
            )}
        </div>
    )
}
