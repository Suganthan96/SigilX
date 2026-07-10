"use client";

import Image from "next/image";
import {useState} from "react";
import {TextEffect} from "@/components/motion-primitives/text-effect";
import {transitionVariants} from "@/lib/utils";
import {AnimatedGroup} from "@/components/motion-primitives/animated-group";

function EntropyPreview() {
    return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
            <polyline
                points="0,140 12,90 24,160 36,70 48,130 60,50 72,150 84,80 96,170 108,60 120,140 132,90 144,175 156,55 168,145 180,100 192,160 200,90"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-foreground"
            />
            <polyline
                points="0,120 12,150 24,100 36,155 48,90 60,145 72,95 84,160 96,110 108,150 120,80 132,155 144,100 156,140 168,85 180,150 192,105 200,140"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                opacity="0.4"
                className="text-foreground"
            />
        </svg>
    );
}

function AttractorPreview() {
    const dots = Array.from({length: 90}).map((_, i) => {
        const a = i * 2.399963;
        const r = 6 + i * 1.55;
        const x = 100 + r * Math.cos(a) * 0.9;
        const y = 100 + r * Math.sin(a);
        return {x, y, r: 1 + (i % 5) * 0.35};
    });
    return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
            {dots.map((d, i) => (
                <circle key={i} cx={d.x} cy={d.y} r={d.r} className="fill-foreground" opacity={0.15 + (i % 6) * 0.12}/>
            ))}
        </svg>
    );
}

const STEPS = [
    {
        num: "01",
        title: "Wallet In",
        desc: "Submit any EVM wallet address — no signup, no wallet connect required.",
        preview: {type: "image" as const, src: "/wallet_without_bg.png"},
    },
    {
        num: "02",
        title: "Entropy Analysis",
        desc: "Sample Entropy, Correlation Dimension, and Burstiness extracted from the transaction history.",
        preview: {type: "svg" as const, node: <EntropyPreview/>},
    },
    {
        num: "03",
        title: "Generative Render",
        desc: "The feature vector maps deterministically to a 600×600 animated SVG portrait.",
        preview: {type: "svg" as const, node: <AttractorPreview/>},
    },
    {
        num: "04",
        title: "Mint on X Layer",
        desc: "Lock it in as an ERC-721 — feature vector and SVG hash stored immutably on-chain.",
        preview: {type: "image" as const, src: "/logo_without_bg.png"},
    },
];

export default function Agenda() {
    const [active, setActive] = useState(0);
    const activeStep = STEPS[active];

    return (
        <section className="scroll-py-16 py-16 md:scroll-py-32 md:py-32">
            <div className="mx-auto max-w-5xl px-6">
                <div className="grid gap-y-12 lg:grid-cols-[1fr_auto] px-2">
                    <div className="flex flex-col text-center lg:text-left">
                        <TextEffect
                            triggerOnView
                            preset="fade-in-blur"
                            speedSegment={0.3}
                            as="h2"
                            className="mb-4 text-3xl font-semibold md:text-4xl">
                            How It Works
                        </TextEffect>
                        <div
                            key={active}
                            className="mx-auto mt-6 aspect-square w-full max-w-sm animate-in fade-in duration-500 rounded-2xl border border-dashed border-border bg-muted/20 p-10 lg:mx-0">
                            {activeStep.preview.type === "image" ? (
                                <Image
                                    src={activeStep.preview.src}
                                    alt={activeStep.title}
                                    width={400}
                                    height={400}
                                    className="h-full w-full object-contain drop-shadow-xl"
                                />
                            ) : (
                                activeStep.preview.node
                            )}
                        </div>
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
                        {STEPS.map((step, i) => (
                            <div
                                key={step.num}
                                onMouseEnter={() => setActive(i)}
                                className={`cursor-default py-6 first:pt-0 transition-opacity ${active === i ? "opacity-100" : "opacity-60"}`}
                            >
                                <div className="font-medium space-x-2">
                                    <span className='text-muted-foreground font-mono '>{step.num}</span>
                                    <span>{step.title}</span>
                                </div>
                                <p className="text-muted-foreground mt-4">{step.desc}</p>
                            </div>
                        ))}
                    </AnimatedGroup>
                </div>
            </div>
        </section>
    )
}
