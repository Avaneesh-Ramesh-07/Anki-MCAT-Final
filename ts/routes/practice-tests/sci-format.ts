// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

// Display-only scientific-notation formatter for practice-test text.
//
// - Caret exponents become Unicode superscripts: `s^2` -> `s²`, `m^-1` -> `m⁻¹`,
//   `2^n` -> `2ⁿ`, `10^-3` -> `10⁻³`.
// - Chemical formulas become Unicode subscripts: `O2` -> `O₂`, `H2O` -> `H₂O`,
//   `CO2` -> `CO₂`, `C6H12O6` -> `C₆H₁₂O₆`. A leading coefficient is NOT a
//   subscript (`2O` stays `2O`, `2H2O` -> `2H₂O`), matching the chemical meaning.
// - Ionic charges become superscripts: `Na+` -> `Na⁺`, `Ca2+` -> `Ca²⁺`.
//
// This is purely presentational: the stored question data stays ASCII, so
// grading, keyword matching, and answer comparison are unaffected. Only element
// symbols are treated as formula starts, so lookalikes (`R1`, `G1`, `Ch3`) and
// hyphenated terms (`O-linked`, `C-terminal`, `K-channel`) are left untouched.

const SUP: Record<string, string> = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    n: "ⁿ",
    x: "ˣ",
    i: "ⁱ",
};
const SUB: Record<string, string> = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
};

function toSup(s: string): string | null {
    let out = "";
    for (const ch of s) {
        const m = SUP[ch];
        if (m === undefined) {
            return null;
        }
        out += m;
    }
    return out;
}

function toSub(s: string): string {
    let out = "";
    for (const ch of s) {
        out += SUB[ch] ?? ch;
    }
    return out;
}

// Common element symbols, longest-first so "Ca" matches before "C".
const ELEMENTS = [
    "He",
    "Li",
    "Be",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "Cl",
    "Ar",
    "Ca",
    "Sc",
    "Ti",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Ag",
    "Cd",
    "Sn",
    "Sb",
    "Te",
    "Xe",
    "Cs",
    "Ba",
    "Pt",
    "Au",
    "Hg",
    "Pb",
    "Bi",
    "H",
    "B",
    "C",
    "N",
    "O",
    "F",
    "P",
    "S",
    "K",
    "V",
    "I",
    "U",
    "W",
];
const EL = `(?:${ELEMENTS.join("|")})`;
// A formula token: starts with an element symbol, is a run of element symbols
// and digit counts, with an optional trailing ionic charge, and is bounded by
// non-letters (so we never grab the head/tail of an ordinary word).
const FORMULA = new RegExp(
    `(?<![A-Za-z])(${EL}(?:\\d+|${EL})*(?:\\d*[+-])?)(?![A-Za-z])`,
    "g",
);

function formatFormula(tok: string): string {
    let out = "";
    let i = 0;
    while (i < tok.length) {
        const ch = tok[i];
        if (ch >= "0" && ch <= "9") {
            let j = i;
            while (j < tok.length && tok[j] >= "0" && tok[j] <= "9") {
                j++;
            }
            const digits = tok.slice(i, j);
            const next = tok[j];
            if (next === "+" || next === "-") {
                // charge magnitude, e.g. the "2" in Ca2+ -> superscript
                out += (toSup(digits) ?? digits) + (SUP[next] ?? next);
                i = j + 1;
            } else {
                // atom count, e.g. the "2" in O2 -> subscript
                out += toSub(digits);
                i = j;
            }
        } else if (ch === "+" || ch === "-") {
            out += SUP[ch] ?? ch; // lone charge sign, e.g. Na+
            i++;
        } else {
            out += ch; // element letter
            i++;
        }
    }
    return out;
}

/** Render caret exponents as superscripts and chemical formulas with
 * subscripts/charge superscripts. Presentational only. */
export function formatSci(text: string | null | undefined): string {
    if (!text) {
        return text ?? "";
    }
    // 1) caret exponents -> superscript
    let out = text.replace(
        /\^\{?([+-]?[0-9]+|[A-Za-z])\}?/g,
        (m, e: string) => toSup(e) ?? m,
    );
    // 2) chemical formulas -> subscripts / charge superscripts
    out = out.replace(FORMULA, (m) => (/[0-9+-]/.test(m) ? formatFormula(m) : m));
    return out;
}
