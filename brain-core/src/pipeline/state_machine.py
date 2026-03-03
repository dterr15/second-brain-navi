"""Pipeline state machine (doc 04, doc 07, C-05).

Valid transitions (07_system_rules_and_constraints.md section 2.2):
  ingested -> waiting
  waiting -> processing
  processing -> waiting      (JSON invalid or error)
  processing -> completed    (ONLY with valid enriched_data + refined_markdown + priority)
  any -> failed
  failed -> waiting          (retry)

FORBIDDEN (07 section 2.3):
  waiting -> completed       (without valid enrichment)
"""
from src.models.assets import AssetStatus

# Allowed transitions: from_status -> set of allowed to_statuses
VALID_TRANSITIONS: dict[AssetStatus, set[AssetStatus]] = {
    AssetStatus.ingested: {AssetStatus.waiting, AssetStatus.failed},
    AssetStatus.waiting: {AssetStatus.processing, AssetStatus.failed},
    AssetStatus.processing: {AssetStatus.waiting, AssetStatus.completed, AssetStatus.failed},
    AssetStatus.completed: {AssetStatus.failed},
    AssetStatus.failed: {AssetStatus.waiting},
}


class TransitionError(Exception):
    """Raised when a state transition is invalid."""
    def __init__(self, from_status: str, to_status: str, reason: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        msg = f"Invalid transition: {from_status} -> {to_status}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class CompletionError(Exception):
    """Raised when completion requirements are not met (C-01)."""
    def __init__(self, missing_fields: list[str]):
        self.missing_fields = missing_fields
        super().__init__(f"Cannot complete asset. Missing: {', '.join(missing_fields)}")


def validate_transition(from_status: str, to_status: str) -> None:
    """Validate that a state transition is allowed (C-05)."""
    try:
        from_enum = AssetStatus(from_status)
        to_enum = AssetStatus(to_status)
    except ValueError as e:
        raise TransitionError(from_status, to_status, f"Invalid status value: {e}")

    allowed = VALID_TRANSITIONS.get(from_enum, set())
    if to_enum not in allowed:
        raise TransitionError(from_status, to_status, "Transition not allowed by state machine rules")


def validate_completion_requirements(asset) -> None:
    """Enforce C-01: Completion Rule.
    Asset cannot move to completed without:
    - enriched_data (valid, not null)
    - refined_markdown (present, not empty)
    - priority (defined, 1-5)
    """
    missing = []
    if not asset.enriched_data:
        missing.append("enriched_data")
    if not asset.refined_markdown or asset.refined_markdown.strip() == "":
        missing.append("refined_markdown")
    if asset.priority is None:
        missing.append("priority")
    if missing:
        raise CompletionError(missing)
