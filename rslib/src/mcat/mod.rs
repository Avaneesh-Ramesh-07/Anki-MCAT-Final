// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! MCAT readiness features built into the engine, as three separately-shown
//! scores over the `aamc::<section>::<topic>` note tags:
//! - `mastery` — the memory model (comfort-augmented FSRS DSR recall).
//! - `performance` — topical practice-test scores with recency decay.
//! - `readiness` — the sanctioned composite of memory + topical + per-topic
//!   full-length accuracy, with a compound give-up rule.

mod mastery;
mod performance;
mod readiness;
mod service;
