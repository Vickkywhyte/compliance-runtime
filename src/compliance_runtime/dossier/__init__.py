"""Compliance dossier generation (FR-6).

Produces a regulator-facing PDF that summarizes the evidence chain, approval
oversight, and EU AI Act Article 12 obligation coverage. Exports only
whitelisted fields (C-38); the private key is never included (C-39) and the
public verification key is shown only as a fingerprint, clearly labeled (C-40).
"""

from __future__ import annotations
