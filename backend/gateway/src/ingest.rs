//! Ingestion / enrichment types (BACKEND-10, blueprint Part 18.1).
//!
//! The hot path consumes a flattened L0 event (DATA owns the canonical schema) and produces a
//! `FeatureView` (the online features it reads from Redis/Feast). Kept flat for cache-friendly,
//! allocation-light processing on the latency-critical path.

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct Event {
    pub event_id: String,
    pub actor_id: String,
    pub verb: String,
    pub channel: String,
    pub amount_inr: i64,
    pub is_off_hours: bool,
    /// Minutes since a new beneficiary was created (None if not applicable) — the burst signal.
    pub new_beneficiary_minutes: Option<f64>,
    pub maker_checker_same_actor: bool,
    /// Whether a matching application transaction exists (linkage app-txn↔DB-write).
    pub app_txn_present: bool,
}

#[derive(Clone, Debug, Default)]
pub struct FeatureView {
    pub is_off_hours: bool,
    pub new_beneficiary_minutes: Option<f64>,
    pub maker_checker_same_actor: bool,
    /// Derived: lower new-beneficiary latency ⇒ higher risk (0..1).
    pub lat_risk: f64,
    pub amount_inr: i64,
}
