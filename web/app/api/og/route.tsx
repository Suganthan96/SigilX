import { ImageResponse } from "next/og"
import { FEATURE_LABELS, getPortrait, SigilXApiError, type FeatureVector } from "@/lib/api"
import { shortenAddress } from "@/lib/utils"

export const runtime = "edge"

function hueFor(features: FeatureVector): number {
    // Mirrors the low->high mapping in services/renderer/palette.py (195 = teal, 320 = violet-red)
    return 195 + (320 - 195) * features.activity_entropy
}

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url)
        const id = searchParams.get("id")

        if (!id) {
            return new Response("Missing ?id=", { status: 400 })
        }

        const portrait = await getPortrait(id)
        const hue = hueFor(portrait.features)
        const bg = `hsl(${hue}, 30%, 8%)`
        const accent = `hsl(${hue}, 70%, 55%)`

        const keys = Object.keys(FEATURE_LABELS) as (keyof FeatureVector)[]

        return new ImageResponse(
            (
                <div
                    style={{
                        height: "100%",
                        width: "100%",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        backgroundColor: bg,
                        padding: "64px",
                        fontFamily: "sans-serif",
                    }}
                >
                    <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ color: accent, fontSize: 28, letterSpacing: 4, textTransform: "uppercase" }}>
                            SigilX · Chain Portrait
                        </span>
                        <span style={{ color: "#ffffff", fontSize: 56, marginTop: 16, fontWeight: 600 }}>
                            {shortenAddress(portrait.metadata.wallet)}
                        </span>
                        <span style={{ color: "#aaaaaa", fontSize: 28, marginTop: 8 }}>
                            {portrait.metadata.chain} · {portrait.metadata.tx_count} transactions analyzed
                        </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "flex-end", gap: 16, height: 160 }}>
                        {keys.map((key) => (
                            <div key={key} style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 100 }}>
                                <div
                                    style={{
                                        width: 32,
                                        height: Math.max(8, portrait.features[key] * 140),
                                        backgroundColor: accent,
                                        borderRadius: 6,
                                    }}
                                />
                            </div>
                        ))}
                    </div>
                </div>
            ),
            { width: 1200, height: 630 }
        )
    } catch (e) {
        if (e instanceof SigilXApiError && e.status === 404) {
            return new Response("Portrait not found", { status: 404 })
        }
        console.log(`OG Image Generation Error: ${e}`)
        return new Response("Failed to generate the image", { status: 500 })
    }
}
