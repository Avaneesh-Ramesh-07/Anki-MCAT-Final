// Copyright: Ankitects Pty Ltd and contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

//! The free-response AI grader (Backend service).
//!
//! Grades one free-response practice answer against its rubric by calling an
//! external LLM (OpenAI's chat-completions API). This lives on `Backend` (not
//! an open `Collection`) because it needs network + the `OPENAI_API_KEY` env
//! var, reusing the backend's shared reqwest client and tokio runtime (same
//! pattern as `backend/github.rs`).
//!
//! Two invariants matter for trust:
//! - The grader receives ONLY the prompt, the rubric, and the student's answer.
//!   It is never given the reference/ground-truth answer, so it grades purely
//!   from the (human-authored) rubric.
//! - It never returns a hard error for a missing key or a network failure —
//!   instead it returns `graded=false` with a reason, so the caller degrades
//!   gracefully (shows the reference answer, records no score).

use std::time::Duration;

use anki_proto::mcat::CriterionResult;
use anki_proto::mcat::GradeFreeResponseRequest;
use anki_proto::mcat::GradeFreeResponseResponse;
use reqwest::Client;
use serde::Deserialize;
use serde_json::json;

use super::Backend;
use crate::prelude::*;
use crate::services::BackendMcatService;

const OPENAI_URL: &str = "https://api.openai.com/v1/chat/completions";
const DEFAULT_MODEL: &str = "gpt-4o-mini";

const SYSTEM_PROMPT: &str = "You are a strict, fair exam grader with NO subject \
knowledge beyond the rubric you are given. Grade the student's answer using ONLY \
the rubric criteria below. For each criterion, award an integer number of points \
from 0 up to that criterion's maximum, based solely on whether the answer \
expresses the criterion's required concepts. If any of a criterion's listed \
disqualifiers applies to the answer, award 0 for that criterion. Do not invent \
criteria, do not use outside knowledge, and do not reward correct-sounding \
statements that the rubric does not credit. Respond with ONLY the JSON object \
described by the user, and nothing else.";

impl BackendMcatService for Backend {
    fn grade_free_response(
        &self,
        input: GradeFreeResponseRequest,
    ) -> Result<GradeFreeResponseResponse> {
        let key = match std::env::var("OPENAI_API_KEY") {
            Ok(k) if !k.trim().is_empty() => k,
            _ => return Ok(ungraded(&input, "OPENAI_API_KEY not set")),
        };
        let base = env_nonempty("OPENAI_BASE_URL").unwrap_or_else(|| OPENAI_URL.to_string());
        let model = if !input.model.is_empty() {
            input.model.clone()
        } else {
            env_nonempty("OPENAI_GRADER_MODEL").unwrap_or_else(|| DEFAULT_MODEL.to_string())
        };

        let client = self.web_client();
        let outcome = self
            .runtime_handle()
            .block_on(grade_via_openai(client, base, key, model, &input));
        Ok(match outcome {
            Ok(resp) => resp,
            Err(msg) => ungraded(&input, &format!("grading failed: {msg}")),
        })
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key).ok().filter(|s| !s.trim().is_empty())
}

/// Build the "couldn't grade" response (graceful degradation).
fn ungraded(input: &GradeFreeResponseRequest, error: &str) -> GradeFreeResponseResponse {
    GradeFreeResponseResponse {
        graded: false,
        error: error.to_string(),
        points_awarded: 0,
        max_points: input.max_points,
        criteria: Vec::new(),
        feedback: String::new(),
    }
}

// ---- OpenAI request/response shapes (only the fields we use) --------------

#[derive(Deserialize)]
struct ChatResponse {
    choices: Vec<Choice>,
}
#[derive(Deserialize)]
struct Choice {
    message: ChatMessage,
}
#[derive(Deserialize)]
struct ChatMessage {
    content: String,
}

/// The grader's own JSON output (inside the chat message content).
#[derive(Deserialize)]
struct GraderOutput {
    #[serde(default)]
    criteria: Vec<CritOut>,
    #[serde(default)]
    feedback: String,
}
#[derive(Deserialize)]
struct CritOut {
    #[serde(default)]
    id: String,
    // i64 so an out-of-range model answer is tolerated, then clamped.
    #[serde(default)]
    points_awarded: i64,
    #[serde(default)]
    rationale: String,
}

async fn grade_via_openai(
    client: Client,
    base_url: String,
    api_key: String,
    model: String,
    input: &GradeFreeResponseRequest,
) -> std::result::Result<GradeFreeResponseResponse, String> {
    let body = json!({
        "model": model,
        "temperature": 0,
        "seed": 7,
        "response_format": { "type": "json_object" },
        "messages": [
            { "role": "system", "content": SYSTEM_PROMPT },
            { "role": "user", "content": build_user_message(input) },
        ],
    });
    let response = client
        .post(&base_url)
        .bearer_auth(&api_key)
        .timeout(Duration::from_secs(60))
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?;
    let chat: ChatResponse = response.json().await.map_err(|e| e.to_string())?;
    let content = chat
        .choices
        .into_iter()
        .next()
        .ok_or_else(|| "no choices in grader response".to_string())?
        .message
        .content;
    let parsed: GraderOutput =
        serde_json::from_str(&content).map_err(|e| format!("bad grader JSON: {e}"))?;
    Ok(assemble_response(input, parsed))
}

/// Render the prompt + rubric + student answer into the grader's user message.
fn build_user_message(input: &GradeFreeResponseRequest) -> String {
    let mut s = String::new();
    s.push_str("QUESTION PROMPT:\n");
    s.push_str(&input.prompt);
    s.push_str("\n\nSTUDENT ANSWER:\n");
    s.push_str(if input.answer.trim().is_empty() {
        "(no answer given)"
    } else {
        &input.answer
    });
    s.push_str("\n\nRUBRIC — award each criterion independently:\n");
    for c in &input.rubric {
        s.push_str(&format!(
            "- id={} (max {} points): {}\n",
            c.id, c.points, c.description
        ));
        if !c.required_concepts.is_empty() {
            s.push_str(&format!(
                "    required concepts (award only if the answer expresses these): {}\n",
                c.required_concepts.join("; ")
            ));
        }
        if !c.disqualifiers.is_empty() {
            s.push_str(&format!(
                "    disqualifiers (award 0 for this criterion if any apply): {}\n",
                c.disqualifiers.join("; ")
            ));
        }
    }
    s.push_str(&format!(
        "\nReturn ONLY this JSON object: {{\"criteria\":[{{\"id\":<string>,\
\"points_awarded\":<integer>,\"rationale\":<string>}}],\"feedback\":<string>}}. \
Include one entry per rubric id, award an integer in [0, that criterion's max], \
and keep the total within {} points.",
        input.max_points
    ));
    s
}

/// Map the grader's raw output onto the rubric: clamp each award to its
/// criterion max, sum, and clamp the total to `max_points`. Missing criteria
/// score 0.
fn assemble_response(
    input: &GradeFreeResponseRequest,
    out: GraderOutput,
) -> GradeFreeResponseResponse {
    let mut criteria = Vec::with_capacity(input.rubric.len());
    let mut total: u32 = 0;
    for rc in &input.rubric {
        let matched = out.criteria.iter().find(|c| c.id == rc.id);
        let awarded = matched
            .map(|c| c.points_awarded.clamp(0, i64::from(rc.points)) as u32)
            .unwrap_or(0);
        let rationale = matched.map(|c| c.rationale.clone()).unwrap_or_default();
        total += awarded;
        criteria.push(CriterionResult {
            id: rc.id.clone(),
            points_awarded: awarded,
            points_possible: rc.points,
            met: rc.points > 0 && awarded == rc.points,
            rationale,
        });
    }
    GradeFreeResponseResponse {
        graded: true,
        error: String::new(),
        points_awarded: total.min(input.max_points),
        max_points: input.max_points,
        criteria,
        feedback: out.feedback,
    }
}

#[cfg(test)]
mod test {
    use anki_proto::mcat::RubricCriterion;

    use super::*;

    fn crit(id: &str, points: u32) -> RubricCriterion {
        RubricCriterion {
            id: id.to_string(),
            description: format!("criterion {id}"),
            points,
            required_concepts: vec![],
            disqualifiers: vec![],
        }
    }
    fn req() -> GradeFreeResponseRequest {
        GradeFreeResponseRequest {
            prompt: "p".into(),
            answer: "a".into(),
            max_points: 4,
            rubric: vec![crit("c1", 2), crit("c2", 2)],
            model: String::new(),
        }
    }

    #[test]
    fn ungraded_reports_reason_and_zero() {
        let r = ungraded(&req(), "OPENAI_API_KEY not set");
        assert!(!r.graded);
        assert_eq!(r.error, "OPENAI_API_KEY not set");
        assert_eq!(r.points_awarded, 0);
        assert_eq!(r.max_points, 4);
        assert!(r.criteria.is_empty());
    }

    #[test]
    fn assemble_clamps_and_sums() {
        // c1 over its max (5 -> 2), c2 negative (-1 -> 0), and an unknown id ignored.
        let out = GraderOutput {
            criteria: vec![
                CritOut {
                    id: "c1".into(),
                    points_awarded: 5,
                    rationale: "ok".into(),
                },
                CritOut {
                    id: "c2".into(),
                    points_awarded: -1,
                    rationale: "no".into(),
                },
                CritOut {
                    id: "ghost".into(),
                    points_awarded: 9,
                    rationale: "x".into(),
                },
            ],
            feedback: "fb".into(),
        };
        let r = assemble_response(&req(), out);
        assert!(r.graded);
        assert_eq!(r.points_awarded, 2); // 2 + 0
        assert_eq!(r.criteria.len(), 2);
        assert_eq!(r.criteria[0].points_awarded, 2);
        assert!(r.criteria[0].met);
        assert_eq!(r.criteria[1].points_awarded, 0);
        assert!(!r.criteria[1].met);
        assert_eq!(r.feedback, "fb");
    }

    #[test]
    fn assemble_total_clamped_to_max_points() {
        let mut input = req();
        input.max_points = 3; // less than sum of rubric maxes (4)
        let out = GraderOutput {
            criteria: vec![
                CritOut {
                    id: "c1".into(),
                    points_awarded: 2,
                    rationale: String::new(),
                },
                CritOut {
                    id: "c2".into(),
                    points_awarded: 2,
                    rationale: String::new(),
                },
            ],
            feedback: String::new(),
        };
        let r = assemble_response(&input, out);
        assert_eq!(r.points_awarded, 3); // 4 clamped to max_points 3
    }
}
