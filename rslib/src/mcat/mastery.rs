// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! The Mastery Query — the memory model.
//!
//! Per AAMC topic (the `aamc::...` note tag) we aggregate Anki's existing FSRS
//! DSR state into a single **comfort-augmented memory score** with a
//! statistical range, and abstain when there isn't enough review evidence
//! (the give-up rule). This is pure statistics over data Anki already stores —
//! no AI.
//!
//! v1 tunables (documented, expected to be calibrated later):
//! - `MASTERED_RETRIEVABILITY`: a card counts as "mastered" at/above this
//!   recall prob.
//! - `MAX_COMFORT_PENALTY` + `SLOW_LATENCY_FACTOR`: how much "effortful"
//!   recalls (a good rating answered slower than ~1.5× the user's median)
//!   discount the score.
//! - `DEFAULT_MIN_REVIEWS`: abstain below this many *reviewed cards* for a
//!   topic (the evidence unit is distinct studied cards, not individual review
//!   events).

use std::collections::BTreeMap;
use std::collections::HashMap;
use std::sync::LazyLock;

use fsrs::FSRS;
use fsrs::FSRS5_DEFAULT_DECAY;

use super::performance::section_of;
use crate::prelude::*;
use crate::search::SortMode;

const AAMC_TAG_PREFIX: &str = "aamc::";
const MASTERED_RETRIEVABILITY: f64 = 0.9;
// Comfort factor (PRD F2 / §6): the memory score can discount DSR
// retrievability for "effortful" recalls — a Good/Easy rating answered slower
// than SLOW_LATENCY_FACTOR x the user's own median latency (the overconfidence
// signal, Insight 3): comfort_factor = 1 - MAX_COMFORT_PENALTY * (effortful /
// graded_reviews).
//
// Disabled (0.0) to avoid double-counting answer time: the reviewer already
// grades "Got it" by how long the answer took (qt/aqt/reviewer.py), so time
// already flows into rating -> FSRS -> retrievability. Discounting the score
// again here for slowness would count the same signal twice. The effortful
// detection still runs (with a 0.0 penalty it's a no-op), so the factor can be
// tuned back on if the reviewer ever stops grading by time.
const MAX_COMFORT_PENALTY: f64 = 0.0;
const SLOW_LATENCY_FACTOR: f64 = 1.5;
const DEFAULT_MIN_REVIEWS: u32 = 5;
/// Weight for an `aamc::<section>::...` tag whose section is not one of the
/// four canonical AAMC sections in `aamc_weights.json` (malformed /
/// off-taxonomy). Roughly the mean of the real section weights, so such a topic
/// still counts about like an average section in the overall roll-up.
const DEFAULT_SECTION_WEIGHT: f64 = 57.0;
/// Rating buttons that claim comfort (Good / Easy); an effortful one of these
/// is the overconfidence signal from Insight 3.
const GOOD_BUTTON: u8 = 3;

/// Per-card data gathered in pass 1, before the user's median latency is known.
struct CardData {
    topics: Vec<String>,
    retrievability: f64,
    /// (taken_millis, button_chosen) for each graded review of this card.
    rated: Vec<(u32, u8)>,
}

#[derive(Default)]
struct TopicAcc {
    retrievability_sum: f64,
    total_cards: u32,
    mastered: u32,
    /// Distinct cards with >=1 graded review — the evidence unit for the
    /// give-up rule and the Wilson n (one studied card = one observation).
    reviews: u32,
    /// Individual graded review events — the denominator for the comfort factor
    /// (which is a per-event ratio), kept separate from the card count.
    graded_reviews: u32,
    effortful_reviews: u32,
}

impl TopicAcc {
    fn add(&mut self, card: &CardData, slow_threshold: f64) {
        self.retrievability_sum += card.retrievability;
        self.total_cards += 1;
        if card.retrievability >= MASTERED_RETRIEVABILITY {
            self.mastered += 1;
        }
        if !card.rated.is_empty() {
            self.reviews += 1;
        }
        self.graded_reviews += card.rated.len() as u32;
        self.effortful_reviews += card
            .rated
            .iter()
            .filter(|(latency, button)| {
                *button >= GOOD_BUTTON && f64::from(*latency) > slow_threshold
            })
            .count() as u32;
    }

    fn finish(&self, topic: String, min_reviews: u32) -> anki_proto::mcat::TopicMastery {
        // mean retrievability over the topic's cards (unstudied cards = 0).
        let raw = if self.total_cards == 0 {
            0.0
        } else {
            self.retrievability_sum / f64::from(self.total_cards)
        };
        // comfort augmentation: effortful (slow but "comfortable") recalls
        // discount the raw DSR score.
        let comfort_factor = if self.graded_reviews == 0 {
            1.0
        } else {
            1.0 - MAX_COMFORT_PENALTY
                * (f64::from(self.effortful_reviews) / f64::from(self.graded_reviews))
        };
        let (low, high) = wilson_interval(raw, self.reviews);
        anki_proto::mcat::TopicMastery {
            topic,
            memory_score: (raw * comfort_factor).clamp(0.0, 1.0),
            range_low: (low * comfort_factor).clamp(0.0, 1.0),
            range_high: (high * comfort_factor).clamp(0.0, 1.0),
            mastered_count: self.mastered,
            total_cards: self.total_cards,
            reviews: self.reviews,
            abstain: self.reviews < min_reviews,
        }
    }
}

impl Collection {
    /// The memory model: per-AAMC-topic comfort-augmented DSR score + range.
    pub fn mastery_query(
        &mut self,
        search: &str,
        min_reviews: u32,
    ) -> Result<anki_proto::mcat::MasteryQueryResponse> {
        let min_reviews = if min_reviews == 0 {
            DEFAULT_MIN_REVIEWS
        } else {
            min_reviews
        };

        // S6: FSRS is mandatory for the memory model, which reads FSRS DSR state
        // and must never fall back to SM-2. Force-enable it if the collection
        // still has it off so DSR state is populated going forward.
        if !self.get_config_bool(BoolKey::Fsrs) {
            self.set_config_bool(BoolKey::Fsrs, true, false)?;
        }

        let cids = self.search_cards(search, SortMode::NoOrder)?;
        let now = self.timing_today()?.now;
        let fsrs = FSRS::new(None).unwrap();

        // Pass 1: gather per-card retrievability + rated-review latencies, and
        // collect every latency to derive the user's median.
        let mut cards = Vec::with_capacity(cids.len());
        let mut all_latencies: Vec<u32> = Vec::new();
        for cid in cids {
            let Some(card) = self.storage.get_card(cid)? else {
                continue;
            };
            let topics = self
                .storage
                .get_note(card.note_id)?
                .map(|note| {
                    note.tags
                        .into_iter()
                        .filter(|t| t.starts_with(AAMC_TAG_PREFIX))
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default();

            let last_review_time = match card.last_review_time {
                Some(t) => Some(t),
                None => self.storage.time_of_last_review(cid)?,
            };
            let retrievability = match (card.memory_state, last_review_time) {
                (Some(state), Some(last)) => {
                    let seconds = now.elapsed_secs_since(last).max(0) as u32;
                    let decay = card.decay.unwrap_or(FSRS5_DEFAULT_DECAY);
                    f64::from(fsrs.current_retrievability_seconds(state.into(), seconds, decay))
                }
                _ => 0.0,
            };

            let rated: Vec<(u32, u8)> = self
                .storage
                .get_revlog_entries_for_card(cid)?
                .into_iter()
                .filter(|e| e.has_rating())
                .map(|e| (e.taken_millis, e.button_chosen))
                .collect();
            for (latency, _) in &rated {
                all_latencies.push(*latency);
            }

            cards.push(CardData {
                topics,
                retrievability,
                rated,
            });
        }

        let slow_threshold = median(&mut all_latencies) * SLOW_LATENCY_FACTOR;

        // Pass 2: aggregate per topic + an overall rollup across every card.
        let mut topics: HashMap<String, TopicAcc> = HashMap::new();
        let mut overall = TopicAcc::default();
        for card in &cards {
            overall.add(card, slow_threshold);
            for topic in &card.topics {
                topics
                    .entry(topic.clone())
                    .or_default()
                    .add(card, slow_threshold);
            }
        }

        let mut topic_results: Vec<_> = topics
            .into_iter()
            .map(|(topic, acc)| acc.finish(topic.clone(), min_reviews))
            .collect();
        topic_results.sort_by(|a, b| a.topic.cmp(&b.topic));

        // Overall: keep the collection-wide counts + evidence gate from the
        // pooled accumulator (so `total_cards` / `reviews` / `abstain` still
        // reflect everything studied, including untagged cards), but replace the
        // headline score + band with an AAMC-content-weighted roll-up of the
        // per-topic results. A topic's influence then comes from the exam
        // blueprint rather than from how many cards you happened to add, and the
        // band stays honestly wide — dominated by your least-studied high-weight
        // topics — instead of the falsely narrow band a single pooled Wilson
        // interval over all reviews reports.
        let mut overall = overall.finish(String::new(), min_reviews);
        let (score, low, high) = weighted_rollup(&topic_results);
        overall.memory_score = score;
        overall.range_low = low;
        overall.range_high = high;

        Ok(anki_proto::mcat::MasteryQueryResponse {
            topics: topic_results,
            overall: Some(overall),
        })
    }
}

/// AAMC per-section weights, read from the same `aamc_weights.json` the
/// readiness model uses — one source of truth for the weight values. Keyed by
/// the four canonical section codes; the `_comment` (and any non-numeric entry)
/// is dropped. Parsed once. (The loader mirrors the one in `readiness.rs`;
/// centralizing both into a shared helper is a follow-up, kept separate here to
/// avoid editing that module while it is under active development.)
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

/// AAMC-weighted roll-up of the per-topic memory results into the overall
/// (score, range_low, range_high), using the *same* weighting the readiness
/// model uses: group topics by AAMC section, average them **uniformly within a
/// section** (AAMC publishes scored-question counts only per section, so
/// disciplines/sub-topics inside a section are treated equally), then combine
/// across the sections present using the shared per-section weights,
/// re-normalized over those present sections. A topic's influence thus comes
/// from the exam blueprint, not from how many cards you happened to add.
///
/// Unlike the readiness model (which keeps every section in the denominator so
/// untested sections drag the score down), this re-normalizes over present
/// sections only: the memory score answers "how well do you recall what you've
/// studied," and penalizing untouched sections is readiness's job.
///
/// The band bounds are propagated the same conservative (comonotonic) way,
/// keeping the overall interval about as wide as your weakest high-weight
/// section rather than shrinking it the way an independence assumption would.
/// Returns (0.0, 0.0, 0.0) when no topic maps to a section (e.g. empty).
fn weighted_rollup(topics: &[anki_proto::mcat::TopicMastery]) -> (f64, f64, f64) {
    #[derive(Default)]
    struct SectionAcc {
        n: f64,
        score: f64,
        low: f64,
        high: f64,
    }
    // Uniform within-section accumulation of each topic's score + band.
    let mut sections: BTreeMap<&str, SectionAcc> = BTreeMap::new();
    for t in topics {
        let Some(section) = section_of(&t.topic) else {
            continue;
        };
        let acc = sections.entry(section).or_default();
        acc.n += 1.0;
        acc.score += t.memory_score;
        acc.low += t.range_low;
        acc.high += t.range_high;
    }

    let weights = section_weights();
    let mut weight_sum = 0.0;
    let (mut score, mut low, mut high) = (0.0, 0.0, 0.0);
    for (section, acc) in &sections {
        if acc.n <= 0.0 {
            continue;
        }
        let w = weights
            .get(*section)
            .copied()
            .unwrap_or(DEFAULT_SECTION_WEIGHT);
        weight_sum += w;
        score += w * (acc.score / acc.n);
        low += w * (acc.low / acc.n);
        high += w * (acc.high / acc.n);
    }
    if weight_sum <= 0.0 {
        return (0.0, 0.0, 0.0);
    }
    (score / weight_sum, low / weight_sum, high / weight_sum)
}

/// Wilson score interval (95%) for proportion `p` backed by `n` observations.
/// With no observations we report maximal uncertainty.
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

/// Median of the values as f64 (0.0 if empty). Sorts the slice in place.
fn median(values: &mut [u32]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.sort_unstable();
    let mid = values.len() / 2;
    if values.len() % 2 == 0 {
        (f64::from(values[mid - 1]) + f64::from(values[mid])) / 2.0
    } else {
        f64::from(values[mid])
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::card::FsrsMemoryState;
    use crate::revlog::RevlogEntry;
    use crate::revlog::RevlogReviewKind;

    /// Adds a Basic note tagged `tag`, then drives its card's FSRS state so a
    /// test can control retrievability + comfort deterministically without the
    /// scheduler: sets memory stability, backdates the last review by
    /// `days_since_review` days, and writes one revlog per `(taken_millis,
    /// button)` in `reviews`. Retrievability then follows the FSRS forgetting
    /// curve R = (days/stability * 0.2346 + 1)^-0.5 (R = 0.9 at t = stability).
    fn add_reviewed_card(
        col: &mut Collection,
        tag: &str,
        stability_days: f32,
        days_since_review: i64,
        reviews: &[(u32, u8)],
    ) -> Result<()> {
        let nt = col.get_notetype_by_name("Basic")?.unwrap();
        let mut note = nt.new_note();
        note.tags = vec![tag.to_string()];
        col.add_note(&mut note, DeckId(1))?;
        let cid = col.search_cards(&format!("nid:{}", note.id), SortMode::NoOrder)?[0];

        let mut card = col.storage.get_card(cid)?.unwrap();
        card.memory_state = Some(FsrsMemoryState {
            stability: stability_days,
            difficulty: 5.0,
        });
        card.last_review_time = Some(TimestampSecs::now().adding_secs(-days_since_review * 86_400));
        card.decay = Some(FSRS5_DEFAULT_DECAY);
        col.storage.update_card(&card)?;

        for (i, (taken, button)) in reviews.iter().enumerate() {
            let entry = RevlogEntry {
                id: RevlogId(cid.0 + i as i64 + 1),
                cid,
                usn: Usn(-1),
                button_chosen: *button,
                interval: 1,
                last_interval: 1,
                ease_factor: 2500,
                taken_millis: *taken,
                review_kind: RevlogReviewKind::Review,
            };
            col.storage.add_revlog_entry(&entry, true)?;
        }
        Ok(())
    }

    #[test]
    fn empty_collection_abstains() -> Result<()> {
        let mut col = Collection::new();
        let resp = col.mastery_query("", 0)?;
        assert!(resp.topics.is_empty());
        let overall = resp.overall.unwrap();
        assert_eq!(overall.total_cards, 0);
        assert_eq!(overall.reviews, 0);
        assert!(overall.abstain);
        Ok(())
    }

    /// Spec test 1: nothing studied → every topic abstains (score 0), while the
    /// per-topic grouping by `aamc::` tag still works.
    #[test]
    fn groups_unstudied_cards_by_aamc_tag() -> Result<()> {
        let mut col = Collection::new();
        let nt = col.get_notetype_by_name("Basic")?.unwrap();

        let mut n1 = nt.new_note();
        n1.tags = vec!["aamc::biochem::amino-acids".to_string()];
        col.add_note(&mut n1, DeckId(1))?;

        let mut n2 = nt.new_note();
        n2.tags = vec!["aamc::physics::kinematics".to_string()];
        col.add_note(&mut n2, DeckId(1))?;

        // an untagged note: counts in the overall rollup but in no topic.
        let mut n3 = nt.new_note();
        col.add_note(&mut n3, DeckId(1))?;

        let resp = col.mastery_query("", 0)?;

        // two topics, sorted by tag name.
        assert_eq!(resp.topics.len(), 2);
        assert_eq!(resp.topics[0].topic, "aamc::biochem::amino-acids");
        assert_eq!(resp.topics[1].topic, "aamc::physics::kinematics");

        // unstudied → score 0, nothing mastered, and abstaining (0 reviews < N).
        let topic = &resp.topics[0];
        assert_eq!(topic.total_cards, 1);
        assert_eq!(topic.mastered_count, 0);
        assert_eq!(topic.reviews, 0);
        assert_eq!(topic.memory_score, 0.0);
        assert!(topic.abstain);

        // overall sees all three cards.
        assert_eq!(resp.overall.unwrap().total_cards, 3);
        Ok(())
    }

    /// Spec test 2: all cards studied but poorly known. A slow/hard learner's
    /// low ratings leave low FSRS stability, so with time elapsed the
    /// retrievability — and thus the memory score — comes out low. (Answer
    /// time reaches the score via the reviewer's rating → FSRS, modeled
    /// here as the low stability; the scoring-time comfort factor is
    /// disabled, see MAX_COMFORT_PENALTY.)
    #[test]
    fn poorly_studied_scores_low() -> Result<()> {
        let mut col = Collection::new();
        // Each card: stability 1 day, last reviewed ~99 days ago → the FSRS
        // forgetting curve gives retrievability ≈ 0.20.
        let reviews = [(3000, 3)];
        for _ in 0..6 {
            add_reviewed_card(&mut col, "aamc::bio-biochem::biology", 1.0, 99, &reviews)?;
        }

        let resp = col.mastery_query("", 0)?;
        let topic = &resp.topics[0];
        assert_eq!(topic.topic, "aamc::bio-biochem::biology");
        assert!(!topic.abstain, "6 studied cards clears the give-up gate");
        assert!(topic.reviews >= 5);
        assert!(
            topic.memory_score > 0.0 && topic.memory_score < 0.35,
            "poorly retained → low score, got {}",
            topic.memory_score
        );
        Ok(())
    }

    /// Spec test 3: all cards studied to a moderate level — decent FSRS
    /// stability with some time elapsed, answered at a steady
    /// (non-effortful) pace — so the memory score is high but short of
    /// 100%.
    #[test]
    fn moderately_studied_scores_high_not_full() -> Result<()> {
        let mut col = Collection::new();
        // stability 15 days, last reviewed 10 days ago → retrievability ≈ 0.93.
        // Uniform latencies → no review is "slow vs median" → no comfort penalty.
        let reviews = [(3000, 3), (3000, 3), (3000, 3)];
        for _ in 0..6 {
            add_reviewed_card(&mut col, "aamc::bio-biochem::biology", 15.0, 10, &reviews)?;
        }

        let resp = col.mastery_query("", 0)?;
        let topic = &resp.topics[0];
        assert!(!topic.abstain);
        assert!(
            topic.memory_score > 0.85 && topic.memory_score < 0.98,
            "moderately retained → high but not full, got {}",
            topic.memory_score
        );
        Ok(())
    }

    #[test]
    fn reviews_count_distinct_cards_not_events() {
        // The evidence unit is cards: a card reviewed many times still counts
        // once toward `reviews` (Wilson n / give-up gate), while `graded_reviews`
        // keeps the raw event count for the comfort denominator.
        let mut acc = TopicAcc::default();
        let reviewed_4x = CardData {
            topics: vec![],
            retrievability: 0.5,
            rated: vec![(1000, 3), (1200, 3), (900, 4), (1100, 3)],
        };
        let reviewed_1x = CardData {
            topics: vec![],
            retrievability: 0.8,
            rated: vec![(800, 3)],
        };
        let unseen = CardData {
            topics: vec![],
            retrievability: 0.0,
            rated: vec![],
        };
        acc.add(&reviewed_4x, f64::MAX);
        acc.add(&reviewed_1x, f64::MAX);
        acc.add(&unseen, f64::MAX);

        assert_eq!(acc.total_cards, 3);
        assert_eq!(acc.reviews, 2); // 2 cards had >=1 review (not 5 events)
        assert_eq!(acc.graded_reviews, 5); // 4 + 1 raw events
    }

    #[test]
    fn wilson_interval_behaves() {
        // no evidence → full [0,1] uncertainty.
        assert_eq!(wilson_interval(0.0, 0), (0.0, 1.0));
        // with evidence the interval brackets the estimate and stays in [0,1].
        let (low, high) = wilson_interval(0.8, 50);
        assert!(low >= 0.0 && high <= 1.0);
        assert!(low < 0.8 && high > 0.8);
        assert!(high - low > 0.0);
    }

    #[test]
    fn overall_is_section_weighted_rollup_not_card_pool() {
        use anki_proto::mcat::TopicMastery;
        let tm = |topic: &str, score: f64, low: f64, high: f64| TopicMastery {
            topic: topic.to_string(),
            memory_score: score,
            range_low: low,
            range_high: high,
            mastered_count: 0,
            total_cards: 1,
            reviews: 1,
            abstain: false,
        };
        // bio-biochem has two disciplines: they are averaged UNIFORMLY within the
        // section (0.9, 0.3 -> 0.6), matching the readiness model (AAMC publishes
        // counts only per section). chem-phys contributes physics (0.5).
        let topics = vec![
            tm("aamc::bio-biochem::biology", 0.9, 0.8, 1.0),
            tm("aamc::bio-biochem::biochemistry", 0.3, 0.2, 0.4),
            tm("aamc::chem-phys::physics", 0.5, 0.4, 0.6),
        ];
        let (score, low, high) = weighted_rollup(&topics);

        // Section-weighted mean of the within-section means, using the shared
        // aamc_weights.json values (read here so the test survives retuning them).
        let w = section_weights();
        let bio = w.get("bio-biochem").copied().unwrap();
        let cp = w.get("chem-phys").copied().unwrap();
        let expected = (bio * 0.6 + cp * 0.5) / (bio + cp);
        assert!((score - expected).abs() < 1e-9);

        // It is NOT the naive per-topic mean ((0.9+0.3+0.5)/3): biology and
        // biochemistry share bio-biochem's weight rather than counting as two.
        assert!((score - (0.9 + 0.3 + 0.5) / 3.0).abs() > 1e-3);

        // Band propagated the same way: brackets the score, stays in [0,1].
        assert!(low < score && high > score);
        assert!(low >= 0.0 && high <= 1.0);

        // No topics → zeros.
        assert_eq!(weighted_rollup(&[]), (0.0, 0.0, 0.0));
    }
}
