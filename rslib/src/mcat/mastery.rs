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
//! - `MASTERED_RETRIEVABILITY`: a card counts as "mastered" at/above this recall prob.
//! - `MAX_COMFORT_PENALTY` + `SLOW_LATENCY_FACTOR`: how much "effortful" recalls
//!   (a good rating answered slower than ~1.5× the user's median) discount the score.
//! - `DEFAULT_MIN_REVIEWS`: abstain below this many graded reviews for a topic.

use std::collections::HashMap;

use fsrs::FSRS;
use fsrs::FSRS5_DEFAULT_DECAY;

use crate::prelude::*;
use crate::search::SortMode;

const AAMC_TAG_PREFIX: &str = "aamc::";
const MASTERED_RETRIEVABILITY: f64 = 0.9;
// The reviewer now derives the rating from answer time (qt/aqt/reviewer.py), so
// slowness already flows into rating -> FSRS -> retrievability. Discounting again
// here would double-count time, so the penalty is disabled (kept for tunability).
const MAX_COMFORT_PENALTY: f64 = 0.0;
const SLOW_LATENCY_FACTOR: f64 = 1.5;
const DEFAULT_MIN_REVIEWS: u32 = 5;
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
    reviews: u32,
    effortful_reviews: u32,
}

impl TopicAcc {
    fn add(&mut self, card: &CardData, slow_threshold: f64) {
        self.retrievability_sum += card.retrievability;
        self.total_cards += 1;
        if card.retrievability >= MASTERED_RETRIEVABILITY {
            self.mastered += 1;
        }
        self.reviews += card.rated.len() as u32;
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
        let comfort_factor = if self.reviews == 0 {
            1.0
        } else {
            1.0 - MAX_COMFORT_PENALTY * (f64::from(self.effortful_reviews) / f64::from(self.reviews))
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
                topics.entry(topic.clone()).or_default().add(card, slow_threshold);
            }
        }

        let mut topic_results: Vec<_> = topics
            .into_iter()
            .map(|(topic, acc)| acc.finish(topic.clone(), min_reviews))
            .collect();
        topic_results.sort_by(|a, b| a.topic.cmp(&b.topic));

        Ok(anki_proto::mcat::MasteryQueryResponse {
            topics: topic_results,
            overall: Some(overall.finish(String::new(), min_reviews)),
        })
    }
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
    ((center - margin).clamp(0.0, 1.0), (center + margin).clamp(0.0, 1.0))
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
}
