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
//! - It never returns a hard error. When AI grading is toggled off (the
//!   Home-page switch), no API key is set, or the model call fails, it falls
//!   back to a deterministic KEYWORD MATCH against the rubric's
//!   ground-truth-derived `keywords`, so the caller always gets a usable grade.

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
const DEFAULT_MODEL: &str = "gpt-4.1";
/// Collection-config key for the Home-page "AI grading" toggle (default on).
const AI_GRADING_CONFIG_KEY: &str = "mcatAiGrading";

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
        // Home-page "AI grading" toggle (collection config; default on). When
        // it's off — or no API key is configured — grade by keyword match
        // against the ground-truth-derived rubric keywords instead of the model.
        let ai_enabled: bool = self
            .with_col(|col| Ok(col.get_config_optional(AI_GRADING_CONFIG_KEY)))
            .ok()
            .flatten()
            .unwrap_or(true);
        let key = std::env::var("OPENAI_API_KEY")
            .ok()
            .filter(|k| !k.trim().is_empty());
        if !ai_enabled || key.is_none() {
            return Ok(keyword_grade(&input));
        }
        let key = key.unwrap();
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
            // On any AI failure, fall back to keyword grading (a real result)
            // rather than leaving the student ungraded.
            Err(_) => keyword_grade(&input),
        })
    }
}

fn env_nonempty(key: &str) -> Option<String> {
    std::env::var(key).ok().filter(|s| !s.trim().is_empty())
}

/// Deterministic, offline grader used when AI grading is off / unavailable.
/// Awards a criterion its full points when the student's answer contains ANY of
/// its ground-truth-derived `keywords` (falling back to `required_concepts`
/// when no keywords were authored) and no `disqualifier` phrase is present.
/// Reuses [`assemble_response`] for clamping/summing, so the output shape is
/// identical to the AI path. Never errors.
fn keyword_grade(input: &GradeFreeResponseRequest) -> GradeFreeResponseResponse {
    let answer = normalize(&input.answer);
    let mut met = 0u32;
    let criteria = input
        .rubric
        .iter()
        .map(|rc| {
            let disqualified = rc.disqualifiers.iter().any(|d| contains_phrase(&answer, d));
            let terms = if rc.keywords.is_empty() {
                &rc.required_concepts
            } else {
                &rc.keywords
            };
            let hits = terms.iter().filter(|t| contains_phrase(&answer, t)).count();
            let matched = !disqualified && hits > 0;
            if matched {
                met += 1;
            }
            let rationale = if disqualified {
                "Keyword match: a disqualifying statement was detected.".to_string()
            } else if matched {
                format!("Keyword match: found {hits} expected key term(s).")
            } else {
                "Keyword match: expected key terms were not found.".to_string()
            };
            CritOut {
                id: rc.id.clone(),
                points_awarded: if matched { i64::from(rc.points) } else { 0 },
                rationale,
            }
        })
        .collect();
    let feedback = format!(
        "Keyword match — {met} of {} criteria met. AI grading is off, so this is a \
         rough offline check against the rubric's key terms.",
        input.rubric.len()
    );
    assemble_response(input, GraderOutput { criteria, feedback })
}

/// Lowercase and reduce to single-spaced alphanumeric tokens for matching.
fn normalize(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut prev_space = true;
    for c in s.chars() {
        if c.is_alphanumeric() {
            out.extend(c.to_lowercase());
            prev_space = false;
        } else if !prev_space {
            out.push(' ');
            prev_space = true;
        }
    }
    out.trim().to_string()
}

/// Whether the normalized answer contains `term` as a whole-word (phrase)
/// match. Both sides are space-padded so a token can't match inside a longer
/// word (e.g. "ion" must not hit "cation").
fn contains_phrase(answer_norm: &str, term: &str) -> bool {
    let t = normalize(term);
    if t.is_empty() {
        return false;
    }
    format!(" {answer_norm} ").contains(&format!(" {t} "))
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
            keywords: vec![],
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
    fn keyword_grade_matches_and_disqualifies() {
        let mut input = req();
        input.rubric = vec![
            RubricCriterion {
                keywords: vec!["nonreducing ends".into()],
                ..crit("c1", 2)
            },
            RubricCriterion {
                keywords: vec!["phosphorylase".into()],
                disqualifiers: vec!["insoluble".into()],
                ..crit("c2", 2)
            },
        ];
        input.answer = "Branching creates many nonreducing ends; phosphorylase acts \
            there, but glycogen is insoluble."
            .into();
        let r = keyword_grade(&input);
        assert!(r.graded);
        assert_eq!(r.criteria[0].points_awarded, 2); // matched "nonreducing ends"
        assert!(r.criteria[0].met);
        assert_eq!(r.criteria[1].points_awarded, 0); // disqualified by "insoluble"
        assert!(!r.criteria[1].met);
        assert_eq!(r.points_awarded, 2);
    }

    #[test]
    fn keyword_grade_empty_answer_scores_zero() {
        let mut input = req();
        input.rubric = vec![RubricCriterion {
            keywords: vec!["mitochondria".into()],
            ..crit("c1", 2)
        }];
        input.answer = String::new();
        let r = keyword_grade(&input);
        assert!(r.graded);
        assert_eq!(r.points_awarded, 0);
        assert!(!r.criteria[0].met);
    }

    #[test]
    fn keyword_grade_no_partial_word_match() {
        // "ion" must not match inside "cation".
        let mut input = req();
        input.rubric = vec![RubricCriterion {
            keywords: vec!["ion".into()],
            ..crit("c1", 2)
        }];
        input.answer = "the cation moved".into();
        assert_eq!(keyword_grade(&input).criteria[0].points_awarded, 0);
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
