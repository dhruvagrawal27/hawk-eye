//! L1 rules gateway + hard-hit short-circuit (BACKEND-11, blueprint Part 18.1 l.566).
//!
//! On a hard rule hit the gateway emits a HIGH alert immediately, **without invoking model
//! serving**. The named hard rules mirror the Python engine (`rules_engine`).

use crate::ingest::{Event, FeatureView};
use crate::rules_gateway::{alert_id_for, Alert, ReasonCode, Severity, HIGH_VALUE_INR};

#[derive(Clone, Debug, Default)]
pub struct L1Outcome {
    pub fired: bool,
    pub hard_hit: bool,
    pub l1_score: f64,
    pub severity: Severity,
    pub reason_codes: Vec<ReasonCode>,
}

const PAYMENT_VERBS: &[&str] = &["approve_payment", "payment", "transfer"];

/// Evaluate the L1 named rules deterministically.
pub fn evaluate_l1(e: &Event, f: &FeatureView) -> L1Outcome {
    let mut out = L1Outcome::default();
    let mut score: f64 = 0.0;

    // NEW_BENEFICIARY_THEN_HIGHVALUE (hard).
    if PAYMENT_VERBS.contains(&e.verb.as_str())
        && e.amount_inr >= HIGH_VALUE_INR
        && f.new_beneficiary_minutes.map(|m| m <= 60.0).unwrap_or(false)
    {
        out.hard_hit = true;
        score = score.max(0.9);
        out.reason_codes.push(ReasonCode::rule(
            "NEW_BENEFICIARY_THEN_HIGHVALUE",
            "new payee paid a high value within a short latency window",
        ));
    }

    // DB_WRITE_WITHOUT_APP_TXN (hard).
    if (e.channel == "db" || e.channel == "database") && !e.app_txn_present {
        out.hard_hit = true;
        score = score.max(0.92);
        out.reason_codes.push(ReasonCode::rule(
            "DB_WRITE_WITHOUT_APP_TXN",
            "direct DB write with no matching application transaction",
        ));
    }

    // SoD: same actor as maker AND checker (hard).
    if f.maker_checker_same_actor {
        out.hard_hit = true;
        score = score.max(0.95);
        out.reason_codes.push(ReasonCode::rule(
            "SOD_MAKER_CHECKER_SAME_ACTOR",
            "same actor acted as both maker and checker",
        ));
    }

    // OFF_HOURS_ACTIVITY (soft).
    if e.is_off_hours {
        score = score.max(0.4);
        out.reason_codes.push(ReasonCode::rule(
            "OFF_HOURS_ACTIVITY",
            "activity outside actor & peer baseline hours",
        ));
    }

    out.fired = !out.reason_codes.is_empty();
    out.l1_score = score;
    out.severity = if out.hard_hit { Severity::High } else { Severity::Medium };
    out
}

/// Emit a HIGH alert on the short-circuit path (no ML invoked).
pub fn emit_high(e: &Event, l1: &L1Outcome) -> Alert {
    let risk = ((l1.l1_score * 100.0) as u8).max(85);
    Alert {
        alert_id: alert_id_for(&e.event_id),
        entity_id: e.actor_id.clone(),
        risk_score: risk,
        severity: Severity::High,
        confidence: (0.6 + 0.35 * l1.l1_score).min(0.95),
        contributing_layers: vec!["L1_rules".into()],
        reason_codes: l1.reason_codes.clone(),
        exposure_inr: e.amount_inr,
        pii_tokenized: true,
    }
}

/// Emit an L1-only alert on the degraded path (model server down).
pub fn emit_degraded(e: &Event, l1: &L1Outcome) -> Alert {
    let risk = ((l1.l1_score * 100.0) as u8).max(1);
    Alert {
        alert_id: alert_id_for(&e.event_id),
        entity_id: e.actor_id.clone(),
        risk_score: risk,
        severity: l1.severity,
        confidence: (0.5 + 0.3 * l1.l1_score).min(0.9),
        contributing_layers: vec!["L1_rules".into()],
        reason_codes: l1.reason_codes.clone(),
        exposure_inr: e.amount_inr,
        pii_tokenized: true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::features;

    #[test]
    fn new_beneficiary_highvalue_is_hard_hit() {
        let e = Event {
            verb: "approve_payment".into(),
            amount_inr: 4_800_000,
            new_beneficiary_minutes: Some(19.0),
            ..Event::default()
        };
        let f = features::assemble(&e);
        let l1 = evaluate_l1(&e, &f);
        assert!(l1.hard_hit);
        assert_eq!(l1.severity, Severity::High);
    }

    #[test]
    fn off_hours_alone_is_soft() {
        let e = Event { verb: "login".into(), is_off_hours: true, ..Event::default() };
        let f = features::assemble(&e);
        let l1 = evaluate_l1(&e, &f);
        assert!(l1.fired);
        assert!(!l1.hard_hit);
    }
}
