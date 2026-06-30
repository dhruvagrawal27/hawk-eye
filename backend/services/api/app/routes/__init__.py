"""API routers (BACKEND M1–M5). Aggregated and mounted under /api/v1 by app.main."""

from fastapi import APIRouter

from app.routes import (
    admin_routes,
    alert_routes,
    audit_routes,
    auth_routes,
    case_routes,
    compliance_routes,
    coverage_routes,
    disposition_routes,
    entity_routes,
    events_routes,
    explanation_routes,
    feedback_routes,
    model_routes,
    narrative_routes,
    report_routes,
    rules_routes,
)

# Order is cosmetic (OpenAPI grouping). All mounted under the same /api/v1 prefix.
api_router = APIRouter()
for module in (
    auth_routes,
    alert_routes,
    entity_routes,
    explanation_routes,
    narrative_routes,
    disposition_routes,
    feedback_routes,
    rules_routes,
    model_routes,
    audit_routes,
    admin_routes,
    report_routes,
    coverage_routes,
    case_routes,
    compliance_routes,
    events_routes,
):
    api_router.include_router(module.router)

__all__ = ["api_router"]
