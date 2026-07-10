import Link from 'next/link'
import Image from 'next/image'
import React from "react";

const links = [
    {
        title: 'X Layer',
        href: 'https://www.oklink.com/xlayer-test',
    },
    {
        title: 'OKX Market API',
        href: 'https://www.okx.com/web3/build/docs/waas/rest-market',
    },
    {
        title: 'Docs',
        href: '/docs',
    },
]

export default function FooterSection() {
    return (
        <footer className="py-16 md:py-32">
            <div className="mx-auto max-w-5xl px-6">
                <Link
                    href="/"
                    aria-label="go home"
                    className="mx-auto flex size-fit items-center gap-2">
                    <Image src="/SigilX.png" alt="SigilX" width={30} height={30} className="rounded-sm"/>
                    <span className="font-mono text-foreground">SigilX</span>
                </Link>

                <div className="my-8 flex flex-wrap justify-center gap-6 text-sm">
                    {links.map((link, index) => (
                        <Link
                            key={index}
                            href={link.href}
                            className="text-muted-foreground hover:text-primary block duration-150">
                            <span>{link.title}</span>
                        </Link>
                    ))}
                </div>
                <span className="text-muted-foreground block text-center text-sm font-mono">Chain Portraits, deterministically rendered • Powered by OKX Market API + X Layer.</span>
            </div>
        </footer>
    )
}
