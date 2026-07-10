import React from "react"
import type {Metadata} from 'next'
import {Geist, Geist_Mono} from 'next/font/google'
import {Analytics} from '@vercel/analytics/next'
import './globals.css'
import Dither from "@/components/Dither";
import CanvasErrorBoundary from "@/components/canvas-error-boundary";
import FooterSection from "@/components/footer";
import {HeroHeader} from "@/components/header";

const _geist = Geist({subsets: ["latin"]});
const _geistMono = Geist_Mono({subsets: ["latin"]});

export const metadata: Metadata = {
    title: 'SigilX — Chain Portrait',
    description: 'Turn any wallet\'s on-chain history into a unique, deterministic work of art. Same wallet, same art, every time — powered by OKX Market API and X Layer.',
    generator: 'v0.app',
    icons: {
        icon: [
            {
                url: '/icon-light-32x32.png',
                media: '(prefers-color-scheme: light)',
            },
            {
                url: '/icon-dark-32x32.png',
                media: '(prefers-color-scheme: dark)',
            },
            {
                url: '/icon.svg',
                type: 'image/svg+xml',
            },
        ],
        apple: '/apple-icon.png',
    },
}

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode
}>) {
    return (
        <html lang="en" className="dark">
        <body className="font-sans antialiased">
        <div className='absolute w-full h-dvh max-h-155 sm:max-h-115 md:max-h-125 lg:max-h-190 xl:max-h-195'>
            <CanvasErrorBoundary fallback={<div className="w-full h-full bg-background" />}>
                <Dither
                    waveColor={[0.30980392156862746, 0.30980392156862746, 0.30980392156862746]}
                    disableAnimation={false}
                    enableMouseInteraction
                    mouseRadius={0.3}
                    colorNum={4}
                    pixelSize={2}
                    waveAmplitude={0.3}
                    waveFrequency={3}
                    waveSpeed={0.05}
                />
            </CanvasErrorBoundary>
        </div>
        <HeroHeader/>
        {children}
        <FooterSection/>
        <Analytics/>
        </body>
        </html>
    )
}
