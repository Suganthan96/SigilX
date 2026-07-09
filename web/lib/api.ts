/**
 * Client for the SigilX FastAPI backend (services/api).
 * Base URL is configurable via NEXT_PUBLIC_API_BASE_URL for local dev vs. deployed environments.
 */

export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export interface FeatureVector {
    activity_entropy: number
    timing_regularity: number
    amount_variance: number
    interaction_diversity: number
    burst_coefficient: number
    recency_decay: number
    volume_skew: number
    chaos_dimension: number
}

export const FEATURE_LABELS: Record<keyof FeatureVector, string> = {
    activity_entropy: "Activity Entropy",
    timing_regularity: "Timing Regularity",
    amount_variance: "Amount Variance",
    interaction_diversity: "Interaction Diversity",
    burst_coefficient: "Burst Coefficient",
    recency_decay: "Recency Decay",
    volume_skew: "Volume Skew",
    chaos_dimension: "Chaos Dimension",
}

export interface PortraitMetadata {
    title: string
    wallet: string
    chain: string
    generated_at: string
    tx_count: number
    svg_hash: string
    portrait_id: string
}

export interface Portrait {
    portrait_id: string
    svg: string
    features: FeatureVector
    metadata: PortraitMetadata
    cached?: boolean
    token_id?: number
    tx_hash?: string
    explorer_url?: string
}

export interface ApiErrorBody {
    error: string
    message?: string
    tx_count?: number
    minimum_required?: number
}

export class SigilXApiError extends Error {
    status: number
    body: ApiErrorBody | null

    constructor(status: number, body: ApiErrorBody | null) {
        super(body?.message || body?.error || `Request failed (${status})`)
        this.status = status
        this.body = body
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...(process.env.NEXT_PUBLIC_DEMO_API_KEY
                ? { "X-Demo-Key": process.env.NEXT_PUBLIC_DEMO_API_KEY }
                : {}),
            ...init?.headers,
        },
    })

    if (!res.ok) {
        let body: ApiErrorBody | null = null
        try {
            const parsed = await res.json()
            body = parsed.detail ?? parsed
        } catch {
            // non-JSON error body — leave body null
        }
        throw new SigilXApiError(res.status, body)
    }

    return res.json() as Promise<T>
}

export function generatePortrait(walletAddress: string, chain: string): Promise<Portrait> {
    return request<Portrait>("/generate", {
        method: "POST",
        body: JSON.stringify({ wallet_address: walletAddress, chain }),
    })
}

export function getPortrait(portraitId: string): Promise<Portrait> {
    return request<Portrait>(`/portrait/${portraitId}`)
}

export interface MintResult {
    success: boolean
    tx_hash: string
    token_id: number
    block_number: number
    explorer_url: string
    error: string
}

export function mintPortrait(portraitId: string, toAddress: string): Promise<MintResult> {
    return request<MintResult>("/mint", {
        method: "POST",
        body: JSON.stringify({ portrait_id: portraitId, to_address: toAddress }),
    })
}

export interface SupportedChain {
    id: string
    chain_id: string
}

export function getSupportedChains(): Promise<{ supported_chains: SupportedChain[] }> {
    return request("/chains")
}
