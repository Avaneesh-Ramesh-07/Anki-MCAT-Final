# Anki Codebase Notes

> Living summary of the `anki-mcat` repository, built by systematically exploring each
> subsystem. This is a fork of upstream Anki (ankitects/anki) intended to become an
> **MCAT study app** (desktop + Android), per `anki_prd_mvp.md`, `anki_prd_post_mvp.md`,
> and `anki_tech_stack.md`. License: AGPL-3.0-or-later (parts BSD-3).

---

## 0. High-level architecture

Anki is a spaced-repetition flashcard engine with a **multi-layer, one-engine / many-clients**
design. A single Rust core (`anki` crate in `rslib/`) holds all real logic; thin clients in
other languages call into it by passing **serialized protobuf bytes** through a single
entrypoint: `Backend.command(service, method, bytes)`.

```
Web UI (Svelte/TS, ts/)                Android UI (Kotlin, AnkiDroid fork — separate repo)
      │ HTTP /_anki/*  · postProto             │ JNI
      ▼                                         ▼
PyQt6 shell + mediasrv (qt/aqt/)          rsdroid JNI bridge
      │                                         │
      ▼                                         │
Python lib `anki` (pylib/anki/)                 │
      │  _backend_generated.py (codegen)        │
      ▼                                         ▼
rsbridge (PyO3 cdylib, pylib/rsbridge) ──► Rust core `anki` crate (rslib/)
                                              Backend dispatch → scheduler/FSRS,
                                              storage (SQLite), sync client, search, …
                                                    │
                                                    ▼  Zstd-JSON/HTTP · USN merge
                                              anki-sync-server (Axum, rslib/sync/)
```

**The protobuf service contracts in `proto/anki/*.proto` are the single IPC boundary** for
every client and the source of generated APIs for Rust, Python, and TypeScript.

### Layer map (tracked-file counts)
| Dir | Files | Role |
|---|---|---|
| `ts/` | 522 | Web frontend — SvelteKit 2 / Svelte 5 / TS 5 / Vite 6 / Sass + Bootstrap 5 |
| `rslib/` | 481 | Core Rust engine (`anki` crate) — scheduler, storage, sync, search, import/export, media |
| `qt/` | 293 | PyQt6 desktop GUI (`aqt`), embeds web views, mediasrv, installer |
| `docs-site/` | 280 | Documentation website |
| `pylib/` | 98 | Python library (`import anki`) wrapping Rust via `rsbridge` (PyO3 cdylib) |
| `ftl/` | 58 | Fluent translation files (ftl/core, ftl/qt) |
| `build/` | 46 | Rust-based build system (configure → Ninja generator → runner) |
| `tools/` | 36 | Dev/build helper scripts |
| `docs/` | 30 | Developer docs (contributing, development, syncserver, …) |
| `proto/` | 28 | Protobuf definitions — the IPC contract & codegen source |

### Build & tooling (from justfile + CLAUDE.md)
- **Entry point:** `just` recipes wrap a Rust-generated **Ninja** build. Never call
  `./ninja`/`./run`/`tools/*` directly — use `just`.
- Key recipes: `just run` (build pylib+qt, launch dev), `just run-optimized`, `just check`
  (format + full build + checks; run before completion), `just build` (pylib qt).
- Tests: `just test-rust|test-py|test-ts|test-e2e` (Playwright e2e in `ts/tests/e2e/`).
  Lint/format: `just lint`, `just fmt`, `just fix-fmt`, `just fix-lint`, `just minilints`.
- Quick iteration: Rust `cargo check`; Python/TS `just lint`; web live reload `just web-watch`.
- Toolchains: Rust 1.92 (`rust-toolchain.toml`), CPython 3.13, Yarn 4.11 / Node, `uv` (Python
  deps), `protoc` (auto-fetched). Windows shell for just recipes is `pwsh`.
- Codegen: `proto/anki/*.proto` → Rust `services.rs`, Python `_backend_generated.py`,
  TS `@generated/backend`.
- Web views served at `http://localhost:40000/_anki/pages/` in dev.

### MCAT-fork intent (from anki_tech_stack.md / PRDs)
- One Rust engine, two clients (this desktop repo + an AnkiDroid Kotlin fork pinned to this
  repo's `anki` crate via `rsdroid`/`cargo-ndk`). iOS deferred.
- New work targets: "MCAT services" (readiness / practice-test / comfort) added to the Rust
  backend like `StatsService`; readiness dashboard in `ts/routes/` + Android Kotlin; scheduler
  tweaks (points-at-stake queue / topic-aware sched / mastery query); answer-time "comfort"
  signal off `revlog` `taken_millis`; FSRS is the external `fsrs` crate (v5.2.0) — extend, don't fork.
- New engine work lands in `proto/anki/`, `rslib/src/scheduler/`, `rslib/src/services.rs`,
  `rslib/src/stats/`, with tests in `rslib/src/...` + `pylib/tests/`.

---
<!-- Subsystem deep-dives appended below as exploration proceeds. -->

## 1. `proto/` — the IPC contract

All protobuf3 definitions live in `proto/anki/*.proto` (~24 files). They are the single IPC
boundary between the Rust core and every client. Codegen produces: Rust modules
(`rslib/proto/src/lib.rs` includes them), Python (`out/pylib/anki/*_pb2.py` +
`out/pylib/anki/_backend_generated.py`), and TS (`@generated/backend`).

**Dispatch model:** clients call `Backend.command(service_id, method_id, bytes)`. Service IDs
are fixed per service; method IDs are 0-indexed in declaration order within a service. The
generated Python stub shows the pattern, e.g. `answer_card` → `_run_command(scheduler_svc,
answer_card_idx, msg.SerializeToString())`. Rust routes by service/method id into per-service
handlers under `rslib/src/backend/` and the service impls. Most mutations return `OpChanges`
(bit-flags of what changed: card/note/deck/tag/notetype/config/study_queues/browser_table…)
which tells the UI what to refresh and drives undo.

**Service inventory** (file → service → purpose → notable methods):
| File | Service | Purpose | Notable methods |
|---|---|---|---|
| `sync.proto` | (Backend)SyncService | media + collection sync | `sync_media`, `sync_login`, `sync_status`, `sync_collection`, `full_upload_or_download`, `abort_sync` |
| `collection.proto` | (Backend)CollectionService | collection lifecycle/txn | `open_collection`, `close_collection`, `create_backup`, `check_database`, `undo`, `redo` |
| `cards.proto` | CardsService | card CRUD | `get_card`, `update_cards`, `remove_cards`, `set_deck`, `set_flag` |
| `notes.proto` | NotesService | note CRUD/fields | `add_note(s)`, `get_note`, `update_notes`, `remove_notes`, `cloze_numbers_in_note` |
| `decks.proto` | DecksService | deck CRUD/tree | `new_deck`, `add_deck`, `update_deck`, `deck_tree`, `set_current_deck` |
| `notetypes.proto` | NotetypesService | notetypes/templates | `add_notetype`, `update_notetype`, `change_notetype` |
| `deck_config.proto` | DeckConfigService | scheduling config | `get_deck_config`, `update_deck_configs`, `get_deck_configs_for_update` |
| `scheduler.proto` | SchedulerService | scheduling/answering | `get_queued_cards`, `answer_card`, `sched_timing_today`, `bury_or_suspend_cards`, `get_scheduling_states`, `custom_study` |
| `stats.proto` | StatsService | stats/graphs | `card_stats`, `get_review_logs`, `graphs`, `get_graph_preferences` |
| `search.proto` | SearchService | search/browser | `search_cards`, `search_notes`, `find_and_replace`, `browser_row_for_id` |
| `tags.proto` | TagsService | tags | `all_tags`, `add/remove_note_tags`, `rename_tags`, `complete_tag` |
| `import_export.proto` | ImportExportService | package/CSV import/export | `import_anki_package`, `export_anki_package`, `import_csv`, `export_note_csv` |
| `card_rendering.proto` | CardRenderingService | template render/media | `render_existing_card`, `render_uncommitted_card`, `extract_av_tags`, `extract_latex` |
| `config.proto` | ConfigService | prefs/global config | `get_preferences`, `set_preferences`, `get/set_config_*` |
| `media.proto` | MediaService | media files | `check_media`, `add_media_file`, `trash_media_files` |
| others | I18nService, LinksService, ImageOcclusionService, AnkiwebService, AnkihubService, GithubService | localization, help links, image-occlusion, platform integrations | — |

Note the recurring pairing: a public `XyzService` (on-the-fly ops) plus a backend-only
`BackendXyzService` (offline ops not exposed to all clients).

**Key message types:** `Card` (cards.proto: id, note_id, deck_id, template_idx, type, queue,
due, interval, ease_factor, reps, lapses, FSRS memory state), `Note` (guid, notetype_id, tags,
fields, usn), `Deck`/`DeckConfig` (decks/deck_config.proto: learn/relearn steps, new & review
per-day limits, FSRS params `fsrs_params_4/5/6`, desired_retention, leech action), `Notetype`,
`SchedulingState` (oneof Normal/Filtered with New/Learning/Review/Relearning substates +
FSRS stability/difficulty), `FsrsMemoryState` (stability, difficulty), `RevlogEntry`/`ReviewLogs`
(stats.proto: time, button_chosen, interval, ease, taken_secs, review_kind), `OpChanges`/`Progress`
(collection.proto), and primitive wrappers in `generic.proto` (Empty, Int64, String, Json, Bool, StringList).
Errors flow back as `BackendError` (kind + message + help_page) defined in `backend.proto`.

**MCAT-fork relevance:** a new MCAT service (readiness / practice-test / comfort) should be
modeled on the **stats service** — add `proto/anki/mcat.proto` with a `McatService` (and empty
`BackendMcatService`), wire it into `rslib/proto/src/lib.rs` codegen, implement under
`rslib/src/` like `stats/`, and reuse existing messages (`RevlogEntry`, `FsrsMemoryState`,
`SchedulingState`, `GraphsRequest`-style filter inputs). Comfort signal comes from revlog
`taken_secs`/`taken_millis`. Adding fields to existing protos is safe (proto3 zero-defaults);
renumbering/removing breaks clients. (Exact service-ID numbering must be taken from the actual
generated code, not assumed.)

## 2. Build system (`build/`, `tools/`, `just`)

**Flow:** `just <recipe>` → **build/configure** (Rust binary) reads the source tree and emits a
`build.ninja` manifest → **Ninja** runs the task graph in parallel → **build/runner** (Rust binary)
is a cross-platform wrapper executing individual actions (pyenv setup, yarn/node, cargo, protoc,
rsync, archiving, wheels). configure declares inputs (globs, proto descriptors, toolchain
downloads), dependencies, and Ninja rules; runner abstracts Windows/Unix differences.

**`build/configure/src/` modules:** `main.rs` (orchestrates protoc, venv, rust/pylib/web/aqt/
installer/audio builds + checks; emits build.ninja), `aqt.rs` (PyQt .ui→_qt6.py via pyside6,
wheels, py checks), `pylib.rs` (proto codegen, hooks_gen.py, rsbridge link, wheel), `rust.rs`
(FTL sync, proto descriptors, rsbridge PyO3, cargo), `web.rs` (node/yarn, Vite+SvelteKit+Sass,
esbuild, protobuf-es, eslint/prettier/dprint, SQL checks), `installer.rs` (Briefcase per-OS),
`platform.rs` (cross-compile target detection), `python.rs` (uv venv), `audio.rs` (mpv+LAME,
Windows), `cog.rs` (hook doc generation).
**`build/ninja_gen/src/`:** `build.rs` (`Build` struct → build.ninja), `action.rs` (`BuildAction`
trait), `cargo.rs`/`node.rs`/`python.rs`/`protobuf.rs` (toolchain actions + pinned versions),
`command.rs`/`copy.rs`/`rsync.rs`/`input.rs`/`hash.rs`/`git.rs`/`render.rs`.
**`build/runner/src/`:** `main.rs` (subcommands Pyenv/Yarn/Rsync/Run/Build/Archive), `build.rs`
(invoke Ninja with PATH/env), `pyenv.rs`, `yarn.rs`, `archive.rs`, `rsync.rs`, `run.rs`.

**`tools/`:** `build`/`build.bat` + arch variants, `ninja.bat`, `clean`, `web-watch`/`rebuild-web`
(hot reload, mac/linux), `run.py`/`runopt`, `build-installer`, `coverage/coverage-{rust,py,ts}`,
`minilints/` (custom Rust linter), `install-n2`, `profile`, `unused-rust-deps`,
`qwebengine-csp-smoke`, `dmypy`, `reload_webviews.py`.

**Rust workspace members:** `build/{configure,ninja_gen,runner}`, `ftl`, `pylib/rsbridge`,
`rslib` + subcrates `rslib/{i18n,io,linkchecker,process,proto,sync}`, `tools/minilints`.
**Notable Rust deps:** fsrs 5.2.0, rusqlite 0.36 (bundled SQLite), axum 0.8.4, tokio 1.45,
prost/prost-build/prost-types 0.13, pyo3 0.29 (abi3-py39), reqwest 0.12.20, snafu 0.8.6,
serde 1.0 / serde_json 1.0, chrono 0.4, fluent 0.16–0.17, tower-http 0.6, tracing 0.1,
zip/zstd/flate2/tar, blake3/sha2/sha1, walkdir/globset/camino.
**JS deps:** @sveltejs/kit 2.60, svelte 5.55, vite 6, typescript 5.0, vitest 3,
@playwright/test 1.60, bootstrap 5.3, jquery 3.5, d3 7, fabric 5.3, esbuild 0.28,
@bufbuild/protobuf 1.2 + protoc-gen-es, mathjax 3.1, yarn 4.11.
**Python deps:** dev = mypy, ruff, pytest(-mock), briefcase, cogapp, complexipy, coverage,
hatchling, types-*; docs = sphinx + myst-parser + sphinx-book-theme + autoapi + mermaid.
**Toolchains:** Rust 1.92 (min 1.80), Node 22.17, Yarn 4.11 (corepack), protoc 31.1, uv 0.11.8,
Python ≥3.12 (wheels target abi3-py39), Playwright ^1.60.

## 3. `rslib/` — core Rust engine (the `anki` crate)

`rslib/src/lib.rs` is the crate root; `prelude.rs` re-exports common types; `services.rs` is
**generated** (via `rslib/build.rs` + `rslib/rust_interface.rs` reading the proto DescriptorPool)
and contains the per-service traits + the `run_service_method(service, method, bytes)` dispatch.
Subcrates: `rslib/{i18n,io,linkchecker,process,proto,sync}`.

### 3.1 Data model — notes / cards / notetypes
- **`Note`** (`rslib/src/notes/mod.rs`): `id: NoteId` (ms-timestamp i64), `guid` (base91), `notetype_id`,
  `mtime: TimestampSecs`, `usn: Usn`, `tags: Vec<String>`, `fields: Vec<String>` (field 0 = sort field),
  cached `sort_field` + `checksum` (u32, for dupe detection). `prepare_for_update()` normalizes NFC,
  recomputes checksum/sort field, validates field count.
- **`Card`** (`rslib/src/card/mod.rs`): `id: CardId`, `note_id`, `deck_id` + `original_deck_id` (filtered),
  `template_idx: u16`, `mtime`, `usn`, `ctype: CardType{New,Learn,Review,Relearn}`,
  `queue: CardQueue{New=0,Learn=1,Review=2,DayLearn=3,PreviewRepeat=4,Suspended=-1,SchedBuried=-2,UserBuried=-3}`,
  `due: i32`, `interval: u32`, `ease_factor: u16` (÷1000), `reps`, `lapses`, `remaining_steps`,
  `original_due`/`original_position` (filtered), `flags: u8` (low 3 bits = flag color), `custom_data: String`
  (JSON for add-on/reviewer persistence), and FSRS fields: `memory_state: Option<FsrsMemoryState{stability,difficulty}>`,
  `desired_retention: Option<f32>`, `decay: Option<f32>`, `last_review_time`.
- **`Notetype`** (`rslib/src/notetype/mod.rs`): `fields: Vec<NoteField>`, `templates: Vec<CardTemplate>`
  (q/a formats incl. browser variants), `config: NotetypeConfig{kind Normal|Cloze, css, latex_pre/post,
  sort_field_idx, reqs}`. Card generation via `CardGenContext` (`notetype/cardgen.rs`): cards are created
  per template whose field requirements (Any/All/None) are satisfied; cloze types generate one card per
  unique cloze number. Cached lookups in `Collection.state.notetype_cache`.

### 3.2 Scheduler (`rslib/src/scheduler/`) — most relevant to the MCAT fork
Module layout: **answering/** (rating→state transition: `mod.rs`, `current.rs`, `learning.rs`,
`review.rs`, `relearning.rs`, `preview.rs`, `revlog.rs`), **queue/** (`builder/` gathers + sorts +
intersperses; `main.rs` pops/pushes), **states/** (`normal.rs` = New/Learning/Review/Relearning,
`filtered.rs`, `preview_filter.rs`, `rescheduling_filter.rs`; load-balancer, fuzz, steps),
**fsrs/** (`memory_state.rs`, `params.rs`, `rescheduler.rs`, `retention.rs`, `simulator.rs`),
**filtered/** (`mod.rs`, `custom_study.rs`), plus `timing.rs`, `bury_and_suspend.rs`, `new.rs`,
`reviews.rs`, `congrats.rs`, `timespan.rs`, `service/` (RPC impl).

- **Answer pipeline:** `Collection::answer_card()` → `CardStateUpdater` (answering/mod.rs) → applies the
  chosen next state, writes the card, and appends a revlog entry. The `CardAnswer` from the frontend
  carries `milliseconds_taken` (capped by deck config `cap_answer_time_to_secs`).
- **Queue building:** `QueueBuilder` gathers in order: intraday learning → day-learning → review →
  new (by `NewCardGatherPriority`: deck order / random / position), then sorts and intersperses per
  `new_review_mix`/`day_learn_mix`, decrementing per-deck `RemainingLimits` (`decks/limits.rs`).
- **States:** `CardState::Normal(New|Learning|Review|Relearning)` or `Filtered(Preview|Rescheduling)`.
  `StateContext` carries steps, multipliers, max interval, leech threshold, load-balancer ctx, and the
  FSRS `NextStates`. Next-state for Review uses FSRS-provided intervals/memory when enabled, else SM-2
  multipliers + fuzz.
- **FSRS:** external `fsrs` crate (`FSRS::new(params)`, `compute_parameters()`, `FSRSItem`/`FSRSReview`).
  Per-card memory state {stability, difficulty} lives on the card; retrievability computed from
  decay + days elapsed. `update_memory_state()` (`fsrs/memory_state.rs`) rebuilds memory from revlogs
  matching a search; `compute_params()` (`fsrs/params.rs`) trains parameters (len 19/20/21 for FSRS 4/5/6;
  decay at index 20 if present). Desired retention is per-deck overridable (`Deck::effective_desired_retention`,
  range 0.7–0.99); params stored in deck config (`fsrs_params_4/5/6`).
- **Timing:** `sched_timing_today()` (`timing.rs`) → `SchedTimingToday{now, days_elapsed, next_day_at}`,
  using rollover hour (default 4am, config key `Rollover`) + creation/current UTC offsets (DST-aware).
  On first call after rollover, scheduler-buried cards are auto-unburied.

### 3.3 revlog (`rslib/src/revlog/mod.rs`)
`RevlogEntry`: `id: RevlogId` (ms timestamp), `cid`, `usn`, `button_chosen` (ease 1–4; 0 = manual),
`interval`/`last_interval` (positive=days, negative=seconds for intraday), `ease_factor: u32`
(normally ×10 of %, e.g. 2500=250%; with FSRS encodes normalized difficulty 100–1100),
**`taken_millis`** (answer time in ms — the basis for the MCAT "comfort"/speed signal), and
`review_kind: {Learning=0, Review=1, Relearning=2, Filtered=3, Manual=4, Rescheduled=5}`. Helpers:
`interval_secs()`, `is_reset()`, `is_cramming()`, `has_rating_and_affects_scheduling()`.

### 3.4 decks & deck config
- **`Deck`** (`decks/mod.rs`): id, `name: NativeDeckName`, mtime, usn, `common` (description, collapse),
  `kind: Normal{config_id, desired_retention?} | Filtered`. `decks/limits.rs` builds `RemainingLimits`
  per deck (review+new remaining after today's usage; `new_cards_ignore_review_limit` flag).
- **`DeckConfig`** (`deckconfig/mod.rs`, wraps proto `DeckConfigInner`): learn/relearn steps,
  graduating intervals, ease & interval multipliers, `new_per_day`/`reviews_per_day` (+ optional per-day
  `DayLimit` overrides), `fsrs_params_4/5/6` + `fsrs_params()` (highest available), `desired_retention`,
  `historical_retention`, `leech_threshold` (8) + `leech_action` (TagOnly|Suspend), bury flags
  (new/reviews/interday-learning). Validated on read.

### 3.5 config (`rslib/src/config/`)
Global `ConfigKey` enum (`config/mod.rs`): timing (`LocalOffset`, `CreationOffset`, `Rollover`,
`FirstDayOfWeek`), scheduler (`SchedulerVersion` V1/V2; V3 = V2 + `Sched2021` bool), queuing
(`NewReviewMix`, `LearnAheadSecs`, `NextNewCardPosition`, `AnswerTimeLimitSecs`), `LastUnburiedDay`,
session (`CurrentDeckId`, `CurrentNotetypeId`). Bool flags in `config/bool.rs` (Fsrs, Sched2021, …).

### 3.6 search (`rslib/src/search/`)
`parser.rs` (nom recursive-descent) parses a query string into a `Node` AST (And/Or/Not/Group/Search);
`SearchNode` has 30+ variants (UnqualifiedText, SingleField{field,text,mode}, Deck, Tag, Rated{days,ease},
State, Property, Duplicates, Regex, AddedInDays, …). `sqlwriter.rs` (`SqlWriter::build_query`) turns the
AST into parameterized SQL choosing the right table join; text normalized to NFC, HTML stripped before
match. `builder.rs` composes/flattens queries. Entry points `search_cards`/`search_notes`
(`search/service/mod.rs`) compile to SQL each call. Sorting via `SortMode` (NoOrder/Builtin{Column}/Custom),
Columns defined in `browser_table.rs`.

### 3.7 stats (`rslib/src/stats/`) — template for a new MCAT service
`stats/service.rs` implements the generated `StatsService` trait for `Collection`: `card_stats`,
`get_review_logs`, `graphs`, `get/set_graph_preferences`. `card.rs`: `card_stats(cid)` loads
card→note→notetype→deck + revlog, computes average/total secs, retrievability, returns proto.
`graphs/mod.rs`: `graph_data_for_search(search, days)` searches cards into a temp table, loads revlog +
cards into a `GraphsContext`, and computes eases / added / review counts+times / true-retention /
future-due / intervals / stability / hours / buttons / card-counts / retrievability. **A new MCAT
readiness/mastery service mirrors this exactly:** define proto service → implement the generated trait for
`Collection` under `rslib/src/mcat/` → query revlog/cards (optionally search→temp-table for batches) →
compute derived metrics → return proto. Register by adding `pub mod mcat;` to `lib.rs`; the build script
generates the trait + dispatcher.

### 3.8 rendering & text
`template.rs` (mustache-like `{{field}}`/`{{#cond}}`/`{{^inv}}`, nom parser, field requirements),
`template_filters.rs`, `cloze.rs` (`{{c1::text::hint}}` regex/tokenizer + per-number card gen),
`latex.rs` (MathJax `\[ \] \( \)`, preamble/postamble), `typeanswer.rs` (type-in answer compare),
`text.rs` (NFC normalize, `strip_html_preserving_media_filenames`, glob/regex helpers,
combining-mark stripping), `card_rendering/` (RenderCardService: render question/answer, extract AV/TTS
tags via `CardNodes::parse`, extract LaTeX).

### 3.9 import/export & media
`import_export/` (ImportExportService): apkg (ZIP of collection.anki2 + media), colpkg (full backup),
CSV (configurable delimiter/field-mapping/HTML), JSON. Key dirs: `package/apkg/`, `package/colpkg/`,
`text/csv/`, `text/json.rs`. `media/` (MediaService): `check_media` (orphans/missing/in-templates),
`add_media_file` (dedupe), `trash_media_files`/`empty_trash`/`restore_trash`, static-media extraction
from notetype CSS/templates (`_underscored` refs).

### 3.10 storage (`rslib/src/storage/`)
SQLite via rusqlite. `storage/sqlite.rs` `SqliteStorage` opens the DB (WAL, page size, exclusive lock,
prepared-statement cache) and registers custom SQL functions (`field_at_index`, `process_text`,
`fnvhash`, `regexp`, `regexp_fields`, `regexp_tags`). Schema versioning in `storage/upgrades/mod.rs`
(SCHEMA_MIN=11, MAX=18; per-version `schemaNN_upgrade.sql` / downgrade SQL via `include_str!`). Per-entity
modules: `storage/{card,note,revlog,deck,deckconfig,notetype,tag,config,graves}/`. `storage/graves/`
tracks tombstones `(oid, type, usn)`; `storage/sync.rs` handles USN (`usn()`, `increment_usn()`,
`objects_pending_sync`, `pending_object_clause` → `"usn = ?"` for clients at usn=-1 vs `"usn >= ?"` for server).

### 3.11 collection / transactions / undo / ops / progress
`collection/mod.rs` `Collection` holds `storage`, paths, media folder/db, `tr: I18n`, `server: bool`,
`state` (caches, undo manager, progress). Built via `CollectionBuilder`. `collection/transact.rs`
`transact(op, fn)` wraps a DB transaction, brackets it with `begin/end_undoable_operation`, bumps mtime
on change, returns `OpOutput<R>{output, OpChanges{op, StateChanges}}`. `ops.rs`: `Op` enum (operation
kinds + `describe(tr)` labels, `Op::Custom`), `StateChanges` bitflags (card/note/deck/tag/notetype/
config/deck_config/mtime), `OpOutput`. `undo/mod.rs` `UndoManager` keeps a capped `VecDeque<UndoableOp>`
(~30 steps); `undo/changes.rs` `UndoableChange` enum is polymorphic over entity types; Sync/SkipUndo ops
bypass undo. `collection/timestamps.rs` tracks `collection_change`/`schema_change`/`last_sync`
(TimestampMillis); schema bump forces a full sync. `progress.rs` `ThrottlingProgressHandler` updates a
shared `Arc<Mutex<ProgressState>>` (~0.1s throttle) and surfaces `want_abort` as `Interrupted`.

### 3.12 sync client (`rslib/src/sync/`) & server (`rslib/sync/`)
**Client phases** (`sync/collection/normal.rs` `NormalSyncer`): (1) meta exchange (`meta.rs` — compare
modified/schema/usn; schema mismatch ⇒ full sync), (2) start + deletions (`start.rs` — exchange & apply
`Graves`), (3) unchunked changes (`changes.rs` — notetypes/decks/deckconfig/tags/config in one batch),
(4) chunked cards/notes/revlog (`chunks.rs`, CHUNK_SIZE 250), (5) sanity check (`sanity.rs` — counts
match), (6) finalize (`finish.rs` — bump USN, set last-sync).
**Conflict rule (last-write-wins by mtime):** `add_or_update_{card,note}_if_newer` in `chunks.rs`: if the
local object is not pending-sync and local mtime ≥ remote mtime, keep local; otherwise remote wins. Local
pending changes (usn=-1) always lose to remote. **Graves** prevent resurrection of deleted objects.
HTTP via `sync/http_client/` (reqwest) with zstd compression; media sync is a separate protocol
(`sync/media/`). **Server** (`rslib/sync/` crate → bin `anki-sync-server`; impl in
`sync/http_server/`): Axum app, per-user collections under `$SYNC_BASE`, users from env
(`SYNC_USER1="user:pass"`), hkey via PBKDF2; routes `/sync/{method}` and `/msync/{method}`. Self-host via
Docker (see `docs/syncserver/`).

### 3.13 Android & AnkiHub glue
`rslib/src/ankidroid/` (`service.rs`, `db.rs`): `AnkidroidService` lets the Android client run raw SQL as
protobuf (`run_db_command`, paginated `get_next_result_page`, `insert_for_id`, result-cache mgmt) via
`backend/dbproxy.rs`. `rslib/src/ankihub/` (`mod.rs`, `login.rs`, `http_client/`): HTTP client + login for
the AnkiHub cloud service.

### 3.14 backend dispatch & errors
`backend/mod.rs` `Backend` wraps a `Mutex<Collection>` and implements
`run_service_method(service, method, input) → Result<Vec<u8>, Vec<u8>>`, matching the service index then
the per-service `run_*_service_method(method, bytes)`. Backend-only services live in
`backend/{collection,sync,config,adding,card_rendering,import_export,ankidroid,ankihub}.rs`; on-the-fly
services are implemented in each module's `service.rs`. Errors: `error/mod.rs` `AnkiError` + `Result<T>`
(snafu-based; variants InvalidInput, DbError, NetworkError, SyncError, SearchError, FsrsInsufficientData,
NotFound, …) with `into_protobuf()` → `BackendError`; helper traits `OrInvalid`/`OrNotFound`.

### 3.15 MCAT-fork engine hooks (concrete)
- **Points-at-stake / topic-aware queue:** intercept `scheduler/queue/builder/` gathering (new-card
  priority) and `decks/limits.rs` (per-topic limits).
- **Mastery query / readiness service:** new `rslib/src/mcat/` modeled on `stats/` (search→revlog→derived
  metrics → proto); add proto service + `pub mod mcat;`.
- **Comfort/speed signal:** read `RevlogEntry.taken_millis` (set from `CardAnswer.milliseconds_taken`,
  capped by `cap_answer_time_to_secs`) in `scheduler/answering/`.
- **Sync a new MCAT entity:** add SQLite table + schema-version bump + per-entity `storage/` module +
  `UndoableChange` variant + grave type + a `*Entry` serde tuple wired into `chunks.rs`
  (chunked) or `changes.rs` (unchunked) + `SanityCheckCounts` field. Existing USN/graves/mtime conflict
  logic then carries it across desktop↔Android.

## 4. `pylib/` — Python library (`import anki`) + rsbridge

### 4.1 rsbridge (PyO3 cdylib, `pylib/rsbridge/lib.rs`)
A `#[pyclass] Backend` wraps the Rust `anki::Backend`. Core methods: `command(service: u32, method: u32,
input: &PyBytes) -> PyBytes` (calls `backend.run_service_method(...)` — the single dispatch point) and
`db_command(bytes)` (JSON SQL interface). Releases the GIL via `py.detach()` during Rust work; Rust errors
become a PyO3 `BackendError` exception. Module exports: `buildhash()`, `open_backend(init_msg)`,
`initialize_logging(path)`, `syncserver()`. `pylib/rsbridge/build.rs` sets platform linker flags.

### 4.2 anki package layout (key modules)
| Module | Responsibility |
|---|---|
| `_backend.py` | `RustBackend(RustBackendGenerated)` wrapper; `backend_exception_to_pylib()` error translation; Translations |
| `_backend_generated.py` | **generated** at build time; snake_case method per RPC, each calls `_run_command(service, method, bytes)` |
| `collection.py` | `Collection` facade (~1300 lines): exposes `.db/.models/.decks/.tags/.conf/.media/.sched/.tr` |
| `cards.py` / `notes.py` | `Card`/`Note` models, proto↔Python conversion, `load()`/`_to_backend_*()` |
| `decks.py` / `models.py` | `DeckManager` / `ModelManager` (notetypes); CRUD via backend |
| `scheduler/v3.py` | `Scheduler`: `get_queued_cards`, `answer_card(CardAnswer)`, `describe_next_states`; `base.py`/`dummy.py` legacy |
| `sync.py` / `media.py` | thin wrappers over backend sync + media |
| `errors.py` | exception hierarchy (BackendError, NetworkError, SyncError, DBError…) |
| `hooks.py` + `hooks_gen.py` | hook system (legacy dict + generated typed hooks) |
| `dbproxy.py` | `DBProxy` SQL interface; `httpclient.py`, `config.py`, `consts.py`, `tags.py`, `template.py`, `lang.py`, `utils.py`, `importing/`, `exporting.py` |

### 4.3 Call chain & hooks
`Collection.method()` → `self._backend.method(args)` (generated) → `_run_command(service, method, bytes)`
→ `self._backend.command(...)` (PyO3) → Rust `run_service_method`. Response proto bytes decoded; backend
errors → Python exceptions. **Hooks:** legacy `runHook/addHook/runFilter` in `hooks.py`; typed generated
hooks in `hooks_gen.py` (each is a callable class with `.append()` + `__call__`), produced by
`pylib/tools/genhooks.py`. Ops fire hooks like `note_will_be_added`, `card_will_flush`, `card_did_render`.

### 4.4 Tests (`pylib/tests/`)
`shared.py` provides `getEmptyCol()` (cached fresh collection) + assertion helpers. Per-domain
`test_*.py` (e.g. `test_schedv3.py` is large). Pattern: `getEmptyCol()` → mutate via Collection API →
assert → `col.close()`. Run with `just test-py` (pytest). **The MCAT spec's required "Python-calling test"
lands here** as `pylib/tests/test_mcat.py`, exercising the full Python→generated→Rust chain.

### 4.5 MCAT-fork relevance
After adding the Rust/proto MCAT service, the snake_case binding appears automatically in
`_backend_generated.py` (e.g. `col._backend.compute_readiness(req)`). Add a hand-written facade
(`pylib/anki/mcat.py`, exposed as `col.mcat`) + new exception types in `errors.py` if needed + the pylib
test above.

## 5. `qt/` — PyQt6 desktop GUI (`aqt`)

### 5.1 App bootstrap (`qt/aqt/__init__.py`, `qt/aqt/main.py`)
`AnkiApp` (QApplication) + global `mw` singleton; `DialogManager` enforces single-instance modals.
`AnkiQt(QMainWindow)` holds `col: Collection`, `pm: ProfileManager` (`qt/aqt/profiles.py`), `taskman`,
`media_syncer`. State machine: `startup → deckBrowser → overview → review` (+ `resetRequired`,
`profileManager`). `setupUI()` wires media server, toolbars, screens, hooks; `setupProfile()` opens the
collection; fires `main_window_did_init`.

### 5.2 Web integration — the bridge between Svelte UI and Python/Rust
- **mediasrv** (`qt/aqt/mediasrv.py`): Flask + Waitress on `127.0.0.1:~40000` (localhost-only). Serves
  bundled SvelteKit pages under `/_anki/*` (from `qt/aqt/data/web/`), `/_addons/*`, and media. `POST
  /_anki/{endpoint}`: either a custom Python handler (`congrats_info`, `update_deck_configs`, `import_csv`,
  `set_scheduling_states`, …) or a raw backend RPC via `raw_backend_request(endpoint)` →
  `getattr(col._backend, f"{endpoint}_raw")(request.data)` (protobuf in/out). Security: random `_APIKEY`
  header for API-enabled pages; per-context CSP (editor, untrusted media); path-traversal guards.
- **webview** (`qt/aqt/webview.py`): `AnkiWebView`/`AnkiWebPage` over QtWebEngine. `AnkiWebViewKind`
  (MAIN/TOOLBAR/EDITOR/REVIEWER/DECK_OPTIONS/…) drives auth+CSP. **QWebChannel bridge:** JS
  `pycmd(arg, cb)` / `bridgeCommand` → Python `_onBridgeCmd()`. Flow: Qt loads `…/deck-options` → Flask
  rewrites to the SvelteKit bundle → page JS calls `pycmd(...)` for callbacks and POSTs protobuf to
  `/_anki/...` for RPCs.

### 5.3 Operations & hooks (`qt/aqt/operations/`)
`CollectionOp` (mutating, undoable) runs on a background thread (`taskman.py` `TaskManager`), shows
progress (`progress.py`), commits, then fires `operation_did_execute(changes, initiator)` so views refresh
by inspecting `OpChanges`. `QueryOp` is read-only (no undo/auto-refresh, can run off-collection). Submodules:
`collection.py` (undo/redo), `deck.py`, `scheduling.py` (suspend/bury/forget/reschedule), `card.py`,
`note.py`, `tag.py`, `notetype.py`. GUI hooks generated by `qt/tools/genhooks_gui.py` → `_aqt.hooks`,
surfaced via `qt/aqt/gui_hooks.py`.

### 5.4 Major UI modules & add-ons
`reviewer.py`, `editor.py`, `browser/`, `deckbrowser.py`, `overview.py`, `toolbar.py`, `sync.py`,
`addons.py`, `preferences.py`, `deckoptions.py`, `changenotetype.py`, `clayout.py` (card template editor),
`import_export/`. **Add-ons** (`addons.py`): loaded from the `addons21/` profile dir, extend via
`gui_hooks.<name>.append(cb)` and `webExports` served at `/_addons/<id>/...`; per-addon JSON config.

### 5.5 Installer & tests
`qt/installer/` is Briefcase-based with `app/` config + `linux-template/`, `mac-template/`,
`windows-template/` and custom `briefcase_plugins/`. `qt/tests/`: `test_addons.py`, `test_mediasrv.py`,
`test_installer.py`, plus `launch_anki_for_e2e.py` (e2e fixture) and `qwebengine_csp_smoke.py`.

### 5.6 MCAT-fork relevance
Desktop readiness dashboard / practice-test UI = a new SvelteKit page (registered in mediasrv's
sveltekit-page list) + a mediasrv POST handler (or raw backend RPC) calling the new MCAT service +
a menu/state entry in `main.py`/toolbar. Collection-mutating actions wrap in `CollectionOp` for undo +
`OpChanges`-driven refresh. Could also ship as an add-on via hooks if kept out of core.

## 6. `ts/` — SvelteKit/Svelte 5 frontend

### 6.1 Build & serving
SvelteKit 2 / Svelte 5 / TS 5 on **Vite 6**. `ts/svelte.config.js` uses `adapter-static` → output to
`out/sveltekit`; aliases `@tslib` → `ts/lib/tslib`, `@generated` → `out/ts/lib/generated`. `ts/vite.config.ts`
proxies `/_anki/*` to mediasrv (`127.0.0.1:40000`) in dev; target es2020. Legacy (non-SvelteKit) pages are
bundled by `bundle_svelte.mjs` / `bundle_ts.mjs` (esbuild) with `page.html` as template. mediasrv serves the
built bundles at `/_anki/pages/`; `just web-watch` live-rebuilds in dev.

### 6.2 Routes/pages (`ts/routes/`)
`congrats` (post-review screen), `graphs` (stats dashboard — ~14 graph components: CardCounts, Calendar,
Reviews, Intervals, Stability, Ease, Difficulty, Retrievability, …), `deck-options/[deckId]`,
`card-info/[cardId]`, `change-notetype/[...ids]`, `image-occlusion`, `import-anki-package`, `import-csv`,
`import-page`. SvelteKit pages use `+page.svelte` + `+page.ts` (load fn); legacy pages use `index.ts` entries.

### 6.3 Backend communication (the TS→Rust call path)
`ts/lib/generated/post.ts` `postProto(method, input, outputType, opts)` encodes the request message to
bytes (`input.toBinary()`), `POST`s to `/_anki/{method}` (`Content-Type: application/binary`), decodes the
reply (`outputType.fromBinary()`). `@generated/backend` (codegen, `out/ts/lib/generated/backend.ts`) exports
100+ typed RPC wrappers (`getDeckConfigsForUpdate`, `cardStats`, `congratsInfo`, `computeFsrsParams`, …),
each calling `postProto`. Proto message classes live in `out/ts/lib/generated/anki/*_pb`. i18n via
`@generated/ftl` (`ftl-helpers.ts`).

### 6.4 ts/lib subdirs
`components/` (~50 Svelte/Bootstrap wrappers: Select, Switch, SpinBox, ButtonGroup, Popover, Icon,
WithTooltip, WithFloating, VirtualTable…), `sveltelib/` (stores/helpers: event-store, shortcut, theme,
modal-closing, resize-store), `generated/` (codegen output copied at build), `tslib/` (utilities: i18n,
nightmode, shortcuts, dom, platform), `sass/` (Bootstrap theme + dark mode), `domlib/` (rich-text DOM
surround/selection), `tag-editor/` (tag input UI).

### 6.5 Reviewer & editor (rich surfaces)
- **reviewer/** (`index.ts`): Python calls `_showQuestion()`/`_showAnswer()` over the bridge; `_updateQA()`
  injects card HTML, renders MathJax, preloads fonts/images (`preload.ts`/`images.ts`). `answering.ts`
  `mutateNextCardStates(key, transform)` fetches scheduling states (`getSchedulingStatesWithContext`),
  applies per-button JSON transforms, posts back (`setSchedulingStates`). Type-in answers via
  `getTypedAnswer()`; bridge commands `"ans"`, `"updateToolbar"`, `"repaintNeeded"`.
- **editor/** (`NoteEditor.svelte`, `base.ts`): mounts BrowserEditor/NoteCreator/ReviewerEditor; fields are
  `EditingArea`→`EditorField`→ rich-text (`rich-text-input/`, contenteditable `<anki-editable>` + `Surrounder`)
  or plain-text (CodeMirror). 600ms debounced saves via `ChangeTimer` → `bridgeCommand("key:...")`; tags via
  `saveTags:`; image-occlusion mask editor; editor toolbar buttons gated by focused-input/surround state.
- **editable/** (contenteditable custom elements, focus/caret handling, `change-timer.ts`), **domlib/surround**
  (format tree build/apply, `match-type`, `split-text`, selection save/restore), **html-filter/** (paste
  sanitization: Basic/Extended/Internal element + CSS whitelists), **mathjax/** (global MathJax config),
  **icons/** (SVG assets).

### 6.6 Tests
Unit: vitest (`*.test.ts` next to sources, e.g. `html-filter/index.test.ts`,
`lib/domlib/surround/surround.test.ts`, `reviewer/lib.test.ts`). e2e: Playwright in `ts/tests/e2e/`
(`fixtures.ts`, `sanity.test.ts`) driven by `just test-e2e` (launches a temp Anki via
`qt/tests/launch_anki_for_e2e.py` and drives mediasrv pages with Chromium).

### 6.7 MCAT-fork relevance
Readiness dashboard = new `ts/routes/readiness-dashboard/` page whose `+page.ts` load fn calls a generated
`@generated/backend` MCAT RPC (auto-added once the proto service exists), composing `ts/lib/components`.
The **comfort/answer-time signal** originates frontend-side in the reviewer (timing around
`_showQuestion`→answer); a give-up/practice-test control would hook `answering.ts mutateNextCardStates`
or mount an overlay in the reviewer QA container.

## 7. Translations, docs, CI & stragglers

### 7.1 ftl/ — translations + i18n codegen
`ftl/core/` holds cross-platform/backend strings (~35 files: actions, browsing, card-stats,
deck-config, errors, scheduling, sync, undo, …); `ftl/qt/` holds desktop-GUI strings (about, addons,
preferences, profiles, qt-misc, …); `ftl/core-repo/` is a submodule with the localized translations.
Strings use Fluent syntax (`key-id = value`, with `{ $var }` placeholders). **Codegen** (in
`rslib/i18n/build.rs`: `extract.rs`→`gather.rs`→`check.rs`→`write_strings.rs`→`typescript.rs`+`python.rs`)
produces a type-safe `All` API consumed by Rust (`anki_i18n`), TS (`@generated/ftl`), and Python — so a
missing/typo'd key fails the build. Runtime wraps Mozilla's `fluent` crate. **Adding a string:** put it in
`ftl/core/*.ftl` (engine/business logic) or `ftl/qt/*.ftl` (desktop UI), then `just check` regenerates the
typed APIs; localized translations are handled externally (translating.ankiweb.net).

### 7.2 docs/ — developer docs
`index.md`, `development.md` (clone/build/run/test), `build.md` (configure/ninja_gen/runner internals),
`contributing.md` (PR rules: linked issue, type hints, passing tests, CONTRIBUTORS), `architecture.md`,
`protobuf.md`, `language_bridge.md` (rsbridge), `e2e-testing.md`, `testing-coverage.md`, `editing.md` (IDE
setup), `releasing.md`, platform docs (`linux/mac/windows.md`), `ninja.md`, auto-generated API refs
(`api-python.md`, `api-rust.md`, `api-aqt-modules.md`), and **`docs/syncserver/README.md`** (self-hosted
sync server: Dockerfile(+distroless), env-var user config — directly relevant to the fork's two-way sync).

### 7.3 docs-site/
Mintlify-based public documentation website (Node + Mintlify CLI). Sections: `addons/` (add-on dev guide +
hooks reference), `ankimobile/` (iOS manual), `developers/` (mirror of docs/), `faqs/`; i18n via language
subdirs. Purpose: end-user + add-on-developer facing docs (distinct from the in-repo `docs/`).

### 7.4 CI (.github/workflows/)
**ci.yml** (push to main/release/**, PRs): jobs = **minilints** (license/contributor checks via
`cargo run -p minilints -- check`), **format** (`just fmt`), **check-linux** (`just build && just lint &&
just test --coverage && just test-e2e` — full build, clippy/ruff/eslint/svelte/ts, unit + Playwright e2e,
coverage regression), plus **check-macos**/**check-windows** (same + wheels, gated to main/labeled). Caches
cargo + build output; setup via `.github/actions/setup-anki`. **release.yml** (manual, `RELEASE=2` LTO:
per-OS builds, signing, GitHub draft, PyPI). **docs-site.yml** (`mintlify validate` + a11y + hook-doc
pytest). Others: prepare-release, publish-audio-package, auto-close-missing-issue, check-linked-issue.

### 7.5 Stragglers
`python/` = `version.py` (exposes `__version__` from `.version`) + `mkempty.py`. `cargo/` = crate-license
metadata (maintained by minilints) + nightly toolchain for formatting. `.config/nextest.toml` = Rust
nextest config (test store at `out/tests/nextest`). `.cargo/config.toml`, `rust-toolchain.toml` pin the
Rust build; `.cursor/rules/` mirror build/i18n guidance.

### 7.6 MCAT-fork relevance
New MCAT user-facing strings go in `ftl/core/` (engine features like readiness/comfort) or `ftl/qt/`
(desktop dialogs), referenced through the generated typed API in each language. A fork must keep CI green:
`just fmt`, `just lint` (clippy/ruff/eslint/svelte/ts), `just test --coverage`, `just test-e2e`, and
minilints (add yourself to CONTRIBUTORS, keep license headers). Any new `.ftl` key or proto change must
build cleanly under `just check` because the i18n/proto codegen is compile-time-checked across all layers.

## 8. Cross-cutting synthesis

### 8.1 The end-to-end request path (one diagram to rule them all)
A user action in the web UI → Svelte handler → either (a) `pycmd("...")` over QWebChannel for a
Python-side callback, or (b) `postProto(method, msg)` → `POST /_anki/{method}` → **mediasrv**
(`qt/aqt/mediasrv.py`) → `col._backend.{method}_raw(bytes)` → **rsbridge** `Backend.command(service,
method, bytes)` (PyO3, GIL released) → **rslib** `Backend::run_service_method` → service index → method
index → per-service handler on `Collection` → SQLite via `SqliteStorage` → result encoded as proto →
back up the stack. Mutations return `OpChanges`; on the Qt side `CollectionOp` fires
`operation_did_execute(changes)` so views refresh. The **same `Backend.command(service, method, bytes)`**
entrypoint is what the Android client hits over JNI (`rsdroid`).

### 8.2 Adding a feature touches these layers in order
1. `proto/anki/<svc>.proto` — define service + messages (the contract).
2. `rslib/src/<area>/service.rs` (or a new `rslib/src/mcat/`) — implement the generated trait for
   `Collection`; register the module in `lib.rs`. Build script regenerates `services.rs` + dispatch.
3. (auto) Python `_backend_generated.py` + `*_pb2.py`, TS `@generated/backend` + `*_pb` regenerate.
4. `pylib/anki/<area>.py` — optional hand-written facade + `pylib/tests/test_<area>.py`.
5. `qt/aqt/` — menu/state/operation + `qt/aqt/mediasrv.py` handler if a web page needs it.
6. `ts/routes/<page>/` — Svelte page calling the generated RPC; `ts/lib/components` for UI.
7. `ftl/core` or `ftl/qt` — user-facing strings.
8. Keep `just check` (fmt + lint + test + e2e + minilints) green.

### 8.3 Identifiers, sync & data-integrity invariants worth remembering
- IDs are timestamps: `NoteId`/`CardId`/`RevlogId`/`DeckId`/`NotetypeId` are i64 ms/s timestamps.
- `usn = -1` marks locally-pending objects (clients); the server assigns real USNs. Conflict = last-write
  wins by `mtime`, with pending-local always losing; **graves** (tombstones) prevent resurrection of
  deletions. A schema-version bump forces a full sync.
- FSRS is the external `fsrs` crate; per-card `{stability, difficulty}` + `desired_retention`/`decay` live
  on the card; parameters live in deck config. Answer time is `RevlogEntry.taken_millis` (capped by
  `cap_answer_time_to_secs`) — the MCAT comfort signal.
- Anything new that must sync needs: SQLite table + schema bump + `storage/` module + `UndoableChange`
  variant + grave type + a sync `*Entry` in `chunks.rs`/`changes.rs` + a `SanityCheckCounts` field.

### 8.4 Exploration coverage (this pass)
Covered: root configs + justfile; `build/` (+`tools/`); `proto/`; `rslib/` (data model, scheduler/FSRS,
revlog, decks/deckconfig, config, search, stats, rendering/text, import/export, media, storage, collection/
undo/ops/progress, sync client + server, ankidroid/ankihub, backend/errors); `pylib/` (+rsbridge, tests);
`qt/aqt/` (+mediasrv, webview, operations, installer, tests); `ts/` (build, routes, backend comms, lib,
reviewer, editor, editable/domlib/html-filter/tag-editor/mathjax, tests); `ftl/`; `docs/`; `docs-site/`;
`.github/` CI; `python/`, `cargo/`, `.config`. Not deep-dived: `out/` (generated), `node_modules`/`.yarn`
(deps), `rslib/benches` + `bench.sh`, `rslib/linkchecker`, the `ftl/core-repo` translation submodule
contents, and individual add-on/installer template internals — all low-signal for architecture.
