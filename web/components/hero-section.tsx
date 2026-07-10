import React from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Button } from '@/components/ui/button'
import { InfiniteSlider } from '@/components/ui/infinite-slider'
import { ProgressiveBlur } from '@/components/ui/progressive-blur'
import { TextEffect } from "@/components/motion-primitives/text-effect";
import { AnimatedGroup } from "@/components/motion-primitives/animated-group";
import DecryptedText from "@/components/DecryptedText";
import { transitionVariants } from "@/lib/utils";

export default function HeroSection() {
    return (
        <main className="overflow-x-hidden">
            <section className='lg:min-h-screen'>
                <div
                    className="relative pb-24 pt-12 md:pb-32 lg:pb-24 lg:pt-24 lg:grid lg:min-h-screen lg:grid-cols-2 lg:grid-rows-1 lg:items-center grid-cols-1 grid-rows-2">
                    <div className="relative mx-auto flex max-w-xl flex-col px-6 lg:block">
                        <div className="mx-auto max-w-2xl text-center lg:ml-0 lg:text-left">
                            <div className='mt-8 lg:mt-16'>
                                <DecryptedText
                                    text="Powered by OKX Market API + X Layer"
                                    animateOn="view"
                                    revealDirection="start"
                                    sequential
                                    useOriginalCharsOnly={false}
                                    speed={70}
                                    className='font-mono text-muted-foreground bg-black rounded-md uppercase'
                                />
                            </div>
                            <TextEffect
                                preset="fade-in-blur"
                                speedSegment={0.3}
                                as="h1"
                                className="max-w-2xl text-balance text-6xl font-semibold md:text-7xl xl:text-8xl">
                                Wrap a Wallet
                            </TextEffect>
                            <TextEffect
                                preset="fade-in-blur"
                                speedSegment={0.3}
                                as="h1"
                                className="max-w-2xl text-balance text-6xl font-semibold md:text-7xl xl:text-8xl">
                                Into Art
                            </TextEffect>
                            <TextEffect
                                per="line"
                                preset="fade-in-blur"
                                speedSegment={0.3}
                                delay={0.5}
                                as="p"
                                className="mt-8 max-w-2xl text-pretty text-lg text-muted-foreground bg-black p-1 rounded-md">
                                SigilX analyzes a wallet's on-chain history with entropy and chaos math, then renders
                                it as a unique, deterministic Chain Portrait. Same wallet, same art, every time.
                            </TextEffect>
                            <AnimatedGroup
                                variants={{
                                    container: {
                                        visible: {
                                            transition: {
                                                staggerChildren: 0.05,
                                                delayChildren: 0.75,
                                            },
                                        },
                                    },
                                    ...transitionVariants,
                                }}
                                className="mt-12 flex flex-col items-center justify-center gap-2 sm:flex-row lg:justify-start"
                            >
                                <Button
                                    asChild
                                    size="lg"
                                    className="px-5 text-base">
                                    <Link href="/generate">
                                        <span className="text-nowrap">Generate Portrait</span>
                                    </Link>
                                </Button>
                                <Button
                                    key={2}
                                    asChild
                                    size="lg"
                                    variant="ghost"
                                    className="px-5 text-base bg-black/30 backdrop-blur-sm hover:bg-black/40">
                                    <Link href="/docs">
                                        <span className="text-nowrap">Read the Docs</span>
                                    </Link>
                                </Button>
                            </AnimatedGroup>
                        </div>
                    </div>
                    <div className="pointer-events-none relative flex w-full items-center justify-center lg:h-full">
                        <Image
                            src="/wallet_without_bg.png"
                            alt="SigilX wallet"
                            width={820}
                            height={820}
                            priority
                            className="w-[85%] max-w-none drop-shadow-2xl lg:w-[105%]"
                        />
                    </div>
                </div>
            </section>
            <section className="bg-background pb-16 md:pb-32">
                <AnimatedGroup
                    variants={{
                        container: {
                            visible: {
                                transition: {
                                    staggerChildren: 0.05,
                                    delayChildren: 0.75,
                                },
                            },
                        },
                        ...transitionVariants,
                    }}
                    className="group relative m-auto max-w-6xl px-6"
                >

                    <div className="flex flex-col items-center md:flex-row">
                        <div className="md:max-w-44 md:border-r md:pr-6">
                            <p className="text-end text-sm font-mono uppercase">Built with</p>
                        </div>
                        <div className="relative py-6 md:w-[calc(100%-11rem)]">
                            <InfiniteSlider
                                speedOnHover={20}
                                speed={40}
                                gap={112}>
                                <div className="flex items-center">
                                    <span className="font-mono text-lg font-semibold uppercase tracking-tight text-foreground">OKX Market API</span>
                                </div>
                                <div className="flex items-center">
                                    <span className="font-mono text-lg font-semibold uppercase tracking-tight text-foreground">X Layer</span>
                                </div>
                                <div className="flex items-center">
                                    <span className="font-mono text-lg font-semibold uppercase tracking-tight text-foreground">IPFS</span>
                                </div>
                                <div className="flex items-center">
                                    <span className="font-mono text-lg font-semibold uppercase tracking-tight text-foreground">ERC-721</span>
                                </div>
                            </InfiniteSlider>
                            <div
                                className="bg-linear-to-r from-background absolute inset-y-0 left-0 w-20"></div>
                            <div
                                className="bg-linear-to-l from-background absolute inset-y-0 right-0 w-20"></div>
                            <ProgressiveBlur
                                className="pointer-events-none absolute left-0 top-0 h-full w-20"
                                direction="left"
                                blurIntensity={1}
                            />
                            <ProgressiveBlur
                                className="pointer-events-none absolute right-0 top-0 h-full w-20"
                                direction="right"
                                blurIntensity={1}
                            />
                        </div>
                    </div>
                </AnimatedGroup>
            </section>
        </main>
    )
}
