#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acamp_robots.research import create_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local Academy Camp research project")
    parser.add_argument("name", help="lowercase name using letters, digits, and hyphens")
    args = parser.parse_args()
    destination = create_project(args.name, root=ROOT)
    print(f"Created local research project: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
