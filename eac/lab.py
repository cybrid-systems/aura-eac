"""Labs: load a lab directory (lab.json + MAL programs), run its checks against the Aura engine, render
traces and frames, and run the minimal learning loop (run -> mutate -> observe -> rollback -> verify)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .client import ROOT, Engine

CHAPTER_POLICY = {"ch06": ROOT / "ch06" / "policy.aura"}


@dataclass
class Lab:
    path: Path
    spec: dict = field(default_factory=dict)

    @classmethod
    def open(cls, p) -> "Lab":
        p = Path(p)
        if not p.is_absolute():
            p = (ROOT / p) if (ROOT / p).exists() else Path.cwd() / p
        return cls(p, json.loads((p / "lab.json").read_text()))

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def chapter(self) -> str:
        return self.path.parent.name

    @property
    def policy(self) -> Path:
        return CHAPTER_POLICY[self.chapter]

    def program(self, name: str | None = None) -> Path:
        if name:
            return self.path / self.spec["programs"][name]["file"]
        return self.path / self.spec["program"]

    def mutation(self, name: str) -> dict:
        try:
            return self.spec["mutations"][name]
        except KeyError:
            raise KeyError(f"{self.name}: no mutation {name!r}; known: {', '.join(self.spec.get('mutations', {}))}")

    def engine(self) -> Engine:
        return Engine(self.policy)


def apply(eng: Engine, lab: Lab, names) -> None:
    for n in names:
        m = lab.mutation(n)
        r = eng.mutate(m["define"], m["body"], m.get("reason", n))
        if not r.get("ok"):
            raise RuntimeError(f"mutation {n} rejected by Aura: {r}")


def unwind(eng: Engine, k: int) -> None:
    for _ in range(k):
        r = eng.rollback()
        if not r.get("ok"):
            raise RuntimeError(f"rollback failed: {r}")


# ------------------------------------------------------------------ checks
def _check_result(chk: dict, r: dict) -> list[str]:
    errs = []
    if "expect_output" in chk and r.get("output") != chk["expect_output"]:
        errs.append(f"output {r.get('output')} != {chk['expect_output']} (error: {r.get('error')})")
    if "expect_error" in chk:
        if not r.get("error") or chk["expect_error"] not in r["error"]:
            errs.append(f"expected error containing {chk['expect_error']!r}, got {r.get('error')!r}")
    elif "expect_output" in chk and r.get("error"):
        errs.append(f"unexpected error: {r['error']}")
    for k, v in chk.get("expect_stats", {}).items():
        if (r.get("stats") or {}).get(k, 0) != v:
            errs.append(f"stat {k} = {(r.get('stats') or {}).get(k, 0)} != {v}")
    return errs


def run_checks(lab: Lab, eng: Engine | None = None) -> list[dict]:
    own = eng is None
    eng = eng or lab.engine()
    out = []
    try:
        if "stages" in lab.spec:
            return run_stages(lab, eng)
        eng.load(lab.program())
        base_src = eng.source()
        for chk in lab.spec.get("checks", []):
            muts = chk.get("mutations", [])
            apply(eng, lab, muts)
            r = eng.run()
            errs = _check_result(chk, r)
            unwind(eng, len(muts))
            if eng.source() != base_src:
                errs.append("rollback did not restore the workspace source byte-for-byte")
            out.append({"lab": lab.name, "check": chk["name"], "ok": not errs, "errors": errs})
        return out
    finally:
        if own:
            eng.close()


def frame_fields(r: dict, proc: str):
    for snap in r.get("snaps") or []:
        for f in snap["frames"]:
            if f["proc"] == proc:
                return [[o, n] for o, n, _ in f["fields"]]
    for t in r.get("frames") or []:
        if t["proc"] == proc:
            return [[o, n] for o, n, _ in t["fields"]]
    return None


def run_stages(lab: Lab, eng: Engine) -> list[dict]:
    """Lab 4: for each stage, apply its layout mutations; programs in `pass` must print the expected output,
    the others must fail (error or wrong output); check one frame's offsets and link-follow counts."""
    out = []
    progs = lab.spec["programs"]
    base_src = eng.source()
    for st in lab.spec["stages"]:
        apply(eng, lab, st["mutations"])
        errs = []
        for pname, pspec in progs.items():
            eng.load(lab.program(pname))
            r = eng.run()
            ok = r.get("output") == pspec["output"] and not r.get("error")
            if (pname in st["pass"]) != ok:
                errs.append(f"{pname}: {'should pass' if pname in st['pass'] else 'should fail'} "
                            f"(output {r.get('output')}, error {r.get('error')})")
            for k, v in st.get("follows", {}).get(pname, {}).items():
                if (r.get("stats") or {}).get(k, 0) != v:
                    errs.append(f"{pname}: {k} = {(r.get('stats') or {}).get(k, 0)} != {v}")
        lay = st.get("layout")
        if lay:
            eng.load(lab.program("t3-locals"))
            got = layout_of(eng, lay["proc"])
            if got != lay["fields"]:
                errs.append(f"layout of {lay['proc']}: {got} != {lay['fields']}")
        unwind(eng, len(st["mutations"]))
        if eng.source() != base_src:
            errs.append("rollback did not restore the workspace source byte-for-byte")
        out.append({"lab": lab.name, "check": st["name"], "ok": not errs, "errors": errs})
    return out


def layout_of(eng: Engine, proc: str):
    """Frame layout of `proc` as the engine builds it: run with a (break) injected at the start of proc."""
    r = eng.call("LAYOUT", proc)
    if "error" in r:
        raise RuntimeError(r["error"])
    return [[o, n] for n, o in r["layout"]]


# ------------------------------------------------------------------ rendering
def fmt_val(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, list) and v and v[0] == "ref":
        return f"&#{v[1]}[{v[2]}]"
    if isinstance(v, list) and v and v[0] == "obj":
        return f"<obj #{v[1]} {v[2]}>"
    return str(v)


def render_frames(frames: list, title: str = "") -> str:
    lines = [f"── {title}" if title else ""]
    for f in frames:
        if f["proc"] == "%program" and not f["fields"]:
            lines.append("  #0 %program (no globals)")
            continue
        lines.append(f"  #{f['id']} {f['proc']}  (level {f['level']})")
        for off, name, val in f["fields"]:
            arrow = ""
            if name in ("static", "dynamic") and isinstance(val, int):
                arrow = f"  -> AR #{val}"
            lines.append(f"      [{off}] {name:<8} {fmt_val(val)}{arrow}")
    return "\n".join(l for l in lines if l != "")


def render_trace(trace: list) -> str:
    lines = []
    for t in trace:
        pad = "  " * (t.get("depth", 1) - 1)
        if t["ev"] == "call":
            args = ", ".join(fmt_val(a) for a in (t.get("args") or []))
            lines.append(f"{pad}call   #{t['id']} {t['proc']}({args})   static->#{t['static']} dynamic->#{t['dynamic']} [{t['how']}]")
        elif t["ev"] == "return":
            lines.append(f"{pad}return #{t['id']} {t['proc']} = {fmt_val(t['value'])}")
        elif t["ev"] == "send":
            lines.append(f"{pad}send   {t['method']} to a {t['object-class']}: method vector of {t['vtable-of']}, slot {t['slot']} -> {t['impl']}")
    return "\n".join(lines)


def render_run(r: dict, focus: str | None = None, trace: bool = True) -> str:
    parts = []
    if trace:
        parts.append(render_trace(r.get("trace") or []))
    snaps = [s for s in (r.get("snaps") or []) if focus is None or s["label"] == focus]
    if snaps:
        s = snaps[0]
        parts.append(render_frames(s["frames"], f"frames at first (break \"{s['label']}\")"))
    if r.get("error"):
        parts.append(f"ERROR: {r['error']}")
        if r.get("frames"):
            parts.append(render_frames(r["frames"], "frames when the error was raised"))
    parts.append(f"output: {r.get('output')}   stats: {json.dumps(r.get('stats') or {}, sort_keys=True)}")
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------------ the minimal loop
def minimal_loop(lab: Lab, mutation: str, show_trace: bool = False) -> tuple[str, dict]:
    """run -> frames -> mutate (wrong convention) -> run -> observe -> ast:restore -> run -> verify."""
    out = []
    m = lab.mutation(mutation)
    focus = lab.spec.get("focus_break")
    with lab.engine() as eng:
        eng.load(lab.program())
        src0 = eng.source()
        r0 = eng.run()
        out.append(f"== 1. 正确约定 / correct convention ({m['define']} v0)")
        out.append(render_run(r0, focus, show_trace))
        mr = eng.mutate(m["define"], m["body"], m.get("reason", mutation))
        out.append(f"\n== 2. mutate:rebind {m['define']} -> {m['body']}   [{m.get('reason', '')}]  ok={mr.get('ok')}")
        r1 = eng.run()
        out.append(render_run(r1, focus, show_trace))
        if m.get("explain"):
            out.append(f"   说明: {m['explain']}")
        rb = eng.rollback()
        r2 = eng.run()
        same = eng.source() == src0
        out.append(f"\n== 3. ast:restore + eval-current  ok={rb.get('ok')}  source restored byte-for-byte: {same}")
        out.append(render_run(r2, focus, show_trace))
        verdict = {
            "baseline_output": r0.get("output"), "mutated_output": r1.get("output"), "mutated_error": r1.get("error"),
            "restored_output": r2.get("output"), "restored": same and r2.get("output") == r0.get("output"),
            "observable": r1.get("output") != r0.get("output") or bool(r1.get("error")),
        }
        out.append(f"\nverdict: {json.dumps(verdict, ensure_ascii=False)}")
    return "\n".join(out), verdict


def all_labs(chapter: str = "ch06") -> list[Lab]:
    return [Lab.open(p) for p in sorted((ROOT / chapter).iterdir()) if (p / "lab.json").exists()]
