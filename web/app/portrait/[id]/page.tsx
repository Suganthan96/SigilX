import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { PortraitView } from "@/components/portrait-view"
import { getPortrait, SigilXApiError } from "@/lib/api"
import { shortenAddress } from "@/lib/utils"

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"

interface PageProps {
    params: Promise<{ id: string }>
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { id } = await params

    try {
        const portrait = await getPortrait(id)
        const title = `${portrait.metadata.title} | SigilX`
        const description = `On-chain behavioral fingerprint for ${shortenAddress(
            portrait.metadata.wallet
        )} on ${portrait.metadata.chain}, rendered as generative art by SigilX.`
        const ogImageUrl = `${SITE_URL}/api/og?id=${id}`

        return {
            title,
            description,
            openGraph: {
                title,
                description,
                url: `${SITE_URL}/portrait/${id}`,
                type: "website",
                images: [{ url: ogImageUrl, width: 1200, height: 630, alt: title }],
            },
            twitter: {
                card: "summary_large_image",
                title,
                description,
                images: [ogImageUrl],
            },
        }
    } catch {
        return { title: "Chain Portrait | SigilX" }
    }
}

export default async function PortraitPage({ params }: PageProps) {
    const { id } = await params

    try {
        const portrait = await getPortrait(id)
        return (
            <main className="mx-auto max-w-4xl px-6 py-16">
                <PortraitView portrait={portrait} />
            </main>
        )
    } catch (err) {
        if (err instanceof SigilXApiError && err.status === 404) {
            notFound()
        }
        throw err
    }
}

// Ensures fresh data — the backend is the source of truth (in-memory cache).
export const dynamic = "force-dynamic"
