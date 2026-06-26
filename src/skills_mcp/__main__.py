"""Console entrypoint: ``python -m skills_mcp`` / ``skills-mcp``."""

from __future__ import annotations

import sys

from .config import ConfigError
from .server import run


def main() -> int:
    try:
        run()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
