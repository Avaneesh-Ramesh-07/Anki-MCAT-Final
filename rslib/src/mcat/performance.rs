// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! The performance model — topical practice-test scores.
//!
//! When the player grades a practice test it reports, per AAMC topic, how many
//! questions were answered and how many were correct. We accumulate those
//! tallies in a collection config key so repeated attempts build evidence (the
//! same way review count backs the memory score). `compute_performance` then
//! reports, per topic and per MCAT section, the fraction correct with a Wilson
//! range, abstaining below a minimum number of answered questions (the give-up
//! rule), plus an approximate MCAT scaled score.
//!
//! v1 tunables:
//! - `DEFAULT_MIN_QUESTIONS`: abstain below this many answered questions.
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

/// Accumulated practice-test evidence, persisted as JSON in the collection.
#[derive(Default, Serialize, Deserialize)]
struct PerformanceStore {
    /// `aamc::...` topic tag -> running tally.
    topics: BTreeMap<String, TopicAgg>,
}

#[derive(Default, Clone, Serialize, Deserialize)]
struct TopicAgg {
    correct: u32,
    answered: u32,
}

impl TopicAgg {
    fn add(&mut self, other: &TopicAgg) {
        self.correct += other.correct;
        self.answered += other.answered;
    }
}

impl Collection {
    /// Accumulate one graded practice test's per-topic tallies.
    pub fn add_practice_result(&mut self, topic_results: &[(String, u32, u32)]) -> Result<()> {
        let mut store: PerformanceStore =
            self.get_config_optional(PERFORMANCE_CONFIG_KEY).unwrap_or_default();
        for (topic, correct, answered) in topic_results {
            let agg = store.topics.entry(topic.clone()).or_default();
            agg.correct += *correct;
            agg.answered += *answered;
        }
        // Not undoable: silent accumulation of practice evidence.
        self.set_config_json(PERFORMANCE_CONFIG_KEY, &store, false)?;
        Ok(())
    }

    /// The performance model: per-topic and per-section fraction-correct with a
    /// Wilson range, plus an approximate total scaled score.
    pub fn compute_performance(
        &self,
        min_questions: u32,
    ) -> Result<anki_proto::mcat::PerformanceQueryResponse> {
        let min_questions = if min_questions == 0 {
            DEFAULT_MIN_QUESTIONS
        } else {
            min_questions
        };
        let store: PerformanceStore =
            self.get_config_optional(PERFORMANCE_CONFIG_KEY).unwrap_or_default();

        let mut section_aggs: BTreeMap<String, TopicAgg> = BTreeMap::new();
        let mut overall = TopicAgg::default();
        let mut topics: Vec<anki_proto::mcat::TopicPerformance> = Vec::new();

        for (topic, agg) in &store.topics {
            topics.push(topic_performance(topic.clone(), agg, min_questions));
            if let Some(section) = section_of(topic) {
                section_aggs.entry(section.to_string()).or_default().add(agg);
            }
            overall.add(agg);
        }
        topics.sort_by(|a, b| a.topic.cmp(&b.topic));

        // Sections in canonical MCAT order, only those with evidence.
        let mut sections: Vec<anki_proto::mcat::SectionPerformance> = Vec::new();
        let mut scaled_total = 0u32;
        for code in SECTIONS {
            if let Some(agg) = section_aggs.get(code) {
                let sp = section_performance(code, agg, min_questions);
                if !sp.abstain {
                    scaled_total += sp.scaled_score;
                }
                sections.push(sp);
            }
        }

        Ok(anki_proto::mcat::PerformanceQueryResponse {
            topics,
            sections,
            overall: Some(topic_performance(String::new(), &overall, min_questions)),
            scaled_total,
        })
    }
}

/// Extract the MCAT section code from an `aamc::<section>::<topic>` tag.
fn section_of(topic: &str) -> Option<&str> {
    topic
        .strip_prefix(AAMC_TAG_PREFIX)?
        .split("::")
        .next()
        .filter(|s| !s.is_empty())
}

fn topic_performance(
    topic: String,
    agg: &TopicAgg,
    min_questions: u32,
) -> anki_proto::mcat::TopicPerformance {
    let score = fraction(agg.correct, agg.answered);
    let (low, high) = wilson_interval(score, agg.answered);
    anki_proto::mcat::TopicPerformance {
        topic,
        score,
        range_low: low,
        range_high: high,
        correct: agg.correct,
        answered: agg.answered,
        abstain: agg.answered < min_questions,
    }
}

fn section_performance(
    code: &str,
    agg: &TopicAgg,
    min_questions: u32,
) -> anki_proto::mcat::SectionPerformance {
    let score = fraction(agg.correct, agg.answered);
    anki_proto::mcat::SectionPerformance {
        section_code: code.to_string(),
        score,
        scaled_score: scaled_from_fraction(score),
        correct: agg.correct,
        answered: agg.answered,
        abstain: agg.answered < min_questions,
    }
}

fn fraction(correct: u32, answered: u32) -> f64 {
    if answered == 0 {
        0.0
    } else {
        f64::from(correct) / f64::from(answered)
    }
}

/// Linear raw->scaled approximation: [0,1] -> [118,132].
fn scaled_from_fraction(fraction: f64) -> u32 {
    let span = f64::from(SCALE_MAX - SCALE_MIN);
    (f64::from(SCALE_MIN) + fraction * span).round() as u32
}

/// Wilson score interval (95%) for proportion `p` over `n` observations.
/// No observations => maximal uncertainty. (Kept local to this module to avoid
/// coupling with the memory model, which has its own copy.)
fn wilson_interval(p: f64, n: u32) -> (f64, f64) {
    if n == 0 {
        return (0.0, 1.0);
    }
    let n = f64::from(n);
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

    #[test]
    fn empty_performance_abstains() -> Result<()> {
        let col = Collection::new();
        let resp = col.compute_performance(0)?;
        assert!(resp.topics.is_empty());
        assert!(resp.sections.is_empty());
        assert_eq!(resp.scaled_total, 0);
        let overall = resp.overall.unwrap();
        assert_eq!(overall.answered, 0);
        assert!(overall.abstain);
        Ok(())
    }

    #[test]
    fn accumulates_and_rolls_up_by_section() -> Result<()> {
        let mut col = Collection::new();
        // Two topics in the same section, recorded across two attempts.
        col.add_practice_result(&[
            ("aamc::bio-biochem::enzyme-kinetics".to_string(), 4, 5),
            ("aamc::bio-biochem::amino-acids".to_string(), 3, 5),
        ])?;
        col.add_practice_result(&[(
            "aamc::bio-biochem::enzyme-kinetics".to_string(),
            5,
            5,
        )])?;

        let resp = col.compute_performance(0)?;

        // enzyme-kinetics: 9/10 across the two attempts (accumulated).
        let ek = resp
            .topics
            .iter()
            .find(|t| t.topic == "aamc::bio-biochem::enzyme-kinetics")
            .unwrap();
        assert_eq!(ek.correct, 9);
        assert_eq!(ek.answered, 10);
        assert!(!ek.abstain);
        assert!((ek.score - 0.9).abs() < 1e-9);

        // one section rollup: 12 correct / 15 answered.
        assert_eq!(resp.sections.len(), 1);
        let sec = &resp.sections[0];
        assert_eq!(sec.section_code, "bio-biochem");
        assert_eq!(sec.correct, 12);
        assert_eq!(sec.answered, 15);
        // 12/15 = 0.8 -> 118 + round(0.8*14) = 118 + 11 = 129.
        assert_eq!(sec.scaled_score, 129);
        assert_eq!(resp.scaled_total, 129);
        Ok(())
    }

    #[test]
    fn topic_below_threshold_abstains() -> Result<()> {
        let mut col = Collection::new();
        col.add_practice_result(&[("aamc::cars::humanities".to_string(), 2, 3)])?;
        let resp = col.compute_performance(5)?;
        let t = &resp.topics[0];
        assert_eq!(t.answered, 3);
        assert!(t.abstain); // 3 < 5
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
