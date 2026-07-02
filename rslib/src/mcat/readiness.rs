// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! The Readiness Query — the composite model ("what would you score today?").
//!
//! Readiness is the *only* sanctioned composite. Per AAMC topic it is a
//! weighted sum of three independent signals:
//!
//! ```text
//! readiness(topic) = 0.05 * memory(topic)          // Mastery Query (FSRS recall)
//!                  + 0.45 * topical(topic)          // standalone topical tests
//!                  + 0.50 * full_length(topic)      // that topic WITHIN full-lengths
//! ```
//!
//! Design choices worth stating explicitly:
//! - **Missing component = 0** (not ignored): a topic with strong memory but no
//!   topical/full-length evidence is dragged down (anti-overconfidence, R2.2).
//!   A missing component contributes 0 to both the point estimate *and* the
//!   range endpoints (a certain 0, not Wilson's [0,1] "no data" interval).
//! - The range is the weighted envelope of the components' Wilson endpoints — a
//!   conservative linear blend, not a rigorous joint confidence interval.
//! - **Compound give-up (R4):** a topic abstains until it has enough card
//!   evidence AND >=1 topical test covering it AND >=1 completed full-length
//!   exam on record. With no full-length at all, every topic abstains.
//! - **Full (overall) readiness (R5):** an AAMC-content-weighted aggregate over
//!   the whole taxonomy; unstudied *or* individually-abstaining topics count as
//!   0 (MBH-1, anti-overconfidence). It abstains only until the first
//!   full-length is completed, then reports a real number dragged toward 0 by
//!   every thin/untouched topic.
//!
//! The three MBH-1 states never collapse together: *abstain* (no number),
//! *missing-component 0* (a studied topic missing one component, dragging the
//! shown score down), and *unstudied 0* (untouched topics dragging the overall
//! aggregate).

use std::collections::BTreeMap;
use std::collections::BTreeSet;
use std::sync::LazyLock;

use anki_proto::mcat::ReadinessComponents;
use anki_proto::mcat::TopicMastery;
use anki_proto::mcat::TopicReadiness;

use super::performance::section_of;
use super::performance::TopicEvidence;
use crate::prelude::*;

/// Component weights (R2.1): memory lowest, topical middle, full-length
/// highest.
const W_MEMORY: f64 = 0.05;
const W_TOPICAL: f64 = 0.45;
const W_FULL_LENGTH: f64 = 0.50;
/// Card gate (R4): a topic needs at least this many reviewed cards. "reviews"
/// is the count of distinct studied cards (see mastery.rs).
const DEFAULT_MIN_REVIEWED_CARDS: u32 = 5;

/// AAMC per-section weights (R5), embedded and parsed once. Keyed by the four
/// canonical section codes; the value is that section's scored-question count.
/// The `_comment` (and any non-numeric entry) is dropped.
static SECTION_WEIGHTS: LazyLock<BTreeMap<String, f64>> = LazyLock::new(|| {
    let raw: BTreeMap<String, serde_json::Value> =
        serde_json::from_str(include_str!("aamc_weights.json"))
            .expect("aamc_weights.json must be valid JSON");
    raw.into_iter()
        .filter(|(k, _)| !k.starts_with('_'))
        .filter_map(|(k, v)| v.as_f64().map(|w| (k, w)))
        .collect()
});

fn section_weights() -> &'static BTreeMap<String, f64> {
    &SECTION_WEIGHTS
}

impl Collection {
    /// The readiness model: per-topic composite + an AAMC-weighted overall.
    pub fn readiness_query(
        &mut self,
        search: &str,
        min_reviews: u32,
        _min_questions: u32,
    ) -> Result<anki_proto::mcat::ReadinessQueryResponse> {
        let min_reviewed_cards = if min_reviews == 0 {
            DEFAULT_MIN_REVIEWED_CARDS
        } else {
            min_reviews
        };

        // Memory (also force-enables FSRS per S6). Pass min_reviews through so
        // the memory model uses the same gate default.
        let mastery = self.mastery_query(search, min_reviews)?;
        let now = TimestampSecs::now().0;
        let topical = self.topical_topic_evidence(now);
        let full_length = self.full_length_topic_evidence(now);
        let completed_fls = self.full_length_completed_count();

        let memory: BTreeMap<&str, &TopicMastery> = mastery
            .topics
            .iter()
            .map(|t| (t.topic.as_str(), t))
            .collect();

        // Every topic with any evidence, from any of the three signals.
        let mut topic_set: BTreeSet<String> = BTreeSet::new();
        topic_set.extend(mastery.topics.iter().map(|t| t.topic.clone()));
        topic_set.extend(topical.keys().cloned());
        topic_set.extend(full_length.keys().cloned());

        let mut computed: BTreeMap<String, TopicReadiness> = BTreeMap::new();
        for topic in &topic_set {
            let tr = compute_topic_readiness(
                topic.clone(),
                memory.get(topic.as_str()).copied(),
                topical.get(topic),
                full_length.get(topic),
                completed_fls,
                min_reviewed_cards,
            );
            computed.insert(topic.clone(), tr);
        }

        // BTreeMap keeps topics sorted by tag.
        let topics: Vec<TopicReadiness> = computed.values().cloned().collect();
        let overall = aggregate_overall(&computed, completed_fls, section_weights());

        Ok(anki_proto::mcat::ReadinessQueryResponse {
            topics,
            overall: Some(overall),
        })
    }
}

/// Compose one topic's readiness from its three (optional) component signals.
fn compute_topic_readiness(
    topic: String,
    memory: Option<&TopicMastery>,
    topical: Option<&TopicEvidence>,
    full_length: Option<&TopicEvidence>,
    completed_fls: u32,
    min_reviewed_cards: u32,
) -> TopicReadiness {
    // Missing component => 0 for both the point estimate and its range (R2.2).
    let (mem, mem_lo, mem_hi, cards) = match memory {
        Some(m) => (m.memory_score, m.range_low, m.range_high, m.reviews),
        None => (0.0, 0.0, 0.0, 0),
    };
    let (top, top_lo, top_hi, tests) = match topical {
        Some(e) => (e.score, e.range_low, e.range_high, e.tests_covering),
        None => (0.0, 0.0, 0.0, 0),
    };
    let (fl, fl_lo, fl_hi, has_fl_topic) = match full_length {
        Some(e) => (e.score, e.range_low, e.range_high, true),
        None => (0.0, 0.0, 0.0, false),
    };

    let readiness = W_MEMORY * mem + W_TOPICAL * top + W_FULL_LENGTH * fl;
    let range_low = W_MEMORY * mem_lo + W_TOPICAL * top_lo + W_FULL_LENGTH * fl_lo;
    let range_high = W_MEMORY * mem_hi + W_TOPICAL * top_hi + W_FULL_LENGTH * fl_hi;

    // Compound give-up rule (R4).
    let cards_ok = cards >= min_reviewed_cards;
    let topical_ok = tests >= 1;
    let fl_ok = completed_fls >= 1;
    let abstain = !(cards_ok && topical_ok && fl_ok);

    TopicReadiness {
        topic,
        readiness_score: readiness.clamp(0.0, 1.0),
        range_low: range_low.clamp(0.0, 1.0),
        range_high: range_high.clamp(0.0, 1.0),
        components: Some(ReadinessComponents {
            memory: mem,
            topical: top,
            full_length: fl,
            has_memory: cards >= 1,
            has_topical: tests >= 1,
            has_full_length: has_fl_topic,
            memory_contribution: W_MEMORY * mem,
            topical_contribution: W_TOPICAL * top,
            full_length_contribution: W_FULL_LENGTH * fl,
        }),
        abstain,
        reviewed_cards: cards,
        topical_tests: tests,
        has_completed_full_length: fl_ok,
    }
}

/// Per-section running mean of the non-abstaining topics in that section.
#[derive(Default)]
struct SectionAcc {
    n: f64,
    score: f64,
    low: f64,
    high: f64,
    mem: f64,
    top: f64,
    fl: f64,
}

/// R5: AAMC-section-weighted aggregate. Each section contributes the mean
/// readiness of its non-abstaining topics, weighted by that section's share of
/// scored questions (`section_weights`). All four sections stay in the
/// denominator, so an untested section — or an
/// individually-abstaining/unstudied topic — contributes 0 and drags the
/// overall down (MBH-1, anti-overconfidence). Sub-topic weighting within a
/// section is uniform (AAMC publishes counts only per section). The overall
/// abstains until the first full-length is completed.
fn aggregate_overall(
    computed: &BTreeMap<String, TopicReadiness>,
    completed_fls: u32,
    section_weights: &BTreeMap<String, f64>,
) -> TopicReadiness {
    let mut sections: BTreeMap<String, SectionAcc> = BTreeMap::new();
    for tr in computed.values() {
        if tr.abstain {
            continue;
        }
        let Some(section) = section_of(&tr.topic) else {
            continue;
        };
        let acc = sections.entry(section.to_string()).or_default();
        acc.n += 1.0;
        acc.score += tr.readiness_score;
        acc.low += tr.range_low;
        acc.high += tr.range_high;
        if let Some(c) = &tr.components {
            acc.mem += c.memory_contribution;
            acc.top += c.topical_contribution;
            acc.fl += c.full_length_contribution;
        }
    }

    let mut total_w = 0.0;
    let (mut num, mut num_lo, mut num_hi) = (0.0, 0.0, 0.0);
    let (mut mem_c, mut top_c, mut fl_c) = (0.0, 0.0, 0.0);
    for (section, w) in section_weights {
        total_w += w;
        // An untested section (no non-abstaining topics) contributes 0.
        if let Some(acc) = sections.get(section) {
            if acc.n > 0.0 {
                num += w * (acc.score / acc.n);
                num_lo += w * (acc.low / acc.n);
                num_hi += w * (acc.high / acc.n);
                mem_c += w * (acc.mem / acc.n);
                top_c += w * (acc.top / acc.n);
                fl_c += w * (acc.fl / acc.n);
            }
        }
    }

    let norm = if total_w > 0.0 { total_w } else { 1.0 };
    let memory_contribution = mem_c / norm;
    let topical_contribution = top_c / norm;
    let full_length_contribution = fl_c / norm;

    TopicReadiness {
        topic: String::new(),
        readiness_score: (num / norm).clamp(0.0, 1.0),
        range_low: (num_lo / norm).clamp(0.0, 1.0),
        range_high: (num_hi / norm).clamp(0.0, 1.0),
        components: Some(ReadinessComponents {
            // Section-weighted average component values.
            memory: memory_contribution / W_MEMORY,
            topical: topical_contribution / W_TOPICAL,
            full_length: full_length_contribution / W_FULL_LENGTH,
            has_memory: false,
            has_topical: false,
            has_full_length: false,
            memory_contribution,
            topical_contribution,
            full_length_contribution,
        }),
        // R4/R5: no full-length on record => the composite abstains entirely.
        abstain: completed_fls == 0,
        reviewed_cards: 0,
        topical_tests: 0,
        has_completed_full_length: completed_fls >= 1,
    }
}

#[cfg(test)]
mod test {
    use super::*;

    fn mastery(topic: &str, score: f64, reviews: u32) -> TopicMastery {
        TopicMastery {
            topic: topic.to_string(),
            memory_score: score,
            range_low: score,
            range_high: score,
            reviews,
            ..Default::default()
        }
    }
    fn evidence(score: f64, tests: u32) -> TopicEvidence {
        TopicEvidence {
            score,
            range_low: score,
            range_high: score,
            tests_covering: tests,
        }
    }

    #[test]
    fn all_components_present_passes_gate_and_weights() {
        let m = mastery("aamc::bio-biochem::enzyme-kinetics", 0.8, 6);
        let top = evidence(0.6, 2);
        let fl = evidence(0.4, 1);
        let tr = compute_topic_readiness(m.topic.clone(), Some(&m), Some(&top), Some(&fl), 1, 5);
        assert!(!tr.abstain);
        // 0.05*0.8 + 0.45*0.6 + 0.50*0.4 = 0.04 + 0.27 + 0.20 = 0.51
        assert!((tr.readiness_score - 0.51).abs() < 1e-9);
        let c = tr.components.unwrap();
        assert!(c.has_memory && c.has_topical && c.has_full_length);
        assert!((c.topical_contribution - 0.27).abs() < 1e-9);
    }

    #[test]
    fn missing_full_length_component_drags_without_abstaining() {
        // Gate satisfied (>=5 cards, >=1 topical test, a full-length exists), but
        // this topic had NO questions in any full-length -> component 3 = 0.
        let m = mastery("aamc::cars::humanities", 1.0, 10);
        let top = evidence(1.0, 2);
        let tr = compute_topic_readiness(m.topic.clone(), Some(&m), Some(&top), None, 1, 5);
        assert!(!tr.abstain); // MBH-1: a real, shown low score (not abstain)
                              // 0.05*1 + 0.45*1 + 0.50*0 = 0.5 (the missing 50% drags it down).
        assert!((tr.readiness_score - 0.5).abs() < 1e-9);
        let c = tr.components.unwrap();
        assert!(c.has_memory && c.has_topical && !c.has_full_length);
    }

    #[test]
    fn abstains_without_full_length() {
        let m = mastery("aamc::psych-soc::learning", 0.9, 20);
        let top = evidence(0.8, 3);
        // completed_fls = 0 -> abstain regardless of strong memory + topical.
        let tr = compute_topic_readiness(m.topic.clone(), Some(&m), Some(&top), None, 0, 5);
        assert!(tr.abstain);
        assert!(!tr.has_completed_full_length);
    }

    #[test]
    fn abstains_below_card_gate() {
        let m = mastery("aamc::chem-phys::circuits", 0.9, 3); // 3 < 5 cards
        let top = evidence(0.8, 3);
        let fl = evidence(0.7, 1);
        let tr = compute_topic_readiness(m.topic.clone(), Some(&m), Some(&top), Some(&fl), 1, 5);
        assert!(tr.abstain);
        assert_eq!(tr.reviewed_cards, 3);
    }

    #[test]
    fn overall_abstains_with_no_full_length_but_scores_after() {
        let mut computed = BTreeMap::new();
        let m = mastery("aamc::bio-biochem::x", 1.0, 10);
        let top = evidence(1.0, 2);
        let fl = evidence(1.0, 1);
        computed.insert(
            "aamc::bio-biochem::x".to_string(),
            compute_topic_readiness(
                "aamc::bio-biochem::x".to_string(),
                Some(&m),
                Some(&top),
                Some(&fl),
                1,
                5,
            ),
        );
        // Section weights: bio-biochem has evidence (readiness 1.0); cars is
        // untested and stays in the denominator, dragging the overall down.
        let mut weights = BTreeMap::new();
        weights.insert("bio-biochem".to_string(), 1.0);
        weights.insert("cars".to_string(), 1.0);

        // No full-length -> abstain.
        let o0 = aggregate_overall(&computed, 0, &weights);
        assert!(o0.abstain);

        // With a full-length: real number. bio-biochem section mean = 1.0, cars
        // untested = 0, weighted over both sections => (1*1.0 + 1*0)/2 = 0.5.
        let o1 = aggregate_overall(&computed, 1, &weights);
        assert!(!o1.abstain);
        assert!((o1.readiness_score - 0.5).abs() < 1e-9);
    }
}
