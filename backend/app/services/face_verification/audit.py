"""Audit trail for identity verification operations.

Records security-sensitive operations without creating new database tables.
Uses the existing `failure_reason` text field on IdentityVerificationAttempt
to store JSON-encoded override metadata when human review/override occurs.

Audit events are NOT stored in separate tables to avoid migration complexity.
The existing model fields provide sufficient audit capacity:

- `failure_reason`: stores the automated failure reason OR override reason
- `decision`: stores the final decision (automated or overridden)
- `status`: tracks lifecycle progression
- `started_at` / `completed_at`: timestamps

For override events, the `failure_reason` field is updated with a JSON
structure containing:
- original_decision: what the automated system decided
- override_decision: what the human decided
- reason: human-provided reason
- override_timestamp: when the override occurred

Privacy:
- Never stores raw images, embeddings, or biometric templates
- Never stores API keys, secrets, or authorization headers
- Never stores raw provider responses
- Only stores safe operational metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def build_override_audit_entry(
    *,
    original_decision: str,
    override_decision: str,
    reason: str,
    operator_id: str | None = None,
    previous_status: str | None = None,
) -> str:
    """Build a JSON-encoded audit entry for a human override.

    This entry is stored in the `failure_reason` field of the attempt
    when a human override occurs.

    Args:
        original_decision: The automated decision before override.
        override_decision: The human-decided new decision.
        reason: Human-provided reason for the override.
        operator_id: Identifier of the operator performing the override.
        previous_status: Status of the attempt before override.

    Returns:
        JSON-encoded string suitable for storage in failure_reason.
    """
    entry: dict[str, Any] = {
        "audit_type": "human_override",
        "original_decision": original_decision,
        "override_decision": override_decision,
        "reason": reason,
        "override_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if operator_id:
        entry["operator_id"] = operator_id
    if previous_status:
        entry["previous_status"] = previous_status

    return json.dumps(entry, ensure_ascii=False)


def parse_override_audit_entry(failure_reason: str | None) -> dict[str, Any] | None:
    """Parse a JSON-encoded override audit entry from failure_reason.

    Args:
        failure_reason: The failure_reason field value.

    Returns:
        Parsed dict if the entry is a valid override audit entry,
        None otherwise.
    """
    if not failure_reason:
        return None
    try:
        data = json.loads(failure_reason)
        if isinstance(data, dict) and data.get("audit_type") == "human_override":
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def build_verification_audit_metadata(
    *,
    attempt_id: int,
    provider_name: str,
    category: str,
    decision: str | None = None,
    evidence_count: int = 0,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """Build safe audit metadata for a verification operation.

    This metadata is suitable for structured logging — never for storage
    in fields that could leak to clients.

    Privacy:
    - No raw images, embeddings, or biometric data
    - No API keys or secrets
    - Only safe operational information
    """
    metadata: dict[str, Any] = {
        "attempt_id": attempt_id,
        "provider": provider_name,
        "category": category,
    }
    if decision:
        metadata["decision"] = decision
    if evidence_count > 0:
        metadata["evidence_count"] = evidence_count
    if duration_ms is not None:
        metadata["duration_ms"] = round(duration_ms, 2)
    return metadata


def log_verification_event(
    *,
    attempt_id: int,
    event_type: str,
    category: str,
    decision: str | None = None,
    detail: str | None = None,
) -> None:
    """Log a verification event at INFO level.

    Args:
        attempt_id: The verification attempt ID.
        event_type: Type of event (e.g. "provider_executed", "evidence_recorded",
                    "decision_made", "override_applied").
        category: FailureCategory or success category.
        decision: If applicable, the decision made.
        detail: Safe, non-sensitive detail message.
    """
    parts = [
        f"attempt={attempt_id}",
        f"event={event_type}",
        f"category={category}",
    ]
    if decision:
        parts.append(f"decision={decision}")
    if detail:
        parts.append(detail)
    logger.info("VERIFICATION_AUDIT: %s", " | ".join(parts))
