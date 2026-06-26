"""Centralised Claude Skills MCP server.

A single always-on MCP server that stores reusable Claude skills as plain
instruction text. Every Claude Code instance connects to it and reuses the
skills with no local files, no sync step, and no client-side git operations.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
