import {TextEffect} from "@/components/motion-primitives/text-effect";
import React from "react";
import {transitionVariants} from "@/lib/utils";
import {AnimatedGroup} from "@/components/motion-primitives/animated-group";

export default function Agenda() {
    return (
        <section className="scroll-py-16 py-16 md:scroll-py-32 md:py-32">
            <div className="mx-auto max-w-5xl px-6">
                <div className="grid gap-y-12 px-2 lg:grid-cols-[1fr_auto]">
                    <div className="text-center lg:text-left">
                        <TextEffect
                            triggerOnView
                            preset="fade-in-blur"
                            speedSegment={0.3}
                            as="h2"
                            className="mb-4 text-3xl font-semibold md:text-4xl">
                            How It Works
                        </TextEffect>
                    </div>

                    <AnimatedGroup
                        triggerOnView
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
                        className="divide-y divide-dashed sm:mx-auto sm:max-w-lg lg:mx-0"
                    >
                        <div className="pb-6">
                            <div className="font-medium space-x-2">
                                <span className='text-muted-foreground font-mono '>01</span>
                                <span>Wallet In</span>
                            </div>
                            <p className="text-muted-foreground mt-4">Submit any EVM wallet address — no signup, no wallet connect required.</p>
                        </div>
                        <div className="py-6">
                            <div className="font-medium space-x-2">
                                <span className='text-muted-foreground font-mono '>02</span>
                                <span>Entropy Analysis</span>
                            </div>
                            <p className="text-muted-foreground mt-4">Sample Entropy, Correlation Dimension, and Burstiness extracted from the transaction history.</p>
                        </div>
                        <div className="py-6">
                            <div className="font-medium space-x-2">
                                <span className='text-muted-foreground font-mono '>03</span>
                                <span>Generative Render</span>
                            </div>
                            <p className="text-muted-foreground mt-4">The feature vector maps deterministically to a 600×600 animated SVG portrait.</p>
                        </div>
                        <div className="py-6">
                            <div className="font-medium space-x-2">
                                <span className='text-muted-foreground font-mono '>04</span>
                                <span>Mint on X Layer</span>
                            </div>
                            <p className="text-muted-foreground mt-4">Lock it in as an ERC-721 — feature vector and SVG hash stored
                                immutably on-chain.</p>
                        </div>
                    </AnimatedGroup>
                </div>
            </div>
        </section>
    )
}
