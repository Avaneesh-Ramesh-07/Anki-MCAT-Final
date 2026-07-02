// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! The performance model — topical practice-test scores.
//!
//! When the player grades a practice test it reports, per AAMC topic, how many
//! questions were answered and how many were correct. We store each graded
//! submission (a topical test *or* a full-length exam) as a timestamped
//! per-topic breakdown in a collection config key, so repeated attempts build
//! evidence and each attempt can be weighted by its age.
//!
//! `compute_performance` reports, per topic and per MCAT section, a
//! **recency-weighted** fraction correct with a Wilson range, abstaining below
//! a minimum number of (raw) answered questions (the give-up rule), plus an
//! approximate MCAT scaled score. Only **topical** evidence feeds the
//! performance headline; **full-length** evidence is kept separately and read
//! only by the readiness model (its per-topic accuracy under timing/fatigue).
//!
//! v1 tunables:
//! - `DEFAULT_MIN_QUESTIONS`: abstain below this many (raw) answered questions.
//! - `HALF_LIFE_DAYS`: recency decay half-life — a topic's score decays toward
//!   0 as time since its last test grows (performance predicts answering *new*
//!   questions today, so stale evidence is weaker proof).
//! - The raw->scaled mapping is a documented *linear* approximation: each
//!   section maps [0,1] onto [118,132]; the four sections sum to [472,528].
//!   AAMC's true raw->scaled tables are not public and vary per form, so this
//!   is intentionally an estimate, not a claim of exactness.

use std::collections::BTreeMap;

use serde::Deserialize;
use serde::Serialize;

use crate::prelude::*;

const PERFORMANCE_CONFIG_KEY: &str = "mcatPerformance";
const AAMC_TAG_PREFIX: &str = "aamc::";
const DEFAULT_MIN_QUESTIONS: u32 = 5;
/// Canonical MCAT section order (also the full-length exam order).
const SECTIONS: [&str; 4] = ["chem-phys", "cars", "bio-biochem", "psych-soc"];
const SCALE_MIN: u32 = 118;
const SCALE_MAX: u32 = 132;
/// Recency-decay half-life in days (P3): weight = 0.5 ^ (age_days /
/// HALF_LIFE_DAYS).
const HALF_LIFE_DAYS: f64 = 30.0;
const SECS_PER_DAY: f64 = 86_400.0;
/// Current on-disk schema version for the persisted store.
const STORE_VERSION: u32 = 2;

/// One AAMC topic's tally within a single submission.
#[derive(Default, Clone, Serialize, Deserialize)]
struct TopicTally {
    correct: u32,
    answered: u32,
}

/// One graded submission (a topical test or a completed full-length exam):
/// server-stamped time + the per-AAMC-topic breakdown for that submission.
#[derive(Clone, Serialize, Deserialize)]
struct ExamAttempt {
    /// Unique submission id, used to dedupe re-POSTs idempotently.
    exam_id: String,
    /// Static test id (informational; e.g. "bio-biochem-1" / "full-length").
    #[serde(default)]
    test_id: String,
    /// Unix seconds (server clock) when this submission was recorded.
    t: i64,
    /// `aamc::...` topic tag -> tally for this one submission.
    topics: BTreeMap<String, TopicTally>,
}

/// Accumulated practice-test evidence, persisted as JSON in the collection.
#[derive(Default, Serialize, Deserialize)]
struct PerformanceStore {
    #[serde(default)]
    version: u32,
    /// Standalone topical practice-test submissions (feeds the Performance
    /// headline).
    #[serde(default)]
    topical: Vec<ExamAttempt>,
    /// Completed full-length exams (feeds the readiness model only).
    #[serde(default)]
    full_length: Vec<ExamAttempt>,
    /// v1 blob compatibility: the old `{ "topics": { tag: {correct,answered} }
    /// }`. Folded into `topical` on load, then dropped from output.
    #[serde(default, rename = "topics", skip_serializing_if = "BTreeMap::is_empty")]
    legacy_topics: BTreeMap<String, TopicTally>,
}

/// Recency-weighted accumulator: weighted sums drive the score + effective-n
/// Wilson range, raw sums drive display counts and the (raw) abstain gate.
#[derive(Default, Clone)]
struct WeightedTally {
    weighted_correct: f64,
    weighted_answered: f64,
    raw_correct: u32,
    raw_answered: u32,
}

impl WeightedTally {
    fn add(&mut self, weight: f64, correct: u32, answered: u32) {
        self.weighted_correct += weight * f64::from(correct);
        self.weighted_answered += weight * f64::from(answered);
        self.raw_correct += correct;
        self.raw_answered += answered;
    }

    fn score(&self) -> f64 {
        if self.weighted_answered <= 0.0 {
            0.0
        } else {
            self.weighted_correct / self.weighted_answered
        }
    }
}

/// Per-topic evidence surfaced to the readiness model (single store-read source
/// so readiness never re-parses the blob).
pub(crate) struct TopicEvidence {
    pub score: f64,
    pub range_low: f64,
    pub range_high: f64,
    /// Number of distinct submissions in this set that covered the topic
    /// (drives the readiness ">=1 topical test covering the topic" gate).
    pub tests_covering: u32,
}

/// Recency weight for an attempt of age `now - t`: exponential half-life,
/// clamped so future-dated attempts (clock skew) weigh 1.0.
fn recency_weight(now: i64, t: i64) -> f64 {
    let delta_days = ((now - t).max(0) as f64) / SECS_PER_DAY;
    0.5_f64.powf(delta_days / HALF_LIFE_DAYS)
}

/// Build one submission's attempt record, merging duplicate tags.
fn build_attempt(
    now: i64,
    exam_id: &str,
    test_id: &str,
    results: &[(String, u32, u32)],
) -> ExamAttempt {
    let mut topics: BTreeMap<String, TopicTally> = BTreeMap::new();
    for (topic, correct, answered) in results {
        let tally = topics.entry(topic.clone()).or_default();
        tally.correct += *correct;
        tally.answered += *answered;
    }
    ExamAttempt {
        exam_id: exam_id.to_string(),
        test_id: test_id.to_string(),
        t: now,
        topics,
    }
}

/// Fold a set of attempts into per-topic evidence (recency-weighted).
fn topic_evidence_from(attempts: &[ExamAttempt], now: i64) -> BTreeMap<String, TopicEvidence> {
    let mut tallies: BTreeMap<String, WeightedTally> = BTreeMap::new();
    let mut covering: BTreeMap<String, u32> = BTreeMap::new();
    for attempt in attempts {
        let weight = recency_weight(now, attempt.t);
        for (topic, tally) in &attempt.topics {
            tallies
                .entry(topic.clone())
                .or_default()
                .add(weight, tally.correct, tally.answered);
            if tally.answered > 0 {
                *covering.entry(topic.clone()).or_default() += 1;
            }
        }
    }
    tallies
        .into_iter()
        .map(|(topic, wt)| {
            let score = wt.score();
            let (range_low, range_high) = wilson_interval(score, wt.weighted_answered);
            let tests_covering = covering.get(&topic).copied().unwrap_or(0);
            (
                topic,
                TopicEvidence {
                    score,
                    range_low,
                    range_high,
                    tests_covering,
                },
            )
        })
        .collect()
}

impl Collection {
    /// Load the store, folding any legacy v1 `topics` blob into `topical`.
    fn load_performance_store(&self) -> PerformanceStore {
        let mut store: PerformanceStore = self
            .get_config_optional(PERFORMANCE_CONFIG_KEY)
            .unwrap_or_default();
        if !store.legacy_topics.is_empty() {
            // Historical per-attempt times are unrecoverable, so the migrated
            // evidence starts the decay clock at "now".
            let migrated = std::mem::take(&mut store.legacy_topics);
            store.topical.push(ExamAttempt {
                exam_id: "legacy-migration".to_string(),
                test_id: String::new(),
                t: TimestampSecs::now().0,
                topics: migrated,
            });
            store.version = STORE_VERSION;
        }
        store
    }

    /// Persist one submission, deduping by `exam_id` (a re-POST with a known id
    /// replaces; an empty id is synthesized and appended).
    fn record_attempt(&mut self, full_length: bool, mut attempt: ExamAttempt) -> Result<()> {
        let mut store = self.load_performance_store();
        store.version = STORE_VERSION;
        if attempt.exam_id.is_empty() {
            attempt.exam_id = format!(
                "auto-{}-{}",
                attempt.t,
                store.topical.len() + store.full_length.len()
            );
        }
        let list = if full_length {
            &mut store.full_length
        } else {
            &mut store.topical
        };
        match list.iter_mut().find(|a| a.exam_id == attempt.exam_id) {
            Some(existing) => *existing = attempt,
            None => list.push(attempt),
        }
        // Not undoable: silent accumulation of practice evidence.
        self.set_config_json(PERFORMANCE_CONFIG_KEY, &store, false)?;
        Ok(())
    }

    /// Record one graded topical practice test.
    pub fn add_topical_result(
        &mut self,
        exam_id: &str,
        test_id: &str,
        topic_results: &[(String, u32, u32)],
    ) -> Result<()> {
        self.add_topical_result_at(TimestampSecs::now().0, exam_id, test_id, topic_results)
    }

    pub(crate) fn add_topical_result_at(
        &mut self,
        now: i64,
        exam_id: &str,
        test_id: &str,
        topic_results: &[(String, u32, u32)],
    ) -> Result<()> {
        self.record_attempt(false, build_attempt(now, exam_id, test_id, topic_results))
    }

    /// Record one completed full-length exam (per-topic across all sections).
    pub fn add_full_length_result(
        &mut self,
        exam_id: &str,
        test_id: &str,
        topic_results: &[(String, u32, u32)],
    ) -> Result<()> {
        self.add_full_length_result_at(TimestampSecs::now().0, exam_id, test_id, topic_results)
    }

    pub(crate) fn add_full_length_result_at(
        &mut self,
        now: i64,
        exam_id: &str,
        test_id: &str,
        topic_results: &[(String, u32, u32)],
    ) -> Result<()> {
        self.record_attempt(true, build_attempt(now, exam_id, test_id, topic_results))
    }

    /// The performance model: per-topic and per-section recency-weighted
    /// fraction-correct with a Wilson range, plus an approximate total scaled
    /// score. Topical evidence only.
    pub fn compute_performance(
        &self,
        min_questions: u32,
    ) -> Result<anki_proto::mcat::PerformanceQueryResponse> {
        self.compute_performance_at(TimestampSecs::now().0, min_questions)
    }

    pub(crate) fn compute_performance_at(
        &self,
        now: i64,
        min_questions: u32,
    ) -> Result<anki_proto::mcat::PerformanceQueryResponse> {
        let min_questions = if min_questions == 0 {
            DEFAULT_MIN_QUESTIONS
        } else {
            min_questions
        };
        let store = self.load_performance_store();

        let mut per_topic: BTreeMap<String, WeightedTally> = BTreeMap::new();
        let mut per_section: BTreeMap<String, WeightedTally> = BTreeMap::new();
        let mut overall = WeightedTally::default();

        for attempt in &store.topical {
            let weight = recency_weight(now, attempt.t);
            for (topic, tally) in &attempt.topics {
                per_topic.entry(topic.clone()).or_default().add(
                    weight,
                    tally.correct,
                    tally.answered,
                );
                if let Some(section) = section_of(topic) {
                    per_section.entry(section.to_string()).or_default().add(
                        weight,
                        tally.correct,
                        tally.answered,
                    );
                }
                overall.add(weight, tally.correct, tally.answered);
            }
        }

        let mut topics: Vec<_> = per_topic
            .iter()
            .map(|(topic, wt)| topic_performance(topic.clone(), wt, min_questions))
            .collect();
        topics.sort_by(|a, b| a.topic.cmp(&b.topic));

        // All four sections in canonical order, so the dashboard can render a
        // "Not tested yet" state instead of hiding untested sections (P6).
        let mut sections: Vec<anki_proto::mcat::SectionPerformance> = Vec::new();
        let mut scaled_total = 0u32;
        let mut sections_tested = 0u32;
        for code in SECTIONS {
            let wt = per_section.get(code).cloned().unwrap_or_default();
            let sp = section_performance(code, &wt, min_questions);
            if !sp.not_tested {
                sections_tested += 1;
            }
            if !sp.abstain {
                scaled_total += sp.scaled_score;
            }
            sections.push(sp);
        }

        Ok(anki_proto::mcat::PerformanceQueryResponse {
            topics,
            sections,
            overall: Some(topic_performance(String::new(), &overall, min_questions)),
            scaled_total,
            sections_tested,
        })
    }

    // ---- readiness seam (single store-read source for readiness.rs) --------

    /// Recency-weighted per-topic accuracy from standalone topical tests.
    pub(crate) fn topical_topic_evidence(&self, now: i64) -> BTreeMap<String, TopicEvidence> {
        topic_evidence_from(&self.load_performance_store().topical, now)
    }

    /// Recency-weighted per-topic accuracy *within* completed full-length exams
    /// (R3).
    pub(crate) fn full_length_topic_evidence(&self, now: i64) -> BTreeMap<String, TopicEvidence> {
        topic_evidence_from(&self.load_performance_store().full_length, now)
    }

    /// Number of completed full-length exams on record (R4 gate).
    pub(crate) fn full_length_completed_count(&self) -> u32 {
        self.load_performance_store().full_length.len() as u32
    }
}

/// Extract the MCAT section code from an `aamc::<section>::<topic>` tag.
pub(crate) fn section_of(topic: &str) -> Option<&str> {
    topic
        .strip_prefix(AAMC_TAG_PREFIX)?
        .split("::")
        .next()
        .filter(|s| !s.is_empty())
}

fn topic_performance(
    topic: String,
    wt: &WeightedTally,
    min_questions: u32,
) -> anki_proto::mcat::TopicPerformance {
    let score = wt.score();
    let (low, high) = wilson_interval(score, wt.weighted_answered);
    anki_proto::mcat::TopicPerformance {
        topic,
        score,
        range_low: low,
        range_high: high,
        correct: wt.raw_correct,
        answered: wt.raw_answered,
        abstain: wt.raw_answered < min_questions,
    }
}

fn section_performance(
    code: &str,
    wt: &WeightedTally,
    min_questions: u32,
) -> anki_proto::mcat::SectionPerformance {
    let score = wt.score();
    anki_proto::mcat::SectionPerformance {
        section_code: code.to_string(),
        score,
        scaled_score: scaled_from_fraction(score),
        correct: wt.raw_correct,
        answered: wt.raw_answered,
        abstain: wt.raw_answered < min_questions,
        not_tested: wt.raw_answered == 0,
    }
}

/// Linear raw->scaled approximation: [0,1] -> [118,132].
fn scaled_from_fraction(fraction: f64) -> u32 {
    let span = f64::from(SCALE_MAX - SCALE_MIN);
    (f64::from(SCALE_MIN) + fraction * span).round() as u32
}

/// Wilson score interval (95%) for proportion `p` over an effective `n`
/// (recency-weighted, so fractional). No observations => maximal uncertainty.
/// (Kept local to this module to avoid coupling with the memory model.)
fn wilson_interval(p: f64, n: f64) -> (f64, f64) {
    if n <= 0.0 {
        return (0.0, 1.0);
    }
    let z = 1.96_f64;
    let z2 = z * z;
    let denom = 1.0 + z2 / n;
    let center = (p + z2 / (2.0 * n)) / denom;
    let margin = (z / denom) * (p * (1.0 - p) / n + z2 / (4.0 * n * n)).sqrt();
    (
        (center - margin).clamp(0.0, 1.0),
        (center + margin).clamp(0.0, 1.0),
    )
}

#[cfg(test)]
mod test {
    use super::*;

    // A fixed clock for deterministic recency math.
    const NOW: i64 = 1_800_000_000;
    fn days(n: i64) -> i64 {
        n * 86_400
    }

    #[test]
    fn empty_performance_emits_four_untested_sections() -> Result<()> {
        let col = Collection::new();
        let resp = col.compute_performance_at(NOW, 0)?;
        assert!(resp.topics.is_empty());
        assert_eq!(resp.sections.len(), 4);
        assert!(resp.sections.iter().all(|s| s.not_tested && s.abstain));
        assert_eq!(resp.sections_tested, 0);
        assert_eq!(resp.scaled_total, 0);
        let overall = resp.overall.unwrap();
        assert_eq!(overall.answered, 0);
        assert!(overall.abstain);
        Ok(())
    }

    #[test]
    fn accumulates_and_rolls_up_by_section() -> Result<()> {
        let mut col = Collection::new();
        // Two topics in the same section, recorded across two attempts at the
        // same instant so recency weights are ~1 (reproduces the v1 numbers).
        col.add_topical_result_at(
            NOW,
            "bio-1",
            "bio-biochem-1",
            &[
                ("aamc::bio-biochem::enzyme-kinetics".to_string(), 4, 5),
                ("aamc::bio-biochem::amino-acids".to_string(), 3, 5),
            ],
        )?;
        col.add_topical_result_at(
            NOW,
            "bio-2",
            "bio-biochem-1",
            &[("aamc::bio-biochem::enzyme-kinetics".to_string(), 5, 5)],
        )?;

        let resp = col.compute_performance_at(NOW, 0)?;

        let ek = resp
            .topics
            .iter()
            .find(|t| t.topic == "aamc::bio-biochem::enzyme-kinetics")
            .unwrap();
        assert_eq!(ek.correct, 9);
        assert_eq!(ek.answered, 10);
        assert!(!ek.abstain);
        assert!((ek.score - 0.9).abs() < 1e-9);

        // bio-biochem rollup: 12/15 -> 118 + round(0.8*14) = 129.
        let sec = resp
            .sections
            .iter()
            .find(|s| s.section_code == "bio-biochem")
            .unwrap();
        assert_eq!(sec.correct, 12);
        assert_eq!(sec.answered, 15);
        assert_eq!(sec.scaled_score, 129);
        assert!(!sec.not_tested);
        assert_eq!(resp.sections_tested, 1);
        assert_eq!(resp.scaled_total, 129);
        Ok(())
    }

    #[test]
    fn recency_leans_toward_recent_attempts() -> Result<()> {
        let mut col = Collection::new();
        // Stale attempt (two half-lives ago -> weight 0.25): all wrong.
        col.add_topical_result_at(
            NOW - days(60),
            "old",
            "cars-1",
            &[("aamc::cars::humanities".to_string(), 0, 10)],
        )?;
        // Fresh attempt (weight ~1): all correct.
        col.add_topical_result_at(
            NOW,
            "new",
            "cars-1",
            &[("aamc::cars::humanities".to_string(), 10, 10)],
        )?;

        let resp = col.compute_performance_at(NOW, 0)?;
        let t = resp
            .topics
            .iter()
            .find(|t| t.topic == "aamc::cars::humanities")
            .unwrap();
        // Raw counts stay honest (20 answered), but the weighted score leans to
        // the recent all-correct attempt: 10 / (10 + 0.25*10) = 0.8.
        assert_eq!(t.answered, 20);
        assert_eq!(t.correct, 10);
        assert!((t.score - 0.8).abs() < 1e-6);
        assert!(!t.abstain); // raw answered 20 >= 5
        Ok(())
    }

    #[test]
    fn abstain_uses_raw_answered() -> Result<()> {
        let mut col = Collection::new();
        col.add_topical_result_at(
            NOW,
            "x",
            "cars-1",
            &[("aamc::cars::humanities".to_string(), 2, 3)],
        )?;
        let resp = col.compute_performance_at(NOW, 5)?;
        let t = &resp.topics[0];
        assert_eq!(t.answered, 3);
        assert!(t.abstain); // 3 < 5 (raw)
        Ok(())
    }

    #[test]
    fn full_length_is_separate_from_topical() -> Result<()> {
        let mut col = Collection::new();
        col.add_full_length_result_at(
            NOW,
            "fl-1",
            "full-length",
            &[("aamc::psych-soc::learning".to_string(), 8, 10)],
        )?;
        // Full-length evidence must NOT feed the performance headline.
        let resp = col.compute_performance_at(NOW, 0)?;
        assert!(resp.topics.is_empty());
        assert!(resp.overall.unwrap().abstain);
        // But it is visible to the readiness seam.
        assert_eq!(col.full_length_completed_count(), 1);
        let fl = col.full_length_topic_evidence(NOW);
        let ev = fl.get("aamc::psych-soc::learning").unwrap();
        assert_eq!(ev.tests_covering, 1);
        assert!((ev.score - 0.8).abs() < 1e-9);
        Ok(())
    }

    #[test]
    fn dedupes_by_exam_id() -> Result<()> {
        let mut col = Collection::new();
        let payload = &[("aamc::cars::humanities".to_string(), 5, 10)];
        col.add_topical_result_at(NOW, "same", "cars-1", payload)?;
        col.add_topical_result_at(NOW, "same", "cars-1", payload)?; // replace, not add
        let resp = col.compute_performance_at(NOW, 0)?;
        let t = &resp.topics[0];
        assert_eq!(t.answered, 10); // not 20
        Ok(())
    }

    #[test]
    fn migrates_v1_blob() -> Result<()> {
        let mut col = Collection::new();
        // Seed the old-format blob directly.
        #[derive(Serialize)]
        struct V1 {
            topics: BTreeMap<String, TopicTally>,
        }
        let mut topics = BTreeMap::new();
        topics.insert(
            "aamc::chem-phys::circuits".to_string(),
            TopicTally {
                correct: 6,
                answered: 8,
            },
        );
        col.set_config_json(PERFORMANCE_CONFIG_KEY, &V1 { topics }, false)?;

        let resp = col.compute_performance_at(NOW, 0)?;
        let t = resp
            .topics
            .iter()
            .find(|t| t.topic == "aamc::chem-phys::circuits")
            .unwrap();
        assert_eq!(t.correct, 6);
        assert_eq!(t.answered, 8);
        Ok(())
    }

    #[test]
    fn scaled_endpoints() {
        assert_eq!(scaled_from_fraction(0.0), 118);
        assert_eq!(scaled_from_fraction(1.0), 132);
        assert_eq!(section_of("aamc::chem-phys::circuits"), Some("chem-phys"));
        assert_eq!(section_of("nottagged"), None);
    }
}
