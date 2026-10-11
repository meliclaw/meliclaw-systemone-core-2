//! Remote decision models answered by OpenRouter's alpha Decisions API, listed and served
//! alongside local ones (`docs/api.md` §15, `OPENROUTER_API_KEY`).
//!
//! OpenRouter already returns calibrated, typed answers, so these models skip the scheduler and
//! the `Store` entirely: [`OpenRouterClient::decide`] turns its reply directly into
//! [`ollaya_decision::Answer`]s in the same option order a local model's calibration would.

use std::time::Duration;

use ollaya_decision::{Answer, Criteria, Questions};
use serde_json::Value;

use crate::Error;

pub const OPENROUTER_DECISIONS_URL: &str = "https://openrouter.ai/api/alpha/decisions";

#[derive(Debug, Clone, Copy)]
pub struct RemoteModel {
    /// The name ollaya lists and accepts, Ollama-style (`name:tag`).
    pub name: &'static str,
    /// The model id sent to OpenRouter.
    pub openrouter_id: &'static str,
    pub family: &'static str,
    pub parameter_size: &'static str,
    pub description: &'static str,
}

pub const REMOTE_MODELS: &[RemoteModel] = &[
    RemoteModel {
        name: "meliclaw-decision-pplx:27b",
        openrouter_id: "perplexity/pplx-decider-v1.1-27b",
        family: "pplx-decider",
        parameter_size: "27B",
        description: "Meliclaw Decision-pplx-27B (Perplexity pplx-decider-v1.1-27B, via OpenRouter)",
    },
    RemoteModel {
        name: "meliclaw-decision-msd:27b",
        openrouter_id: "microsoft/microsoft-decision-1",
        family: "microsoft-decision-1",
        parameter_size: "27B",
        description: "Meliclaw Decision-msd-27B (Microsoft Decision-1, via OpenRouter)",
    },
    RemoteModel {
        name: "meliclaw-decision-ld1:27b",
        openrouter_id: "liquid/d1",
        family: "liquid-d1",
        parameter_size: "27B",
        description: "Meliclaw Decision-Ld1-27B (Liquid d1, via OpenRouter)",
    },
];

/// Case-insensitive lookup by the name ollaya exposes it under, with or without `:tag`.
pub fn lookup(requested: &str) -> Option<&'static RemoteModel> {
    let requested = requested.trim();
    REMOTE_MODELS.iter().find(|m| {
        m.name.eq_ignore_ascii_case(requested)
            || m.name
                .split(':')
                .next()
                .is_some_and(|base| base.eq_ignore_ascii_case(requested))
    })
}

pub struct OpenRouterClient {
    api_key: String,
    http: reqwest::Client,
}

impl OpenRouterClient {
    pub fn new(api_key: String) -> Self {
        OpenRouterClient {
            api_key,
            http: reqwest::Client::builder()
                .timeout(Duration::from_secs(120))
                .build()
                .expect("reqwest client builds"),
        }
    }
}

impl OpenRouterClient {
    /// Answer `questions` about `state` through OpenRouter's Decisions API.
    pub async fn decide(
        &self,
        openrouter_id: &str,
        state: &Value,
        questions: &Questions,
        questions_json: &Value,
    ) -> Result<Vec<Answer>, Error> {
        let body = serde_json::json!({
            "model": openrouter_id,
            "state": state,
            "questions": questions_json,
        });
        let resp = self
            .http
            .post(OPENROUTER_DECISIONS_URL)
            .bearer_auth(&self.api_key)
            .json(&body)
            .send()
            .await
            .map_err(|e| Error::Runner(format!("openrouter: {e}")))?;
        let status = resp.status();
        let body: Value = resp
            .json()
            .await
            .map_err(|e| Error::Runner(format!("openrouter: malformed response: {e}")))?;
        if !status.is_success() {
            let message = body["error"]["message"]
                .as_str()
                .unwrap_or("openrouter error")
                .to_owned();
            return if status.is_client_error() {
                Err(Error::InvalidRequest(format!("openrouter: {message}")))
            } else {
                Err(Error::Runner(format!("openrouter: {message}")))
            };
        }
        answers_from_openrouter(questions, &body["answers"])
    }
}

/// Convert OpenRouter's typed `answers` object into [`Answer`]s with option-ordered probabilities,
/// so `Answer::to_typesafe`/`to_laya` render the same whether a local or a remote model answered.
fn answers_from_openrouter(questions: &Questions, answers: &Value) -> Result<Vec<Answer>, Error> {
    questions
        .iter()
        .map(|(qid, q)| {
            let a = &answers[qid];
            if a.is_null() {
                return Err(Error::Runner(format!(
                    "openrouter: no answer for question {qid:?}"
                )));
            }
            let probabilities = match &q.criteria {
                Criteria::Noul { .. } => {
                    let p = a["noul"].as_f64().ok_or_else(|| {
                        Error::Runner(format!("openrouter: question {qid:?}: missing noul"))
                    })?;
                    vec![1.0 - p, p]
                }
                Criteria::Choice(options) => {
                    let probs = &a["probabilities"];
                    options
                        .keys()
                        .map(|k| {
                            probs[k].as_f64().ok_or_else(|| {
                                Error::Runner(format!(
                                    "openrouter: question {qid:?}: missing probability for {k:?}"
                                ))
                            })
                        })
                        .collect::<Result<Vec<_>, _>>()?
                }
                Criteria::Score(levels) => {
                    let probs = &a["probabilities"];
                    (0..levels.len())
                        .map(|i| {
                            probs[i.to_string()].as_f64().ok_or_else(|| {
                                Error::Runner(format!(
                                    "openrouter: question {qid:?}: missing probability for level {i}"
                                ))
                            })
                        })
                        .collect::<Result<Vec<_>, _>>()?
                }
            };
            Ok(Answer {
                qtype: q.qtype,
                probabilities,
                act_probability: None,
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn looks_up_by_full_or_bare_name() {
        assert!(lookup("meliclaw-decision-pplx:27b").is_some());
        assert!(lookup("meliclaw-decision-pplx").is_some());
        assert!(lookup("MELICLAW-DECISION-MSD:27B").is_some());
        assert!(lookup("laya").is_none());
    }

    #[test]
    fn converts_noul_choice_and_score_answers() {
        let questions = ollaya_decision::parse_questions(&serde_json::json!({
            "is_urgent": {"type": "noul", "instructions": "urgent?", "criteria": {"true": "yes", "false": "no"}},
            "department": {"type": "choice", "instructions": "team?", "criteria": {"billing": "x", "technical": "y"}},
            "frustration": {"type": "score", "instructions": "level?", "criteria": ["Calm", "Angry"]},
        }))
        .unwrap();
        let answers = serde_json::json!({
            "is_urgent": {"noul": 0.9},
            "department": {"choice": "billing", "probabilities": {"billing": 0.7, "technical": 0.3}},
            "frustration": {"score": 1.0, "probabilities": {"0": 0.2, "1": 0.8}},
        });
        let out = answers_from_openrouter(&questions, &answers).unwrap();
        let close = |a: &[f64], b: &[f64]| {
            a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() < 1e-9)
        };
        assert!(close(&out[0].probabilities, &[0.1, 0.9]));
        assert!(close(&out[1].probabilities, &[0.7, 0.3]));
        assert!(close(&out[2].probabilities, &[0.2, 0.8]));
    }
}
