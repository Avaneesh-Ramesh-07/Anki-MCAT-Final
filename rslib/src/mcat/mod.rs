// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! MCAT readiness features built into the engine. The Mastery Query is the
//! memory model: per AAMC topic (the `aamc::...` tag) it aggregates the
//! comfort-augmented DSR score with a statistical range, abstaining when there
//! isn't enough review evidence yet (the give-up rule).

mod mastery;
mod performance;
mod service;
