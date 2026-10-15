"""Policy engine: YAML policy models, loading, validation, and evaluation.

Rules are evaluated in ascending ``priority`` order; the first rule whose
conditions ALL match determines the disposition (ADR-005, ADR-006). The
operator set is closed (ADR-014). No LLM is ever consulted (ADR-013).
"""

from __future__ import annotations
