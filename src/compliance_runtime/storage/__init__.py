"""Storage layer: SQLite connection/migrations, row models, audit repository.

All SQL lives under this package; callers use repositories and parameterized
queries only (CLAUDE.md §5). Evidence tables are append-only, enforced by
both SQLite triggers (C-10) and the repository API (C-11).
"""

from __future__ import annotations
