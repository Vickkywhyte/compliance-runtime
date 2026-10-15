"""EU AI Act Article 12 obligation mapping (FR-6).

Maps runtime artifacts to the logging/traceability obligations of Article 12
(with a reference to Article 14 human oversight). Each obligation names the
artifact that satisfies it and how that is verified.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AiactObligation(BaseModel):
    """One EU AI Act obligation and the runtime artifact that satisfies it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    artifact: str
    verification: str


OBLIGATIONS: list[AiactObligation] = [
    AiactObligation(
        id="art12.1",
        description="Automatic recording of events (logs) over the "
        "lifetime of the high-risk AI system",
        artifact="action_records",
        verification="ActionRecords persisted for every tool call; "
        "verified by chain_integrity == 1.0",
    ),
    AiactObligation(
        id="art12.2",
        description="Traceability of the AI system's operation "
        "throughout its lifecycle",
        artifact="action_records + audit_events",
        verification="Each ActionRecord links to a ToolCall and "
        "PolicyEvaluation; hash chain provides temporal "
        "ordering; verified by chain_integrity == 1.0",
    ),
    AiactObligation(
        id="art12.3",
        description="Record retention appropriate to the intended purpose",
        artifact="data/runtime.db",
        verification="SQLite file persists records; append-only "
        "triggers prevent deletion (C-10)",
    ),
    AiactObligation(
        id="art14-human-oversight",
        description="Human oversight of the AI system's operation "
        "(Article 14, referenced by 12)",
        artifact="approval_requests + approval_decisions",
        verification="High-stakes actions require human decision; "
        "append-only decisions; optimistic locking "
        "prevents concurrency corruption (C-21..C-27)",
    ),
]


def get_obligations() -> list[AiactObligation]:
    """Return the EU AI Act obligation mapping."""
    return OBLIGATIONS


def _self_test() -> None:
    ids = {o.id for o in get_obligations()}
    assert ids == {"art12.1", "art12.2", "art12.3", "art14-human-oversight"}
    print("dossier.ai_act_mapping self-test: PASS")


if __name__ == "__main__":
    _self_test()
