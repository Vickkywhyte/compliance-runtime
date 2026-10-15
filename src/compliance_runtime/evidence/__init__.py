"""Evidence layer: canonical hashing, Ed25519 signing, recorder, verifier.

Every authorized action is recorded as a SHA-256 hash-chained, Ed25519-signed
:class:`~compliance_runtime.storage.models.ActionRecord` (ADR-004). The chain
and signatures can be verified offline from the record set plus the public key.
The private key is loaded only inside :mod:`compliance_runtime.evidence.signing`
(C-18).
"""

from __future__ import annotations
