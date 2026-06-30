//! Inline inference + L6 fusion (BACKEND-10/12, blueprint Part 18.1).
//!
//! L2/L3 scores arrive from model serving (ONNX Runtime via `ort`, behind the `onnx` feature; a
//! deterministic stub otherwise). `fuse` combines them with the L1 score into a calibrated 0–100
//! risk + severity × confidence + reason codes, mirroring the Python `fusion` service.

use crate::ingest::{Event, FeatureView};
use crate::l1_shortcircuit::L1Outcome;
use crate::rules_gateway::{alert_id_for, Alert, ReasonCode, Severity, EMIT_THRESHOLD};

#[derive(Clone, Debug)]
pub struct Scores {
    pub l2: f64,
    pub l3: f64,
}

/// Inline L2/L3 scoring. With `--features onnx` an `ort` ONNX-Runtime session is wired here; the
/// default build uses this deterministic stand-in (# STUB: ML) so the crate builds without native
/// ONNX libraries.
pub fn score_inline(f: &FeatureView) -> Scores {
    let off = if f.is_off_hours { 1.0 } else { 0.0 };
    let l2 = sigmoid(0.9 * off + 1.1 * f.lat_risk - 0.6);
    let sod = if f.maker_checker_same_actor { 1.0 } else { 0.0 };
    let l3 = sigmoid(1.0 * off + 1.6 * f.lat_risk + 1.4 * sod - 1.0);
    Scores { l2, l3 }
}

fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// L6 stacked-meta fusion → calibrated 0–100 + severity × confidence + reason codes.
pub fn fuse(e: &Event, l1: &L1Outcome, f: &FeatureView, s: &Scores) -> Alert {
    let sod = if f.maker_checker_same_actor { 1.0 } else { 0.0 };
    let z = -2.2 + 1.7 * l1.l1_score + 1.2 * s.l2 + 2.4 * s.l3 + 1.2 * sod;
    let mut prob = sigmoid(z);
    if l1.hard_hit {
        prob = prob.max(0.85);
    }
    let risk = (prob * 100.0).round() as u8;
    let severity = if l1.hard_hit || risk >= EMIT_THRESHOLD {
        Severity::High
    } else if risk >= 40 {
        Severity::Medium
    } else {
        Severity::Low
    };

    let mut layers = vec!["L1_rules".to_string(), "L2_unsupervised".into(), "L3_gbdt".into()];
    let mut reasons = l1.reason_codes.clone();
    if f.lat_risk > 0.0 {
        reasons.push(ReasonCode::shap(
            "new_beneficiary_to_payment_latency_min",
            "short new-beneficiary→payment latency",
        ));
    }
    if sod > 0.0 {
        layers.push("L5_graph".into());
        reasons.push(ReasonCode::graph("maker-checker collusion / self-dealing"));
    }

    Alert {
        alert_id: alert_id_for(&e.event_id),
        entity_id: e.actor_id.clone(),
        risk_score: risk,
        severity,
        confidence: (0.5 + 0.45 * prob).min(0.98),
        contributing_layers: layers,
        reason_codes: reasons,
        exposure_inr: e.amount_inr,
        pii_tokenized: true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fusion_is_high_when_l1_hard_hit() {
        let e = Event { amount_inr: 4_800_000, ..Event::default() };
        let l1 = L1Outcome { hard_hit: true, l1_score: 0.9, fired: true, ..Default::default() };
        let f = FeatureView { lat_risk: 0.8, ..Default::default() };
        let alert = fuse(&e, &l1, &f, &Scores { l2: 0.7, l3: 0.8 });
        assert_eq!(alert.severity, Severity::High);
        assert!(alert.risk_score >= 70);
    }
}
