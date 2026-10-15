"""Configuration: typed models, the single config loader, and key lifecycle.

``loader.py`` is the ONLY module in the codebase that reads ``os.getenv`` /
``os.environ`` (Lesson 8). Everything else imports typed config from here.
"""

from __future__ import annotations
