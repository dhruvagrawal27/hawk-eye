//! Alert/severity types + thresholds shared by the rules gateway (BACKEND-10/11).

use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

/// Only surface triage-worthy alerts (matches the Python `EMIT_THRESHOLD`).
pub const EMIT_THRESHOLD: u8 = 70;
/// High-value payment threshold for NEW_BENEFICIARY_THEN_HIGHVALUE (₹10 lakh).
pub const HIGH_VALUE_INR: i64 = 1_000_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    Low,
    Medium,
    High,
}

impl Default for Severity {
    fn default() -> Self {
        Severity::Low
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReasonCode {
    pub source: String,
    pub code: Option<String>,
    pub detail: Option<String>,
}

impl ReasonCode {
    pub fn rule(code: &str, detail: &str) -> Self {
        ReasonCode { source: "rule".into(), code: Some(code.into()), detail: Some(detail.into()) }
    }
    pub fn shap(feature: &str, detail: &str) -> Self {
        ReasonCode { source: "shap".into(), code: Some(feature.into()), detail: Some(detail.into()) }
    }
    pub fn graph(detail: &str) -> Self {
        ReasonCode { source: "graph".into(), code: None, detail: Some(detail.into()) }
    }
}

/// L6 alert (mirrors `BACKEND.md` §2 — the fields the gateway emits to the alerts topic).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Alert {
    pub alert_id: String,
    pub entity_id: String,
    pub risk_score: u8,
    pub severity: Severity,
    pub confidence: f64,
    pub contributing_layers: Vec<String>,
    pub reason_codes: Vec<ReasonCode>,
    pub exposure_inr: i64,
    pub pii_tokenized: bool,
}

/// Deterministic alert id from the event id (`alr_xxxxxx`).
pub fn alert_id_for(event_id: &str) -> String {
    let mut h = DefaultHasher::new();
    event_id.hash(&mut h);
    format!("alr_{:06x}", (h.finish() as u32) & 0x00ff_ffff)
}
