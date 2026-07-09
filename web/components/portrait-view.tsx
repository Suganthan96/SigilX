'use client'

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { FeatureRadar } from "@/components/feature-radar"
import { FEATURE_LABELS, mintPortrait, type Portrait, type MintResult } from "@/lib/api"
import { shortenAddress } from "@/lib/utils"

export function PortraitView({ portrait }: { portrait: Portrait }) {
    const [minting, setMinting] = useState(false)
    const [mintResult, setMintResult] = useState<MintResult | null>(
        portrait.token_id
            ? {
                  success: true,
                  tx_hash: portrait.tx_hash || "",
                  token_id: portrait.token_id,
                  block_number: 0,
                  explorer_url: portrait.explorer_url || "",
                  error: "",
              }
            : null
    )
    const [mintError, setMintError] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)

    const shareUrl =
        typeof window !== "undefined"
            ? `${window.location.origin}/portrait/${portrait.portrait_id}`
            : ""

    async function handleMint() {
        setMinting(true)
        setMintError(null)
        try {
            const result = await mintPortrait(portrait.portrait_id, portrait.metadata.wallet)
            if (!result.success) {
                setMintError(result.error || "Mint failed")
            } else {
                setMintResult(result)
            }
        } catch (err) {
            setMintError(err instanceof Error ? err.message : "Mint failed")
        } finally {
            setMinting(false)
        }
    }

    function handleShare() {
        if (!shareUrl) return
        navigator.clipboard.writeText(shareUrl)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    return (
        <div className="grid gap-8 md:grid-cols-2">
            <div
                className="mx-auto aspect-square w-full max-w-[500px] overflow-hidden rounded-xl border"
                dangerouslySetInnerHTML={{ __html: portrait.svg }}
            />

            <div className="flex flex-col gap-6">
                <div>
                    <h2 className="font-mono text-lg font-semibold">{portrait.metadata.title}</h2>
                    <p className="text-muted-foreground mt-1 font-mono text-sm">
                        {shortenAddress(portrait.metadata.wallet)} · {portrait.metadata.chain} ·{" "}
                        {portrait.metadata.tx_count} txs
                    </p>
                </div>

                <FeatureRadar features={portrait.features} />

                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    {(Object.keys(FEATURE_LABELS) as (keyof typeof FEATURE_LABELS)[]).map((key) => (
                        <div key={key} className="flex items-center justify-between gap-2">
                            <dt className="text-muted-foreground">{FEATURE_LABELS[key]}</dt>
                            <dd className="font-mono">{portrait.features[key].toFixed(2)}</dd>
                        </div>
                    ))}
                </dl>

                <div className="flex flex-wrap items-center gap-3">
                    {mintResult?.success ? (
                        <Button asChild variant="outline">
                            <a href={mintResult.explorer_url} target="_blank" rel="noreferrer">
                                View mint (token #{mintResult.token_id})
                            </a>
                        </Button>
                    ) : (
                        <Button onClick={handleMint} disabled={minting}>
                            {minting ? "Minting…" : "Mint on X Layer"}
                        </Button>
                    )}
                    <Button variant="outline" onClick={handleShare}>
                        {copied ? "Link copied" : "Copy share link"}
                    </Button>
                </div>
                {mintError && <p className="text-destructive text-sm">{mintError}</p>}
            </div>
        </div>
    )
}
