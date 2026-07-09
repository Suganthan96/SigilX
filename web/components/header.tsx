'use client'
import Link from 'next/link'
import React from 'react'

export const HeroHeader = () => {
    return (
        <header>
            <nav className="bg-background/50 fixed z-20 w-full border-b backdrop-blur-3xl">
                <div className="mx-auto max-w-6xl px-6">
                    <div className="flex items-center justify-between gap-6 py-4">
                        <Link href="/" aria-label="home" className="flex items-center gap-2">
                            <span className="font-mono text-lg font-semibold tracking-tight">
                                Sigil<span className="text-muted-foreground">X</span>
                            </span>
                        </Link>
                        <span className="text-muted-foreground hidden font-mono text-xs uppercase tracking-widest sm:block">
                            Chain Portrait
                        </span>
                    </div>
                </div>
            </nav>
        </header>
    )
}
