'use client'

import {
    PolarAngleAxis,
    PolarGrid,
    Radar,
    RadarChart,
    ResponsiveContainer,
} from "recharts"
import { FEATURE_LABELS, type FeatureVector } from "@/lib/api"

export function FeatureRadar({ features }: { features: FeatureVector }) {
    const data = (Object.keys(FEATURE_LABELS) as (keyof FeatureVector)[]).map((key) => ({
        feature: FEATURE_LABELS[key].replace(" ", "\n"),
        value: Math.round(features[key] * 100),
    }))

    return (
        <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={data} outerRadius="75%">
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis
                        dataKey="feature"
                        tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                    />
                    <Radar
                        dataKey="value"
                        stroke="var(--chart-1)"
                        fill="var(--chart-1)"
                        fillOpacity={0.35}
                    />
                </RadarChart>
            </ResponsiveContainer>
        </div>
    )
}
