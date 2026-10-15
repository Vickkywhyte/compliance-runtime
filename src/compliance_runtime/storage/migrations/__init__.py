"""Numbered SQL migration files, applied in order by ``storage.migrate``.

Each migration is a pure-DDL ``NNN_name.sql`` file (05_DATA_SPEC §10).
Applied versions are tracked in the ``schema_migrations`` table so that
re-running is idempotent.
"""

from __future__ import annotations
