import type { Metadata } from "next"
import { GenerateForm } from "@/components/generate-form"

export const metadata: Metadata = {
    title: "Generate a Portrait | SigilX",
    description: "Turn any EVM wallet's on-chain history into a deterministic Chain Portrait.",
}

export default function GeneratePage() {
    return (
        <main className="mx-auto max-w-4xl px-6 pb-24 pt-32 md:pt-40">
            <div className="mb-10 text-center">
                <h1 className="text-3xl font-semibold md:text-4xl">Generate a Chain Portrait</h1>
                <p className="mt-3 text-muted-foreground">
                    Paste any EVM wallet address. SigilX pulls its on-chain history from the OKX Market API,
                    extracts an 8-dimension behavioral fingerprint, and renders it as a deterministic SVG —
                    same wallet, same art, every time.
                </p>
            </div>
            <GenerateForm />
        </main>
    )
}
