// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

use crate::collection::Collection;
use crate::error;

impl crate::services::McatService for Collection {
    fn mastery_query(
        &mut self,
        input: anki_proto::mcat::MasteryQueryRequest,
    ) -> error::Result<anki_proto::mcat::MasteryQueryResponse> {
        self.mastery_query(&input.search, input.min_reviews)
    }

    fn record_practice_result(
        &mut self,
        input: anki_proto::mcat::RecordPracticeResultRequest,
    ) -> error::Result<()> {
        let results: Vec<(String, u32, u32)> = input
            .topic_results
            .into_iter()
            .map(|r| (r.topic, r.correct, r.answered))
            .collect();
        self.add_practice_result(&results)?;
        Ok(())
    }

    fn performance_query(
        &mut self,
        input: anki_proto::mcat::PerformanceQueryRequest,
    ) -> error::Result<anki_proto::mcat::PerformanceQueryResponse> {
        self.compute_performance(input.min_questions)
    }
}
