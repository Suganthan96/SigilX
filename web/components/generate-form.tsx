"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { PortraitView } from "@/components/portrait-view"
import {
    generatePortrait,
    getSupportedChains,
    SigilXApiError,
    type Portrait,
    type SupportedChain,
} from "@/lib/api"

const FALLBACK_CHAINS: SupportedChain[] = [
    { id: "eth-mainnet", chain_id: "1" },
    { id: "polygon-mainnet", chain_id: "137" },
    { id: "bsc-mainnet", chain_id: "56" },
    { id: "xlayer-mainnet", chain_id: "196" },
    { id: "arbitrum-mainnet", chain_id: "42161" },
    { id: "optimism-mainnet", chain_id: "10" },
    { id: "base-mainnet", chain_id: "8453" },
]

function isValidAddress(value: string) {
    return /^0x[a-fA-F0-9]{40}$/.test(value.trim())
}

export function GenerateForm() {
    const router = useRouter()
    const [wallet, setWallet] = useState("")
    const [chain, setChain] = useState("eth-mainnet")
    const [chains, setChains] = useState<SupportedChain[]>(FALLBACK_CHAINS)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [portrait, setPortrait] = useState<Portrait | null>(null)

    useEffect(() => {
        getSupportedChains()
            .then((res) => {
                if (res.supported_chains?.length) setChains(res.supported_chains)
            })
            .catch(() => {
                // keep fallback list — backend may be offline during static preview
            })
    }, [])

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        if (!isValidAddress(wallet)) {
            setError("Enter a valid EVM address — 0x followed by 40 hex characters.")
            return
        }
        setLoading(true)
        setError(null)
        setPortrait(null)
        try {
            const result = await generatePortrait(wallet.trim(), chain)
            setPortrait(result)
        } catch (err) {
            if (err instanceof SigilXApiError) {
                setError(err.body?.message || err.body?.error || err.message)
            } else {
                setError(err instanceof Error ? err.message : "Generation failed")
            }
        } finally {
            setLoading(false)
        }
    }

    if (portrait) {
        return (
            <div className="flex flex-col gap-8">
                <PortraitView portrait={portrait} />
                <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={() => setPortrait(null)}>
                        Generate another
                    </Button>
                    <Button variant="outline" onClick={() => router.push(`/portrait/${portrait.portrait_id}`)}>
                        Open shareable page
                    </Button>
                </div>
            </div>
        )
    }

    return (
        <form onSubmit={handleSubmit} className="mx-auto flex max-w-lg flex-col gap-5">
            <div className="flex flex-col gap-2">
                <label htmlFor="wallet" className="font-mono text-sm text-muted-foreground">
                    Wallet address
                </label>
                <input
                    id="wallet"
                    value={wallet}
                    onChange={(e) => setWallet(e.target.value)}
                    placeholder="0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                    className="h-11 w-full rounded-md border border-border bg-background px-3 font-mono text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring"
                    autoComplete="off"
                    spellCheck={false}
                />
            </div>

            <div className="flex flex-col gap-2">
                <label htmlFor="chain" className="font-mono text-sm text-muted-foreground">
                    Chain
                </label>
                <select
                    id="chain"
                    value={chain}
                    onChange={(e) => setChain(e.target.value)}
                    className="h-11 w-full rounded-md border border-border bg-background px-3 font-mono text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                    {chains.map((c) => (
                        <option key={c.id} value={c.id}>
                            {c.id}
                        </option>
                    ))}
                </select>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button type="submit" size="lg" disabled={loading}>
                {loading ? "Analyzing wallet…" : "Generate Portrait"}
            </Button>
        </form>
    )
}
