"""Typed exceptions for the AI Compliance Runtime.

Every error raised by runtime code is a subclass of
:class:`ComplianceRuntimeError`. No bare ``except:`` and no raising of
builtin exceptions from application code (see ``claude_chat/CLAUDE.md`` §5).

``SigningKeyError`` intentionally replaces the name ``KeyError`` from the
design list so it does not shadow the builtin ``KeyError``.
"""

from __future__ import annotations


class ComplianceRuntimeError(Exception):
    """Base class for every runtime error."""


# --- Configuration -------------------------------------------------------


class ConfigError(ComplianceRuntimeError):
    """Raised when configuration is missing, malformed, or invalid."""


# --- Policy --------------------------------------------------------------


class PolicyError(ComplianceRuntimeError):
    """Base class for policy-related errors."""


class PolicyValidationError(PolicyError):
    """Raised when a policy fails schema or semantic validation."""


class PolicyLoadError(PolicyError):
    """Raised when a policy file cannot be read or parsed."""


# --- Evidence ------------------------------------------------------------


class EvidenceError(ComplianceRuntimeError):
    """Base class for evidence-chain errors."""


class ChainIntegrityError(EvidenceError):
    """Raised when the hash chain is broken or inconsistent."""


class SignatureError(EvidenceError):
    """Raised when an Ed25519 signature fails to verify."""


# --- Approvals -----------------------------------------------------------


class ApprovalError(ComplianceRuntimeError):
    """Base class for approval-workflow errors."""


class ConcurrentModificationError(ApprovalError):
    """Raised when an optimistic-lock version check fails."""


class ExpiredApprovalError(ApprovalError):
    """Raised when a decision is attempted on an expired request."""


# --- Keys ----------------------------------------------------------------


class SigningKeyError(ComplianceRuntimeError):
    """Raised for signing-key lifecycle errors.

    Named ``SigningKeyError`` (not ``KeyError``) so it does not shadow the
    builtin :class:`KeyError`.
    """


# --- Catch-all internal --------------------------------------------------


class RuntimeInternalError(ComplianceRuntimeError):
    """Raised for unexpected internal failures that are not user errors."""


_ALL_EXCEPTIONS = (
    ComplianceRuntimeError,
    ConfigError,
    PolicyError,
    PolicyValidationError,
    PolicyLoadError,
    EvidenceError,
    ChainIntegrityError,
    SignatureError,
    ApprovalError,
    ConcurrentModificationError,
    ExpiredApprovalError,
    SigningKeyError,
    RuntimeInternalError,
)


def _self_test() -> None:
    """Verify the exception hierarchy is wired correctly."""
    for exc in _ALL_EXCEPTIONS:
        assert issubclass(exc, ComplianceRuntimeError), exc
    assert issubclass(PolicyValidationError, PolicyError)
    assert issubclass(PolicyLoadError, PolicyError)
    assert issubclass(ChainIntegrityError, EvidenceError)
    assert issubclass(SignatureError, EvidenceError)
    assert issubclass(ConcurrentModificationError, ApprovalError)
    assert issubclass(ExpiredApprovalError, ApprovalError)
    # SigningKeyError must NOT be the builtin KeyError.
    assert SigningKeyError is not KeyError
    assert not issubclass(SigningKeyError, KeyError)
    print("exceptions self-test: PASS")


if __name__ == "__main__":
    _self_test()
