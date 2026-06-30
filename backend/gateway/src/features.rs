//! Online feature assembly (BACKEND-10, blueprint Part 18.1).
//!
//! In production this reads Redis/Feast by Feast keys (~1–5 ms). Here it derives the few features
//! the rules + inline models need directly from the event, mirroring the Python feature reader.

use crate::ingest::{Event, FeatureView};

pub fn assemble(e: &Event) -> FeatureView {
    let lat_risk = e
        .new_beneficiary_minutes
        .map(|m| (1.0 - m / 120.0).max(0.0))
        .unwrap_or(0.0);
    FeatureView {
        is_off_hours: e.is_off_hours,
        new_beneficiary_minutes: e.new_beneficiary_minutes,
        maker_checker_same_actor: e.maker_checker_same_actor,
        lat_risk,
        amount_inr: e.amount_inr,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lat_risk_higher_for_shorter_latency() {
        let mut e = Event::default();
        e.new_beneficiary_minutes = Some(6.0);
        let fast = assemble(&e).lat_risk;
        e.new_beneficiary_minutes = Some(90.0);
        let slow = assemble(&e).lat_risk;
        assert!(fast > slow);
    }
}
