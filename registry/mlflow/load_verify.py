"""Signature-verified model load (DATABASE-8).

Blueprint Part 23.3/23.4 (signature verified on load; serving pulls Production +
verifies) + Part 19.4 (verify on load). The serving runtime (BACKEND) calls
``secure_load`` — a load with a valid signature SUCCEEDS; a load with a tampered
artifact or signature is REJECTED. Every load is access-logged (DATABASE-6/8).
"""

from __future__ import annotations

from typing import Optional

from registry.artifacts.serializer import (
    ModelArtifact,
    load_chain,
    registry_path,
    verification_files,
)
from registry.artifacts.store import ArtifactStore, open_artifact_store
from registry.mlflow.access_log import AuditEmitter, log_registry_access, open_emitter
from registry.mlflow.signing import SignatureError, verify_bundle
from services.audit.audit_schema import AuditAction


def verify_artifact(artifact: ModelArtifact) -> bool:
    """True iff the artifact carries a signature that validates its STORED bytes.

    Verifies against the exact bytes on disk (``verification_files``), so a
    corrupt/invalid-JSON metadata.json fails verification rather than crashing.
    """
    if artifact.signature is None:
        return False
    return verify_bundle(verification_files(artifact), artifact.signature)


def secure_load(
    layer: str,
    model: str,
    version: str,
    *,
    actor: str = "svc-serving-loader",
    store: Optional[ArtifactStore] = None,
    emitter: Optional[AuditEmitter] = None,
    access_log: bool = True,
) -> ModelArtifact:
    """Load + verify signature + access-log. Raises ``SignatureError`` on tamper.

    Invariant (Part 19.2): the access event is ALWAYS logged — even when the
    artifact is so corrupt that loading itself fails — so a tampered/extraction
    attempt never escapes the audit trail, and the rejection is ALWAYS a
    ``SignatureError`` (the type BACKEND's serving loader catches), never a raw
    JSON/IO error.
    """
    store = store or open_artifact_store()
    emitter = emitter or open_emitter()
    ref = registry_path(layer, model, version)

    try:
        art = load_chain(store, layer, model, version)
    except Exception as exc:
        if access_log:
            log_registry_access(
                action=AuditAction.REGISTRY_LOAD,
                model_ref=ref,
                actor=actor,
                emitter=emitter,
                details={
                    "signature_verified": "false",
                    "load_error": type(exc).__name__,
                },
            )
        raise SignatureError(
            f"{ref}: load failed ({type(exc).__name__}) — refusing"
        ) from exc

    ok = verify_artifact(art)
    if access_log:
        log_registry_access(
            action=AuditAction.REGISTRY_LOAD,
            model_ref=art.ref,
            actor=actor,
            emitter=emitter,
            details={
                "signature_present": str(art.signature is not None).lower(),
                "signature_verified": str(ok).lower(),
                "metadata_parse_error": str(art.metadata_parse_error).lower(),
                "stage": str(art.metadata.get("stage", "")),
            },
        )
    if art.signature is None:
        raise SignatureError(f"{art.ref}: no signature.sig — refusing to load")
    if not ok:
        raise SignatureError(
            f"{art.ref}: artifact signature INVALID — refusing to load (tamper or corrupt)"
        )
    return art
