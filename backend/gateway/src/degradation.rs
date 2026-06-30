//! Graceful degradation to L1-rules-only (BACKEND-15, blueprint Part 18.1 l.591 / 30.1).
//!
//! When model serving is unavailable the path falls back to L1 rules only, marks affected events
//! for re-scoring, and never goes dark.

use std::sync::Mutex;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    Normal,
    DegradedL1Only,
}

pub struct DegradationController {
    mode: Mutex<Mode>,
    rescore: Mutex<Vec<String>>,
}

impl Default for DegradationController {
    fn default() -> Self {
        Self::new()
    }
}

impl DegradationController {
    pub fn new() -> Self {
        DegradationController { mode: Mutex::new(Mode::Normal), rescore: Mutex::new(Vec::new()) }
    }

    pub fn enter_degraded(&self) {
        *self.mode.lock().unwrap() = Mode::DegradedL1Only;
    }

    /// Leave degraded mode, returning the backlog of event ids to re-score.
    pub fn recover(&self) -> Vec<String> {
        *self.mode.lock().unwrap() = Mode::Normal;
        std::mem::take(&mut *self.rescore.lock().unwrap())
    }

    pub fn mark_for_rescore(&self, event_id: &str) {
        self.rescore.lock().unwrap().push(event_id.to_string());
    }

    pub fn is_degraded(&self) -> bool {
        *self.mode.lock().unwrap() == Mode::DegradedL1Only
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn degrade_then_recover_drains_backlog() {
        let d = DegradationController::new();
        d.enter_degraded();
        d.mark_for_rescore("evt_1");
        assert!(d.is_degraded());
        let backlog = d.recover();
        assert_eq!(backlog, vec!["evt_1".to_string()]);
        assert!(!d.is_degraded());
    }
}
