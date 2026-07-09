import {type ClassValue, clsx} from 'clsx'
import {twMerge} from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

/** Shortens a 0x wallet address for display, e.g. 0x1234...abcd */
export function shortenAddress(address: string): string {
    if (!address || address.length < 10) return address
    return `${address.slice(0, 6)}…${address.slice(-4)}`
}
