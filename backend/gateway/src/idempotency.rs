//! Idempotency / exactly-once keying (BACKEND-14, blueprint Part 18.1 l.590).
//!
//! Deterministic `event_id` keying so a replay never double-alerts. Backed in production by Flink
//! checkpointing + Kafka transactions; this in-memory keyed set gives the same dedupe semantics.

use std::collections::HashSet;
use std::sync::Mutex;

#[derive(Default)]
pub struct IdempotencyStore {
    seen: Mutex<HashSet<String>>,
}

impl IdempotencyStore {
    pub fn new() -> Self {
        IdempotencyStore { seen: Mutex::new(HashSet::new()) }
    }

    /// Mark an event processed. Returns `true` if newly seen, `false` if it was already processed.
    pub fn mark(&self, event_id: &str) -> bool {
        let mut guard = self.seen.lock().expect("idempotency mutex poisoned");
        guard.insert(event_id.to_string())
    }

    pub fn seen(&self, event_id: &str) -> bool {
        self.seen.lock().expect("idempotency mutex poisoned").contains(event_id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mark_is_idempotent() {
        let s = IdempotencyStore::new();
        assert!(s.mark("evt_1"));
        assert!(!s.mark("evt_1"));
        assert!(s.seen("evt_1"));
    }
}
