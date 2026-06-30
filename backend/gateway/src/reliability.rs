//! Reliability patterns (BACKEND-14, blueprint Part 32.2): circuit breaker + DLQ + backpressure.

use std::collections::VecDeque;
use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BreakerState {
    Closed,
    Open,
    HalfOpen,
}

/// Closed → Open (after N failures) → HalfOpen (after cooldown) → Closed (on success).
pub struct CircuitBreaker {
    failure_threshold: u32,
    reset_after: Duration,
    failures: Mutex<u32>,
    opened_at: Mutex<Option<Instant>>,
}

impl CircuitBreaker {
    pub fn new(failure_threshold: u32, reset_after: Duration) -> Self {
        CircuitBreaker {
            failure_threshold,
            reset_after,
            failures: Mutex::new(0),
            opened_at: Mutex::new(None),
        }
    }

    pub fn state(&self) -> BreakerState {
        let opened = *self.opened_at.lock().unwrap();
        match opened {
            Some(t) if t.elapsed() >= self.reset_after => BreakerState::HalfOpen,
            Some(_) => BreakerState::Open,
            None => BreakerState::Closed,
        }
    }

    pub fn allow(&self) -> bool {
        !matches!(self.state(), BreakerState::Open)
    }

    pub fn record_success(&self) {
        *self.failures.lock().unwrap() = 0;
        *self.opened_at.lock().unwrap() = None;
    }

    pub fn record_failure(&self) {
        let mut f = self.failures.lock().unwrap();
        *f += 1;
        if *f >= self.failure_threshold {
            *self.opened_at.lock().unwrap() = Some(Instant::now());
        }
    }
}

/// Bounded dead-letter queue (events that fail after retries land here, not lost).
#[derive(Default)]
pub struct DeadLetterQueue {
    items: Mutex<VecDeque<(String, String)>>, // (event_id, reason)
}

impl DeadLetterQueue {
    pub fn new() -> Self {
        DeadLetterQueue { items: Mutex::new(VecDeque::new()) }
    }
    pub fn put(&self, event_id: &str, reason: &str) {
        self.items.lock().unwrap().push_back((event_id.to_string(), reason.to_string()));
    }
    pub fn len(&self) -> usize {
        self.items.lock().unwrap().len()
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn breaker_opens_after_threshold() {
        let cb = CircuitBreaker::new(2, Duration::from_secs(5));
        assert!(cb.allow());
        cb.record_failure();
        cb.record_failure();
        assert_eq!(cb.state(), BreakerState::Open);
        assert!(!cb.allow());
        cb.record_success();
        assert_eq!(cb.state(), BreakerState::Closed);
    }
}
