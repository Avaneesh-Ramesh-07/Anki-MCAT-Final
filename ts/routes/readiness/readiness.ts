// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Types + loader for the MCAT readiness model. The model is computed in Python
// (single source of truth: qt/aqt/mcat_readiness.py, served by the
// /_anki/mcatReadiness handler), so both the home screen and this dashboard
// show identical numbers.

export interface TopicReadiness {
    tag: string;
    label: string;
    memory: number;
    synthesis: number;
    full_length: number;
    readiness: number;
    low: number;
    high: number;
}

export interface Readiness {
    topics: TopicReadiness[];
    full: { readiness: number; low: number; high: number };
    performance: { score: number; low: number; high: number; attempts: number };
}

export async function fetchReadiness(): Promise<Readiness | null> {
    try {
        const res = await fetch("/_anki/mcatReadiness", {
            method: "POST",
            headers: { "Content-Type": "application/binary" },
            body: new Uint8Array(),
        });
        if (!res.ok) {
            return null;
        }
        return (await res.json()) as Readiness;
    } catch {
        return null;
    }
}
