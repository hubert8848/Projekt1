"""CLI pcbforge.

  python -m pcbforge.cli build  <spec.json|spec.yaml> [--out DIR]
  python -m pcbforge.cli route  <spec.json|spec.yaml> [--out DIR] [--passes N]
  python -m pcbforge.cli check  <spec.json|spec.yaml>
"""
from __future__ import annotations

import argparse
import os
import sys

from . import freerouting
from .checks import run_drc_lite, run_erc, summarize
from .knowledge import Knowledge
from .project import build_project
from .spec import load_json, load_yaml


def _load(path):
    return load_yaml(path) if path.endswith((".yaml", ".yml")) else load_json(path)


def main(argv=None):
    p = argparse.ArgumentParser(prog="pcbforge")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("build", "route", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("spec")
        sp.add_argument("--out", default=None)
        if name == "route":
            sp.add_argument("--passes", type=int, default=10)
    args = p.parse_args(argv)

    design = _load(args.spec)
    outdir = args.out or os.path.join(os.getcwd(), "out", design.name)

    if args.cmd == "check":
        design.ensure_nets()
        from .placement import autoplace
        from .rules import run_rules
        kb = Knowledge.load()
        autoplace(design, kb)
        print("ERC:\n" + summarize(run_erc(design)))
        print("\nDRC-lite:\n" + summarize(run_drc_lite(design)))
        print("\nReguly projektowe:\n" + summarize(run_rules(design, kb)))
        return 0

    res = build_project(design, outdir, kb=Knowledge.load())
    print(f"Zapisano do {outdir}:")
    for f in res.files:
        print("  ", os.path.basename(f))
    print("\nERC:\n" + summarize(res.erc))
    print("\nDRC-lite:\n" + summarize(res.drc))
    print("\nReguly projektowe:\n" + summarize(res.rules))

    if args.cmd == "route":
        dsn = os.path.join(outdir, f"{design.name}.dsn")
        ses = os.path.join(outdir, f"{design.name}.ses")
        ok, log = freerouting.run_freerouting(dsn, ses, passes=args.passes)
        print("\nFreerouting:", "OK -> " + ses if ok else "nie powiodlo sie")
        if not ok:
            print(log)
    return 0 if res.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
