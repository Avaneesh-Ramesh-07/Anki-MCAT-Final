# MCAT-on-Anki — Wednesday Submission

A fork of [Anki](https://github.com/ankitects/anki) that builds MCAT-readiness
features **directly into the existing codebase** (Rust core, Python/Qt, Svelte) —
not a plugin or add-on. AGPL-3.0-or-later; credit to Anki (parts BSD-3). Product
scope: [anki_prd_mvp.md](anki_prd_mvp.md). No AI in the MVP.

## What's the real engine change?

**The Mastery Query — the memory model.** A new backend RPC, implemented in the
shared Rust core, that returns **per AAMC topic**: a comfort-augmented memory
score, a statistical confidence range, mastered-card counts, and an abstain flag
(the give-up rule). It runs over the collection's SQLite, so the same compiled
query ships to desktop and (via `rsdroid`) the phone with no reimplementation.

## Wednesday deliverable status (honest)

| Item                                                              | Status                                          |
| ----------------------------------------------------------------- | ----------------------------------------------- |
| Anki forked & building from source                                | ✅ Done                                         |
| Rust change end-to-end (diff + 3 Rust tests + 1 Python test)      | ✅ Done & passing                               |
| Review loop on the exam deck                                      | ✅ Done (vanilla reviewer + tagged sample deck) |
| Memory model with honest score (range + give-up rule)             | ✅ Done (+ readiness dashboard UI)              |
| Desktop installer on a clean machine                              | ⏳ Build attempted — see "Installer" below      |
| Mobile: phone builds + runs a review session on the shared engine | ❌ Not done (see "Mobile")                      |
| Proof recordings (build / install / phone)                        | ⛔ Manual capture (yours)                       |

## How to build & run (desktop)

```powershell
just run            # builds Rust + web + Qt and launches Anki
```

To see the feature: **File → Import → `tools/mcat_sample.apkg`**, then
**Tools → MCAT Readiness**. The sample deck has five `aamc::`-tagged, pre-reviewed
topics; one (`aamc::psych-soc::memory`) was answered slowly so its score is
visibly discounted by the comfort signal.

> Adding/renaming a SvelteKit route needs a web rebuild that `just run` doesn't
> trigger on Windows: `tools\ninja sveltekit` (after the route files exist).

## How to run the tests

This machine has **Smart App Control (Enforce)**, which blocks `cargo install
cargo-nextest`, so `just test-rust` fails. Run the Rust tests directly instead:

```powershell
$env:CARGO_TARGET_DIR='out\rust'; $env:CARGO_HTTP_CHECK_REVOKE='false'; cargo test -p anki mcat
```

→ `test result: ok. 3 passed` (`wilson_interval_behaves`, `empty_collection_abstains`, `groups_unstudied_cards_by_aamc_tag`).

```powershell
out\pyenv\Scripts\pytest.exe pylib\tests\test_mcat.py
```

→ `1 passed` (full Python → generated binding → Rust backend chain).

## The memory model (one-pager)

Per AAMC topic (the `aamc::section::topic` note tag — the shared key for the
whole MVP), over the topic's cards:

- **Score** = mean **FSRS retrievability** (unstudied cards = 0) **× a comfort
  factor**. The comfort factor = `1 − 0.20 × (effortful ÷ reviews)`, where an
  "effortful" review is a Good/Easy rating answered **slower than 1.5× the user's
  median latency** (Insight 3: slow + confident = likely overconfidence). This is
  the "DSR the app already computes, augmented by the answer-time comfort change."
- **Range** = a **Wilson 95% interval** on (mean retrievability, n = reviews),
  scaled by the comfort factor — wider when evidence is thin (honest uncertainty).
- **Mastered** = cards with retrievability ≥ 0.9.
- **Give-up rule** = **abstain** (show no number) until the topic has ≥ N graded
  reviews (v1 default N = 5; tunable).
- **Overall** = the same aggregation across all cards.

Pure statistics over data Anki already stores (`RevlogEntry.taken_millis`,
`FsrsMemoryState`, retrievability) — no AI. The thresholds (0.9 mastered, 0.20
comfort cap, 1.5× slow, N = 5) are documented v1 defaults, not yet calibrated.

## Why Rust, not Python

The aggregation scans the whole card + revlog set per dashboard load and must hit
the perf budget on a 50k-card deck. In Rust over SQLite it avoids marshalling the
full card set across the PyO3 / JNI boundary, and the same compiled query is the
one that ships to the phone via `rsdroid` — a Python implementation would have to
be rewritten for Android.

## Files touched (the change)

**New:**

- `proto/anki/mcat.proto` — `McatService.MasteryQuery` + messages.
- `rslib/src/mcat/{mod,service,mastery}.rs` — the memory-model engine + 3 unit tests.
- `qt/aqt/mcat.py` — the readiness dashboard window (API-enabled webview).
- `ts/routes/readiness/{+page.ts,+page.svelte,ReadinessDashboard.svelte}` — the dashboard UI.
- `pylib/tests/test_mcat.py` — the Python-calling test.
- `tools/build_mcat_sample.py` (+ `tools/mcat_sample.apkg`) — the tagged sample deck.

**Modified (wiring):**

- `rslib/src/lib.rs` (`pub mod mcat;`), `rslib/proto/src/lib.rs` (`protobuf!(mcat)`), `rslib/proto/python.rs` (`import anki.mcat_pb2`).
- `qt/aqt/mediasrv.py` (expose RPC + register the `readiness` page), `qt/aqt/webview.py` (`READINESS` webview kind + API access), `qt/aqt/main.py` (Tools → MCAT Readiness).

**Undo / corruption:** the Mastery Query is **read-only** (it never writes to the
collection), so it cannot corrupt data or break undo.

**Upstream-merge difficulty:** low–moderate. The change is mostly additive (a new
proto + a new `rslib/src/mcat/` module + new Svelte route). The only edits to
shared files are small list/registration additions (module lists, the webview
kind, one menu line), which rebase cleanly.

## Installer

Built with `tools\ninja installer` (RELEASE=2, Briefcase). See the build log /
`out/` for the produced artifact. If the build fails here it's an environment
issue (this machine's Smart App Control blocks fresh release binaries, and the
briefcase windows-template clone was already failing in `test_installer.py`); the
clean path is to build it in CI (`.github/workflows/ci.yml`) or on a machine
without Smart App Control.

## Mobile (not done — what it needs)

Anki is one engine, two clients. The memory-model **engine** already lives in the
shared `anki` crate, so it reaches the phone automatically **once AnkiDroid is
built against this fork** — but that build is not set up, and it's the prerequisite
for the Wednesday "review session on the shared engine" bar. Steps:

1. Clone `ankidroid/Anki-Android` and `ankidroid/Anki-Android-Backend` (rsdroid).
2. Point `rsdroid`'s `anki` dependency at this fork; build the `.so` with `cargo-ndk`.
3. Build the AnkiDroid APK and run it on an emulator; import the deck; review.

**Blocker on this machine:** the `cargo-ndk` native cross-build produces fresh
unsigned binaries that **Smart App Control (Enforce) will block** — the same wall
that stopped `cargo-nextest`. Realistic options: build the Android engine in **CI
/ WSL / a non-SAC machine**, or disable Smart App Control (irreversible without a
Windows reset). Showing the scores on the phone additionally needs a small **Kotlin
screen** that calls the `mastery_query` RPC over JNI (the engine is already there).
