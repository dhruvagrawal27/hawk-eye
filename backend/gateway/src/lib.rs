//! Hawk-Eye Rust hot-path gateway (BACKEND-10, blueprint Part 8 / 18.1).
//!
//! The latency-critical tier of the online path. Mirrors the Python reference orchestrator
//! (`app/pipeline/online.py`) so the two stay contract-compatible against `BACKEND.md`:
//!
//! ```text
//! event ─▶ ingest/enrich ─▶ feature read (Redis/Feast) ─▶ L1 rules gateway
//!            │                                                   │ hard hit? ──▶ L1 short-circuit: emit HIGH, skip ML
//!            │                                                   ▼ no hard hit
//!            │                                          model serving (L2+L3 inline)
//!            │                                                   ▼
//!            │                                          L6 fusion ─▶ emit alert
//!            └─ idempotency / circuit-breaker / graceful degradation throughout
//! ```
//!
//! ALERT-ONLY: this gateway emits alerts; it never blocks money and never classifies fraud.

pub mod degradation;
pub mod features;
pub mod idempotency;
pub mod inference;
pub mod ingest;
pub mod l1_shortcircuit;
pub mod reliability;
pub mod rules_gateway;

pub use degradation::{DegradationController, Mode};
pub use idempotency::IdempotencyStore;
pub use ingest::{Event, FeatureView};
pub use l1_shortcircuit::{evaluate_l1, L1Outcome};
pub use rules_gateway::{Alert, Severity};

/// End-to-end processing of one event through the hot path.
///
/// Returns `Some(alert)` when an alert is emitted, or `None` on a deduplicated replay or a
/// below-threshold score. The `score_fn` is the inline model-serving call (L2+L3); when it returns
/// `None` the path degrades to L1-rules-only and marks the event for re-scoring.
pub fn process<F>(
    event: &Event,
    dedupe: &IdempotencyStore,
    degradation: &DegradationController,
    score_fn: F,
) -> Option<Alert>
where
    F: FnOnce(&FeatureView) -> Option<inference::Scores>,
{
    // Exactly-once: a replayed event_id never double-alerts (BACKEND-14).
    if !dedupe.mark(&event.event_id) {
        return None;
    }

    let features = features::assemble(event);
    let l1 = evaluate_l1(event, &features);

    // L1 hard-hit short-circuit: emit HIGH immediately, skip ML (BACKEND-11).
    if l1.hard_hit {
        return Some(l1_shortcircuit::emit_high(event, &l1));
    }

    match score_fn(&features) {
        Some(scores) => {
            let alert = inference::fuse(event, &l1, &features, &scores);
            if alert.risk_score >= rules_gateway::EMIT_THRESHOLD || l1.fired {
                Some(alert)
            } else {
                None // recorded to ClickHouse, not surfaced
            }
        }
        None => {
            // Graceful degradation to L1-rules-only; never go dark (BACKEND-15).
            degradation.enter_degraded();
            degradation.mark_for_rescore(&event.event_id);
            if l1.fired {
                Some(l1_shortcircuit::emit_degraded(event, &l1))
            } else {
                None
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn burst_event() -> Event {
        Event {
            event_id: "evt_test_1".into(),
            actor_id: "EMP-7f3a".into(),
            verb: "approve_payment".into(),
            channel: "cbs".into(),
            amount_inr: 4_800_000,
            is_off_hours: true,
            new_beneficiary_minutes: Some(19.0),
            maker_checker_same_actor: false,
            app_txn_present: true,
        }
    }

    #[test]
    fn hard_hit_short_circuits_and_skips_ml() {
        let dedupe = IdempotencyStore::new();
        let degr = DegradationController::new();
        let mut ml_called = false;
        let alert = process(&burst_event(), &dedupe, &degr, |_| {
            ml_called = true;
            Some(inference::Scores { l2: 0.7, l3: 0.8 })
        });
        assert!(alert.is_some());
        assert_eq!(alert.unwrap().severity, Severity::High);
        assert!(!ml_called, "hard-hit must skip model serving (L1 short-circuit)");
    }

    #[test]
    fn replay_does_not_double_alert() {
        let dedupe = IdempotencyStore::new();
        let degr = DegradationController::new();
        let first = process(&burst_event(), &dedupe, &degr, |_| Some(inference::Scores { l2: 0.1, l3: 0.1 }));
        let replay = process(&burst_event(), &dedupe, &degr, |_| Some(inference::Scores { l2: 0.1, l3: 0.1 }));
        assert!(first.is_some());
        assert!(replay.is_none(), "replayed event_id must not double-alert");
    }

    #[test]
    fn degrades_to_l1_when_serving_down() {
        // A hard-hit short-circuits before serving is consulted, so use a soft (off-hours) event.
        let soft = Event {
            verb: "login".into(),
            amount_inr: 0,
            new_beneficiary_minutes: None,
            ..burst_event()
        };
        let dedupe = IdempotencyStore::new();
        let degr = DegradationController::new();
        let alert = process(&soft, &dedupe, &degr, |_| None); // serving down → None
        assert!(alert.is_some(), "off-hours rule still emits an L1-only alert");
        assert!(degr.is_degraded(), "path must degrade to L1-rules-only when serving is down");
        assert_eq!(alert.unwrap().contributing_layers, vec!["L1_rules".to_string()]);
    }
}
