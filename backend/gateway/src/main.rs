//! Hawk-Eye gateway binary (BACKEND-10/28).
//!
//! HTTP ingestion surface for the hot path (PLATFORM fronts it with Kong/APISIX). `POST /ingest`
//! decodes one L0 event, runs it through the hot path (`process`), and returns the emitted alert
//! (204 when deduplicated or below threshold). In production the gateway consumes the Kafka
//! `events` topic and produces to the `alerts` topic; this HTTP entry mirrors that for local runs.

use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use hawk_eye_gateway::{
    inference, process, Alert, DegradationController, Event, IdempotencyStore,
};

#[derive(Clone)]
struct AppState {
    dedupe: Arc<IdempotencyStore>,
    degradation: Arc<DegradationController>,
}

#[tokio::main]
async fn main() {
    let state = AppState {
        dedupe: Arc::new(IdempotencyStore::new()),
        degradation: Arc::new(DegradationController::new()),
    };

    let app = Router::new()
        .route("/healthz", get(healthz))
        .route("/ingest", post(ingest))
        .with_state(state);

    let addr = "0.0.0.0:8081";
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind gateway port");
    tracing::info!("hawk-eye gateway listening on {addr}");
    axum::serve(listener, app).await.expect("serve gateway");
}

async fn healthz() -> &'static str {
    "ok"
}

async fn ingest(
    State(st): State<AppState>,
    Json(event): Json<Event>,
) -> Result<Json<Alert>, StatusCode> {
    // ALERT-ONLY: the gateway emits an alert; a human decides any action downstream.
    let alert = process(&event, &st.dedupe, &st.degradation, |f| {
        Some(inference::score_inline(f))
    });
    match alert {
        Some(a) => Ok(Json(a)),
        None => Err(StatusCode::NO_CONTENT),
    }
}
