"""aura-eac command line.

  python3 -m eac labs                                  list labs
  python3 -m eac run ch06/lab2-static-links [-m MUT]... [--trace]
  python3 -m eac loop ch06/lab2-static-links link-to-caller [--trace]
  python3 -m eac check [LAB ...]                       auto-check labs (default: all of ch06)
  python3 -m eac source                                print the chapter's workspace policies
  python3 -m eac exercise next|answer ID ANSWER|status|auto [--progress FILE]
"""
from __future__ import annotations

import argparse
import json
import sys

from . import exercises, lab as L


def cmd_labs(a):
    for lb in L.all_labs(a.chapter):
        muts = ", ".join(lb.spec.get("mutations", {}))
        print(f"{lb.chapter}/{lb.name:<26} §{','.join(lb.spec['sections']):<12} {lb.spec['title']}")
        print(f"    mutations: {muts}")


def cmd_run(a):
    lb = L.Lab.open(a.lab)
    with lb.engine() as eng:
        eng.load(lb.program(a.program) if a.program else (lb.program() if "program" in lb.spec else lb.program(next(iter(lb.spec["programs"])))))
        L.apply(eng, lb, a.mutate or [])
        r = eng.run()
        print(L.render_run(r, None if a.all_snaps else lb.spec.get("focus_break"), a.trace or True))
        if a.json:
            print(json.dumps(r))


def cmd_loop(a):
    text, verdict = L.minimal_loop(L.Lab.open(a.lab), a.mutation, a.trace)
    print(text)
    if a.record:
        exercises.Progress.load(a.progress).note_experiment(a.lab, a.mutation, verdict).save()
    return 0 if verdict["restored"] and verdict["observable"] else 1


def cmd_check(a):
    labs = [L.Lab.open(p) for p in a.labs] if a.labs else L.all_labs(a.chapter)
    bad = 0
    for lb in labs:
        for c in L.run_checks(lb):
            print(f"{'PASS' if c['ok'] else 'FAIL'}  {c['lab']}: {c['check']}")
            for e in c["errors"]:
                print(f"        {e}")
            bad += not c["ok"]
    print(f"{'all checks passed' if not bad else f'{bad} check(s) failed'}")
    return 1 if bad else 0


def cmd_source(a):
    lb = L.all_labs(a.chapter)[0]
    with lb.engine() as eng:
        print(eng.source())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eac")
    ap.add_argument("--chapter", default="ch06")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("labs").set_defaults(f=cmd_labs)
    p = sub.add_parser("run"); p.add_argument("lab"); p.add_argument("-m", "--mutate", action="append")
    p.add_argument("--program"); p.add_argument("--trace", action="store_true"); p.add_argument("--json", action="store_true")
    p.add_argument("--all-snaps", action="store_true"); p.set_defaults(f=cmd_run)
    p = sub.add_parser("loop"); p.add_argument("lab"); p.add_argument("mutation"); p.add_argument("--trace", action="store_true")
    p.add_argument("--record", action="store_true", help="record the experiment in the progress file")
    p.add_argument("--progress", default=None); p.set_defaults(f=cmd_loop)
    p = sub.add_parser("check"); p.add_argument("labs", nargs="*"); p.set_defaults(f=cmd_check)
    sub.add_parser("source").set_defaults(f=cmd_source)
    exercises.add_cli(sub)
    a = ap.parse_args(argv)
    return a.f(a) or 0


if __name__ == "__main__":
    sys.exit(main())
