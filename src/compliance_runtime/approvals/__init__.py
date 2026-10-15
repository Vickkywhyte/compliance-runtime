"""Approval workflow: state machine, TTL expiry, and the approval service.

Human-in-the-loop is enforced here (ADR-007): the runtime never auto-approves.
State transitions use optimistic locking (C-22) and write an audit event in
the same transaction (C-23); terminal states reject further transitions
(C-24); concurrent decisions resolve to exactly one winner (C-25).
"""

from __future__ import annotations
