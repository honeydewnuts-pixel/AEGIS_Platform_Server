#!/usr/bin/env python3
"""ARRS operator CLI — research only; never trades."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "adapters"))
from registry import ArrsRegistry
from import_discovery import import_discovery
from import_p7 import import_p7

DEFAULT_DATA = ROOT / "data"


def main():
    p = argparse.ArgumentParser(description="ARRS research registry CLI")
    p.add_argument("--root", default=str(DEFAULT_DATA), help="registry data directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("validate")
    sub.add_parser("list-experiments")
    sub.add_parser("list-candidates")
    sub.add_parser("import-discovery")
    sub.add_parser("import-p7")
    sub.add_parser("import-all")
    sub.add_parser("events")

    a = p.parse_args()
    reg = ArrsRegistry(a.root)

    if a.cmd == "init":
        reg._atomic_write()
        print("initialized", a.root)
    elif a.cmd == "validate":
        issues = reg.validate()
        print("OK" if not issues else "ISSUES:\n" + "\n".join(issues))
        sys.exit(0 if not issues else 1)
    elif a.cmd == "list-experiments":
        print(json.dumps(reg.list_experiments(), indent=2, default=str))
    elif a.cmd == "list-candidates":
        print(json.dumps(reg.list_candidates(), indent=2, default=str))
    elif a.cmd == "import-discovery":
        print(json.dumps(import_discovery(reg), indent=2))
    elif a.cmd == "import-p7":
        print(json.dumps(import_p7(reg), indent=2))
    elif a.cmd == "import-all":
        print(json.dumps({"discovery": import_discovery(reg), "p7": import_p7(reg)}, indent=2))
    elif a.cmd == "events":
        print(json.dumps(reg.events(), indent=2, default=str))


if __name__ == "__main__":
    main()
