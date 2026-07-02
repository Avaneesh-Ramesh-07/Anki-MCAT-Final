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
        // Unspecified is treated as topical for backwards compatibility.
        if input.exam_kind == anki_proto::mcat::ExamKind::FullLength as i32 {
            self.add_full_length_result(&input.exam_id, &input.test_id, &results)?;
        } else {
            self.add_topical_result(&input.exam_id, &input.test_id, &results)?;
        }
        Ok(())
    }

    fn performance_query(
        &mut self,
        input: anki_proto::mcat::PerformanceQueryRequest,
    ) -> error::Result<anki_proto::mcat::PerformanceQueryResponse> {
        self.compute_performance(input.min_questions)
    }

    fn readiness_query(
        &mut self,
        input: anki_proto::mcat::ReadinessQueryRequest,
    ) -> error::Result<anki_proto::mcat::ReadinessQueryResponse> {
        self.readiness_query(&input.search, input.min_reviews, input.min_questions)
    }
}
