# Speedrun Tech Stack — MCAT Study App on Anki (Desktop + Android)

> One Rust engine (`anki` crate, `rslib/`), two clients. Every engine change lands in
> `rslib` and ships to both. License: **AGPL-3.0-or-later**, credit to Anki (parts BSD-3).
> Product scope lives in [anki_prd_mvp.md](anki_prd_mvp.md) / [anki_prd_post_mvp.md](anki_prd_post_mvp.md).

## 1. Two apps, one engine (hero view)

```mermaid
flowchart TB
    subgraph DESKTOP["Desktop App — this repo"]
        direction TB
        DTUI["Web UI<br/>SvelteKit + TS + Vite<br/>(ts/routes/)"]
        DTQT["Native shell<br/>PyQt6 + QtWebEngine<br/>(qt/aqt/)"]
        DTPY["Python lib 'anki'<br/>(pylib/anki/)"]
        DTUI --> DTQT --> DTPY
    end

    subgraph ANDROID["Phone Companion — AnkiDroid fork"]
        direction TB
        ADUI["Kotlin UI<br/>(AnkiDroid)"]
        ADJNI["rsdroid<br/>JNI bridge"]
        ADUI --> ADJNI
    end

    subgraph ENGINE["Shared Rust Engine — 'anki' crate (rslib/)"]
        direction TB
        BK["Backend dispatch<br/>(rslib/src/backend)"]
        SCHED["Scheduler + FSRS 5.2<br/>(rslib/src/scheduler)"]
        STORE["SQLite collection + revlog<br/>(rslib/src/storage)"]
        SYNCC["Sync client<br/>(rslib/src/sync)"]
        MCAT["NEW: MCAT services<br/>readiness / practice-test / comfort"]
        BK --> SCHED
        BK --> STORE
        BK --> SYNCC
        BK --> MCAT
    end

    DTPY -->|"PyO3 cdylib · protobuf bytes<br/>(pylib/rsbridge)"| BK
    ADJNI -->|"JNI cdylib · protobuf bytes"| BK
    SYNCC <-->|"Zstd-JSON / HTTP · USN merge"| SS["anki-sync-server (Axum)<br/>self-hosted (rslib/sync/)"]

    classDef engine fill:#1f6feb,stroke:#0d2b66,color:#fff;
    classDef newwork fill:#d29922,stroke:#7a5b00,color:#fff;
    classDef desktop fill:#2da44e,stroke:#0b3d1c,color:#fff;
    classDef android fill:#8957e5,stroke:#3b1f6b,color:#fff;
    classDef infra fill:#6e7781,stroke:#30363d,color:#fff;
    class BK,SCHED,STORE,SYNCC engine;
    class MCAT newwork;
    class DTUI,DTQT,DTPY desktop;
    class ADUI,ADJNI android;
    class SS infra;
```

Both bridges hit the **same entrypoint** — `Backend.command(service, method, bytes)` —
passing serialized protobuf. The protobuf service contracts in `proto/anki/` are the single
IPC boundary for every client.

## 2. Desktop stack (detailed layering)

```mermaid
flowchart TB
    subgraph PRES["Presentation — ts/"]
        SV["SvelteKit 2 · Svelte 5<br/>TypeScript 5 · Vite 6<br/>Sass + Bootstrap 5"]
    end
    subgraph SHELL["Desktop shell — qt/aqt/"]
        QT["PyQt6 6.11 + QtWebEngine<br/>QWebChannel JS↔Py bridge"]
        MS["mediasrv: Flask + Waitress<br/>serves pages @ 127.0.0.1:40000"]
    end
    subgraph PYL["Python library — pylib/anki/"]
        PY["import anki — Collection API"]
        GEN["_backend_generated.py<br/>(auto-gen from proto)"]
    end
    RB["rsbridge — PyO3 cdylib<br/>Backend.command(svc, method, bytes)<br/>(pylib/rsbridge/lib.rs)"]
    CB["Rust core — 'anki' crate (rslib/)<br/>Backend + Collection"]

    SV -->|"HTTP /_anki/* · postProto"| MS
    QT --- MS
    MS --> PY --> GEN --> RB --> CB

    classDef n fill:#0969da,stroke:#033d8b,color:#fff;
    class SV,QT,MS,PY,GEN,RB,CB n;
```

| Layer            | Tech                                                           | Location                       |
| ---------------- | -------------------------------------------------------------- | ------------------------------ |
| Web UI           | SvelteKit 2, Svelte 5, TypeScript 5, Vite 6, Sass, Bootstrap 5 | `ts/routes/`, `ts/lib/sass/`   |
| Native shell     | PyQt6 6.11 + QtWebEngine, QWebChannel                          | `qt/aqt/webview.py`, `main.py` |
| Local web server | Flask + Waitress (`mediasrv`)                                  | `qt/aqt/mediasrv.py`           |
| Python library   | CPython 3.13, `import anki`                                    | `pylib/anki/`                  |
| Language bridge  | **PyO3 `cdylib`**                                              | `pylib/rsbridge/lib.rs`        |
| Engine           | Rust `anki` crate                                              | `rslib/`                       |

## 3. Android stack (AnkiDroid fork)

```mermaid
flowchart TB
    subgraph AUI["AnkiDroid (Kotlin) — forked, separate repo"]
        K["Kotlin UI · reviewer · deck list"]
        DASH["NEW: readiness dashboard +<br/>practice-test screens (Kotlin)"]
    end
    RS["rsdroid — JNI bridge<br/>builds 'anki' crate via cargo-ndk<br/>passes protobuf bytes"]
    CB["Shared Rust core — 'anki' crate (rslib/)<br/>Backend + Collection + scheduler/FSRS<br/>+ NEW MCAT services"]

    K --> RS
    DASH --> RS
    RS -->|"JNI · protobuf bytes"| CB

    classDef a fill:#8957e5,stroke:#3b1f6b,color:#fff;
    classDef new fill:#d29922,stroke:#7a5b00,color:#fff;
    classDef core fill:#1f6feb,stroke:#0d2b66,color:#fff;
    class K,RS a;
    class DASH new;
    class CB core;
```

| Layer  | Tech                                            | Source                                              |
| ------ | ----------------------------------------------- | --------------------------------------------------- |
| UI     | Kotlin (AnkiDroid screens + new MCAT screens)   | AnkiDroid fork                                      |
| Bridge | `rsdroid` JNI, `cargo-ndk` builds `anki` `.so`  | AnkiDroid fork, depends on this repo's `anki` crate |
| Engine | **the same `anki` crate** (pinned to your fork) | `rslib/` (this repo)                                |

> The engine change you make in `rslib` reaches Android by pinning AnkiDroid's `rsdroid`
> dependency to your fork's `anki` crate — no scheduler reimplementation in Kotlin.

## 4. Sync & data topology

```mermaid
flowchart LR
    subgraph D["Desktop"]
        DC["Collection (SQLite)<br/>pending = USN -1"]
    end
    subgraph P["Phone (AnkiDroid)"]
        PC["Collection (SQLite)<br/>offline review queue"]
    end
    SS["anki-sync-server<br/>Axum + Tokio · Docker<br/>(rslib/sync/, docs/syncserver/)"]
    MERGE["Conflict rule<br/>USN + graves tombstones<br/>last-write-wins by mtime<br/>revlog append-only<br/>(chunks.rs)"]

    DC <-->|"sync client · Zstd-JSON/HTTP<br/>(rslib/src/sync)"| SS
    PC <-->|"same Rust sync code"| SS
    SS -.-> MERGE

    classDef n fill:#0969da,stroke:#033d8b,color:#fff;
    classDef infra fill:#6e7781,stroke:#30363d,color:#fff;
    class DC,PC n;
    class SS,MERGE infra;
```

## 5. Where the Speedrun work lands

| Spec requirement                                                                  | Layer it lives in                            | Path                                                                    |
| --------------------------------------------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------- |
| Real Rust change (§7a: points-at-stake queue / topic-aware sched / mastery query) | **Engine** — new proto msg + scheduler/query | `proto/anki/`, `rslib/src/scheduler/`, `rslib/src/services.rs`          |
| 3 Rust unit tests + 1 Python-calling test                                         | Engine + pylib                               | `rslib/src/...`, `pylib/tests/`                                         |
| Memory model (FSRS) + answer-time comfort                                         | Engine                                       | `rslib/src/scheduler/fsrs/`, `rslib/src/revlog/mod.rs` (`taken_millis`) |
| Performance + readiness services                                                  | Engine, exposed like `StatsService`          | `proto/anki/`, `rslib/src/stats/service.rs` pattern                     |
| Readiness dashboard (3 scores + ranges)                                           | Desktop UI + Android UI                      | `ts/routes/` (new page) + AnkiDroid Kotlin screen                       |
| Two-way sync + conflict rule                                                      | Engine (sync)                                | `rslib/src/sync/collection/chunks.rs`                                   |
| Desktop installer                                                                 | Packaging                                    | `qt/installer/` (Briefcase: mac/windows/linux)                          |
| Phone build (signed APK)                                                          | AnkiDroid fork build                         | AnkiDroid Gradle                                                        |
| AI off still scores                                                               | All clients                                  | feature-flag the post-MVP AI service                                    |

## 6. Build & packaging toolchain

- **Orchestration:** `just` recipes → Rust-generated **Ninja** build (`build/configure`, `build/ninja_gen`, `build/runner`).
- **Toolchains:** Rust 1.92 (`rust-toolchain.toml`), CPython 3.13, Yarn 4.11 / Node, `uv` for Python deps, `protoc` (auto-fetched).
- **Codegen:** `proto/anki/*.proto` → Rust services (`rslib/src/services.rs`), Python (`_backend_generated.py`), TS (`@generated/backend`) via `rslib/proto/build.rs`.
- **Desktop installer:** Briefcase (`qt/installer/`, per-OS templates).
- **Android:** AnkiDroid Gradle + `cargo-ndk` (in the AnkiDroid fork).

## 7. Notes & risks

- **Mobile is the highest-risk track — phase it to the deadlines.** Wednesday: the phone
  builds and runs a **review session on the shared deck** (no two-way sync required yet).
  Friday: **two-way sync** (phone ↔ desktop, none lost or double-counted), offline-review-
  then-sync, and the three scores + give-up rule on the phone. Building AnkiDroid against a
  custom `anki` crate (`cargo-ndk`) plus the new Kotlin dashboard / practice-test screens is
  substantial — start it day one, don't leave it to Thursday. (Mirrors the MVP PRD's mobile
  phasing note.)
- **Two repos, one engine:** the AnkiDroid fork is a second repo that depends on this repo's
  `anki` crate (pin `rsdroid`'s dependency to your fork). The _engine change_ still satisfies
  "modify the core, not a plugin."
- **No in-repo mobile FFI** today — relying on AnkiDroid's proven `rsdroid` JNI avoids building one.
- **FSRS is the external `fsrs` crate v5.2.0** — extend around it (comfort signal, readiness), don't fork it lightly.
- **iOS deferred** — would need a new in-repo C-FFI/uniffi crate + Swift app; out of scope for the chosen Android path.
