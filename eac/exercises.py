"""Exercises with auto-checking, and a learner progress (mastery) file that picks the next exercise.

Every exercise is generated from a seed, and its answer is computed by running the Aura engine, never by
a hand-written answer key. Wrong answers that match a known misconception (for example giving the caller's AR
where the static link's target is asked for) are recorded as *confusions*. The next pick goes back to
that concept, using a variant where the two readings disagree.

Progress file: $EAC_PROGRESS or ./progress.json. It holds per-concept attempts, streak, level and an EWMA score,
plus confusion counts, the answer history, the experiments run with `eac loop --record`, and the pending exercises.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from .client import ROOT, Engine
from .lab import Lab

POLICY = ROOT / "ch06" / "policy.aura"
NAMES = ["alpha", "beta", "gamma", "delta", "eps", "zeta", "eta", "theta", "iota", "kappa", "lam", "mu", "nu", "xi",
         "omi", "pi", "rho", "sig", "tau", "ups", "phi", "chi", "psi", "omg"]

# concept -> (lab, short description). Order = suggested study order. Chapter 7 concepts are merged in at the
# bottom of this file from eac/exercises07.py.
CONCEPTS = {
    "ar-recursion": ("lab1-activation-records", "每次调用一个活动记录：递归时同一过程的多个 AR 同时存活"),
    "static-link-target": ("lab2-static-links", "被调用者的静态链指向词法父过程最近的 AR，而不是调用者"),
    "nonlocal-hops": ("lab2-static-links", "访问非局部变量要沿静态链走 (使用层 - 声明层) 跳"),
    "param-mode": ("lab3-parameter-passing", "传值 / 传引用 / 传值-结果 / 传名 对调用者可见的副作用"),
    "frame-offset": ("lab4-linkage", "由链接约定决定的 AR 布局与字段偏移"),
    "closure-link": ("lab5-procedure-params", "过程参数要带上定义处的环境（静态链）"),
    "dispatch": ("lab6-objects", "方法调用经由对象运行时类的方法向量"),
}
CONFUSION_CONCEPT = {
    "static-vs-dynamic": "static-link-target", "hops-along-callers": "nonlocal-hops",
    "param-side-effects": "param-mode", "value-result-vs-reference": "param-mode",
    "closure-env": "closure-link", "dynamic-dispatch": "dispatch", "layout-order": "frame-offset",
    "frame-count": "ar-recursion",
}
MAX_LEVEL = 3


def progress_path(p=None) -> Path:
    return Path(p or os.environ.get("EAC_PROGRESS") or (Path.cwd() / "progress.json"))


# ------------------------------------------------------------------ engine helpers
def run_program(src: str, mutations=()) -> dict:
    with Engine(POLICY) as eng:
        eng.load(src)
        for d, body in mutations:
            r = eng.mutate(d, body, "exercise variant")
            if not r.get("ok"):
                raise RuntimeError(f"exercise mutation rejected: {r}")
        return eng.run()


def ar_procs(trace) -> dict:
    m = {0: "%program"}
    for t in trace:
        if t["ev"] == "call":
            m[t["id"]] = t["proc"]
    return m


def norm(ans) -> str:
    return ",".join(str(ans).replace(" ", "").replace("[", "").replace("]", "").lower().split(","))


@dataclass
class Exercise:
    id: str
    concept: str
    level: int
    question: str
    program: str
    answer: str
    distractors: dict = field(default_factory=dict)      # wrong answer -> confusion tag
    hint: str = ""

    def to_json(self):
        return self.__dict__.copy()


# ------------------------------------------------------------------ generators
def gen_ar_recursion(rng: random.Random, level: int, contrast: bool) -> Exercise:
    shape = rng.choice(["fact", "sum", "pow2"][: 1 + level])
    n = rng.randint(3, 3 + 2 * level)
    f = rng.choice(NAMES)
    body = {"fact": "(return (* k (call {f} (- k 1))))", "sum": "(return (+ k (call {f} (- k 1))))",
            "pow2": "(return (* 2 (call {f} (- k 1))))"}[shape].format(f=f)
    base = {"fact": 1, "sum": 0, "pow2": 1}[shape]
    src = (f"(program (proc main () (locals) (print (call {f} {n})))"
           f" (proc {f} (k) (locals) (if (<= k 0) (return {base}) {body})))")
    r = run_program(src)
    if contrast or rng.random() < 0.5:
        depth = r["stats"]["max-depth"]
        return Exercise("", "ar-recursion", level, f"main 调用 {f}({n})。执行过程中调用栈上最多同时有几个活动记录（含 main，不含程序全局区）？",
                        src, str(depth), {str(depth - 1): "frame-count", str(n): "frame-count"},
                        "每次调用都分配一个新 AR，直到 k <= 0 的那次调用返回之前都不释放。")
    j = rng.randint(1, n)
    ids = [t["id"] for t in r["trace"] if t["ev"] == "call" and t["proc"] == f and t["args"] == [j]]
    val = next(t["value"] for t in r["trace"] if t["ev"] == "return" and t["id"] == ids[0])
    return Exercise("", "ar-recursion", level, f"main 调用 {f}({n})。k = {j} 的那个 {f} 活动记录返回什么值？",
                    src, str(val), {str(r["output"][0]): "frame-count"}, "每个 AR 有自己的 k；从最深的调用往回算。")


def _chain(rng, depth):
    names = rng.sample(NAMES, depth + 2)
    return names[:depth], names[depth], names[depth + 1]


def _nested_program(chain, target, host_index, var=None, var_owner=None, use_in_target=False):
    """main > chain[0] > chain[1] > ... ; `target` is declared inside chain[host_index] (or main if -1);
    the deepest chain proc calls target. Optional variable `var` declared in var_owner (-1 = main)."""
    def locals_of(idx):
        return f"(locals {var})" if var and var_owner == idx else "(locals)"

    def init(idx):
        return f"(set! {var} {100 + idx + 1}) " if var and var_owner == idx else ""
    tbody = f"(print {var})" if use_in_target else "(print 1)"
    tproc = f"(proc {target} () (locals) {tbody})"
    src = ""
    for idx in range(len(chain) - 1, -1, -1):
        kids = []
        if idx + 1 < len(chain):
            kids.append(src)
        if host_index == idx:
            kids.append(tproc)
        call = f"(call {chain[idx + 1]})" if idx + 1 < len(chain) else f"(call {target})"
        procs = f"(procs {' '.join(kids)}) " if kids else ""
        src = f"(proc {chain[idx]} () {locals_of(idx)} {procs}{init(idx)}{call})"
    main_kids = [src] + ([tproc] if host_index == -1 else [])
    return (f"(program (proc main () {locals_of(-1)} (procs {' '.join(main_kids)}) {init(-1)}(call {chain[0]})))")


def gen_static_link_target(rng, level, contrast):
    depth = 1 + level + rng.randint(0, 1)
    chain, target, _ = _chain(rng, depth)
    if not contrast and rng.random() < 0.25:
        host = depth - 1                                   # target nested in its caller: static == dynamic
    else:
        host = rng.randint(-1, depth - 2)
    src = _nested_program(chain, target, host)
    r = run_program(src)
    ev = next(t for t in r["trace"] if t["ev"] == "call" and t["proc"] == target)
    procs = ar_procs(r["trace"])
    ans, caller = procs[ev["static"]], procs[ev["dynamic"]]
    d = {caller: "static-vs-dynamic"} if caller != ans else {}
    return Exercise("", "static-link-target", level,
                    f"{target} 由 {chain[-1]} 调用。{target} 的静态链指向哪个过程的活动记录？（填过程名）",
                    src, ans, d, "静态链看声明位置（词法父过程），动态链看调用者。")


def gen_nonlocal_hops(rng, level, contrast):
    depth = 1 + level + rng.randint(0, 1)
    chain, target, _ = _chain(rng, depth)
    host = rng.randint(-1, depth - 2)
    owner = rng.randint(-1, host)                          # v declared in an ancestor of target's host
    src = _nested_program(chain, target, host, var="v", var_owner=owner, use_in_target=True)
    r = run_program(src)
    if r.get("error"):
        raise RuntimeError(r["error"])
    lv_target, lv_owner = (host + 1) + 2, owner + 2         # main = level 1, chain[i] = level i+2
    with Engine(POLICY) as eng:
        hops = eng.policy_call("access-hops", lv_target, lv_owner)
    dyn = (depth - 1 - owner) + 1                           # callers: target -> chain[-1] -> ... -> owner
    d = {str(dyn): "hops-along-callers"} if dyn != hops else {}
    owner_name = "main" if owner == -1 else chain[owner]
    return Exercise("", "nonlocal-hops", level,
                    f"{target} 打印 v（v 声明在 {owner_name} 中）。从 {target} 的 AR 出发，访问 v 要沿静态链走几跳？",
                    src, str(hops), d, "跳数 = 使用处的词法层 - 声明处的词法层，与调用了多少层无关。")


PARAM_PROGRAMS = {
    "swap": ("(program (globals a b) (proc main () (locals) (set! a {x}) (set! b {y}) (call swap a b) (print a) (print b))"
             " (proc swap (p q) (locals t) (set! t p) (set! p q) (set! q t)))"),
    "bump": ("(program (globals i) (proc main () (locals) (set! i {x}) (call bump i i) (print i))"
             " (proc bump (u v) (locals) (set! u (+ u {y})) (set! v (* v 2))))"),
    "jensen": ("(program (globals i) (proc main () (locals) (set! i {x}) (print (call sum i 1 {y} (* i 2))) (print i))"
               " (proc sum (k lo hi term) (locals s) (set! s 0) (set! k lo)"
               " (while (<= k hi) (set! s (+ s term)) (set! k (+ k 1))) (return s)))"),
}
MODES = ["value", "reference", "value-result", "name"]


def gen_param_mode(rng, level, contrast):
    prog = rng.choice(["swap", "bump", "jensen"][: 1 + level])
    mode = rng.choice(MODES[1:] if contrast else MODES[: 2 + level])
    src = PARAM_PROGRAMS[prog].format(x=rng.randint(1, 9), y=rng.randint(2, 6))
    outs = {m: run_program(src, [("pass-mode", f'(lambda (proc param) "{m}")')]) for m in MODES}
    ans = ",".join(str(v) for v in outs[mode]["output"])
    d = {}
    for m, tag in (("value", "param-side-effects"), ("reference", "value-result-vs-reference"),
                   ("value-result", "value-result-vs-reference"), ("name", "param-side-effects")):
        o = ",".join(str(v) for v in outs[m]["output"])
        if m != mode and o != ans and o not in d:
            d[o] = tag
    return Exercise("", "param-mode", level, f"所有形参都按 {mode} 传递。main 依次打印什么？（逗号分隔）",
                    src, ans, d, "先想清楚形参槽里放的是值、地址，还是 thunk。")


AREAS = ["ret", "dynamic", "static", "params", "locals", "saved"]


def gen_frame_offset(rng, level, contrast):
    areas = AREAS[:]
    rng.shuffle(areas)
    params = rng.sample(["a", "b", "c", "d"], rng.randint(1, 1 + level))
    locs = rng.sample(["x", "y", "z", "w"], rng.randint(1, 1 + level))
    saves = rng.sample(["r1", "r2", "r3"], rng.randint(0, level))
    ask = rng.choice([("l:" + rng.choice(locs), f"局部变量 {locs[0]}")] if False else
                     [("l:" + v, f"局部变量 {v}") for v in locs] + [("p:" + v, f"形参 {v}") for v in params]
                     + [("static", "静态链"), ("ret", "返回地址")])
    src = (f"(program (proc main () (locals) (call f {' '.join('1' for _ in params)}))"
           f" (proc f ({' '.join(params)}) (locals {' '.join(locs)}) (return 0)))")
    areas_src = " ".join(f'\\"{a}\\"' for a in areas)
    saves_src = " ".join(f'\\"{s}\\"' for s in saves)
    with Engine(POLICY) as eng:
        eng.load(src)
        eng.mutate("frame-areas", f'(lambda (proc) (list {" ".join(chr(34) + a + chr(34) for a in areas)}))', "ex")
        eng.mutate("callee-saves", f'(lambda (proc) (list {" ".join(chr(34) + s + chr(34) for s in saves)}))', "ex")
        lay = eng.call("LAYOUT", "f")["layout"]
    off = dict((n, o) for n, o in lay)[ask[0]]
    naive = {}
    # misconception: ignoring the sizes of earlier variable-sized areas (counting each area as one slot)
    pos = areas.index("params" if ask[0].startswith("p:") else "locals" if ask[0].startswith("l:") else ask[0])
    wrong = pos + (([n for n, _ in lay if n.startswith(ask[0][:2])].index(ask[0])) if ask[0][:2] in ("p:", "l:") else 0)
    if wrong != off:
        naive[str(wrong)] = "layout-order"
    return Exercise("", "frame-offset", level,
                    f"链接约定把 AR 各区按顺序排为 {areas}（每个区的大小：ret/dynamic/static 各 1 槽，params={len(params)}，"
                    f"locals={len(locs)}，saved={len(saves)} 个被调用者保存寄存器）。过程 f({' '.join(params)}) 的局部变量为 "
                    f"{' '.join(locs)}。{ask[1]} 在 f 的 AR 中的偏移是多少（从 0 开始）？",
                    src, str(off), naive, "偏移 = 它前面所有区的大小之和 + 在本区内的位置。")


def gen_closure_link(rng, level, contrast):
    n, other, x = rng.randint(2, 9), rng.randint(100, 900), rng.randint(1, 5)
    times = 1 + min(level, 2)
    calls = "x"
    for _ in range(times):
        calls = f"(call f {calls})"
    src = ("(program (proc main () (locals) (procs"
           f" (proc outer (n) (locals) (procs (proc addn (v) (locals) (return (+ v n))))"
           f" (return (call apply (proc-ref addn) {x})))"
           f" (proc apply (f x) (locals n) (set! n {other}) (return {calls})))"
           f" (print (call outer {n}))))")
    good = run_program(src)["output"][0]
    bad = run_program(src, [("closure-link", '(lambda () "caller")')])["output"][0]
    return Exercise("", "closure-link", level, f"main 打印什么？（apply 自己也有局部变量 n = {other}）",
                    src, str(good), {str(bad): "closure-env"}, "addn 的非局部变量 n 按 addn 的声明位置解析。")


def gen_dispatch(rng, level, contrast):
    a, b = rng.randint(1, 9), rng.randint(10, 90)
    override = contrast or rng.random() < 0.8
    meth = f"(proc val (self) (locals) (return {b}))" if override else f"(proc other (self) (locals) (return {b}))"
    src = (f"(program (class Base (fields) (methods (proc val (self) (locals) (return {a}))))"
           f" (class Sub (extends Base) (fields) (methods {meth}))"
           f" (proc main () (locals o) (set! o (new Sub)) (print (send-as Base o val))))")
    good = run_program(src)["output"][0]
    bad = run_program(src, [("dispatch-class", "(lambda (runtime declared) declared)")])["output"][0]
    return Exercise("", "dispatch", level, "o 的声明类型是 Base，运行时类是 Sub。(send-as Base o val) 打印什么？",
                    src, str(good), {str(bad): "dynamic-dispatch"} if bad != good else {},
                    "虚方法经由对象记录里的方法向量指针找到实现；覆盖的方法占用同一个槽位。")


GENERATORS = {
    "ar-recursion": gen_ar_recursion, "static-link-target": gen_static_link_target,
    "nonlocal-hops": gen_nonlocal_hops, "param-mode": gen_param_mode, "frame-offset": gen_frame_offset,
    "closure-link": gen_closure_link, "dispatch": gen_dispatch,
}


def chapter_of(concept: str) -> str:
    lab = CONCEPTS[concept][0]
    return lab.split("/")[0] if "/" in lab else "ch06"


def generate(concept: str, level: int, seed: int, contrast: bool = False) -> Exercise:
    ex = GENERATORS[concept](random.Random(f"{concept}:{level}:{seed}:{contrast}"), level, contrast)
    ex.id = f"{concept}-L{level}-{seed}{'-c' if contrast else ''}"
    ex.distractors = {w: t for w, t in ex.distractors.items() if norm(w) != norm(ex.answer)}
    return ex


# ------------------------------------------------------------------ progress / mastery
@dataclass
class Progress:
    path: Path
    data: dict

    @classmethod
    def load(cls, p=None) -> "Progress":
        path = progress_path(p)
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault("version", 1)
        data.setdefault("concepts", {})
        data.setdefault("confusions", {})
        data.setdefault("history", [])
        data.setdefault("experiments", [])
        data.setdefault("pending", {})
        data.setdefault("seed", 0)
        return cls(path, data)

    def save(self) -> "Progress":
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        return self

    def concept(self, c: str) -> dict:
        return self.data["concepts"].setdefault(c, {"attempts": 0, "correct": 0, "streak": 0, "level": 1, "score": 0.0})

    def mastered(self, c: str) -> bool:
        s = self.data["concepts"].get(c)
        open_conf = any(n > 0 and CONFUSION_CONCEPT[t] == c for t, n in self.data["confusions"].items())
        return bool(s) and s["attempts"] >= 3 and s["score"] >= 0.8 and s["level"] >= 2 and not open_conf

    def pick(self, chapter: str | None = None) -> tuple[str, bool, str]:
        """-> (concept, contrast?, reason). Confusions first, then unseen concepts, then the weakest one.
        chapter: restrict to one chapter's concepts (None = all)."""
        concepts = [c for c in CONCEPTS if chapter is None or chapter_of(c) == chapter]
        conf = sorted(((n, t) for t, n in self.data["confusions"].items()
                       if n > 0 and CONFUSION_CONCEPT[t] in concepts), reverse=True)
        recent = [h["concept"] for h in self.data["history"][-3:]]
        if conf:
            tag = conf[0][1]
            c = CONFUSION_CONCEPT[tag]
            # interleave: after three contrast drills in a row on the same concept, practise something else once
            if not (len(recent) == 3 and all(r == c for r in recent)):
                return c, True, f"recent confusion: {tag}"
        for c in concepts:
            if c not in self.data["concepts"]:
                return c, False, "not seen yet"
        open_ = [c for c in concepts if not self.mastered(c) and not (len(recent) == 3 and all(r == c for r in recent))]
        pool = open_ or concepts
        c = min(pool, key=lambda k: (self.data["concepts"][k]["score"], self.data["concepts"][k]["attempts"]))
        return c, False, ("weakest concept" if open_ else "all mastered: review the weakest")

    def next_exercise(self, chapter: str | None = None) -> tuple[Exercise, str]:
        c, contrast, why = self.pick(chapter)
        st = self.concept(c)
        self.data["seed"] += 1
        ex = generate(c, st["level"], self.data["seed"], contrast)
        self.data["pending"][ex.id] = ex.to_json()
        return ex, why

    def answer(self, ex_id: str, given: str) -> dict:
        ex = self.data["pending"].pop(ex_id, None)
        if ex is None:
            raise KeyError(f"no pending exercise {ex_id}")
        ok = norm(given) == norm(ex["answer"])
        st = self.concept(ex["concept"])
        st["attempts"] += 1
        st["correct"] += ok
        st["streak"] = st["streak"] + 1 if ok else 0
        st["score"] = round(0.6 * st["score"] + 0.4 * (1.0 if ok else 0.0), 3)
        if ok and st["streak"] >= 2:
            st["level"] = min(MAX_LEVEL, st["level"] + 1)
            st["streak"] = 0
        if not ok and st["level"] > 1 and st["score"] < 0.4:
            st["level"] -= 1
        tag = None
        if not ok:
            tag = next((t for w, t in ex["distractors"].items() if norm(w) == norm(given)), None)
            if tag:
                self.data["confusions"][tag] = self.data["confusions"].get(tag, 0) + 1
        elif ex["id"].endswith("-c"):
            # a correct answer on a contrast variant resolves one count of that concept's confusions
            for t, cc in CONFUSION_CONCEPT.items():
                if cc == ex["concept"] and self.data["confusions"].get(t, 0) > 0:
                    self.data["confusions"][t] -= 1
        rec = {"t": int(time.time()), "id": ex_id, "concept": ex["concept"], "given": given,
               "answer": ex["answer"], "ok": ok, "confusion": tag}
        self.data["history"].append(rec)
        return {**rec, "hint": ex.get("hint", ""), "level": st["level"], "score": st["score"]}

    def note_experiment(self, lab: str, mutation: str, verdict: dict) -> "Progress":
        self.data["experiments"].append({"t": int(time.time()), "lab": lab, "mutation": mutation, **verdict})
        return self

    def status(self, chapter: str | None = None) -> str:
        lines = ["concept               attempts  correct  level  score  mastered"]
        for c in CONCEPTS:
            if chapter and chapter_of(c) != chapter:
                continue
            s = self.data["concepts"].get(c)
            if s:
                lines.append(f"{c:<22}{s['attempts']:>8}{s['correct']:>9}{s['level']:>7}{s['score']:>7.2f}  "
                             f"{'yes' if self.mastered(c) else '-'}")
            else:
                lines.append(f"{c:<22}{'-':>8}")
        conf = {k: v for k, v in self.data["confusions"].items() if v}
        lines.append(f"open confusions: {conf or 'none'}")
        lines.append(f"experiments recorded: {len(self.data['experiments'])}")
        return "\n".join(lines)


# ------------------------------------------------------------------ simulated learners (tests / demos)
def simulated_answer(ex: Exercise, profile: dict, rng: random.Random) -> str:
    """profile: {"skill": {concept: p_correct}, "misconceptions": {tag: p}}"""
    for w, tag in ex.distractors.items():
        if rng.random() < profile.get("misconceptions", {}).get(tag, 0.0):
            return w
    if rng.random() < profile.get("skill", {}).get(ex.concept, 0.9):
        return ex.answer
    return "?"


# ------------------------------------------------------------------ CLI
def add_cli(sub):
    p = sub.add_parser("exercise", help="exercises + learner progress")
    p.add_argument("action", choices=["next", "answer", "status", "show", "auto"])
    p.add_argument("args", nargs="*")
    p.add_argument("--progress", default=None)
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--profile", default='{"misconceptions": {"static-vs-dynamic": 0.6}}')
    p.set_defaults(f=cmd_exercise)


def cmd_exercise(a):
    pr = Progress.load(a.progress)
    ch = getattr(a, "chapter", None)
    if a.action == "next":
        ex, why = pr.next_exercise(ch)
        pr.save()
        print(f"[{ex.id}]  ({why})\n{ex.question}\n\nprogram:\n{ex.program}\n\n"
              f"answer with: python3 -m eac exercise answer {ex.id} <answer>")
    elif a.action == "answer":
        r = pr.answer(a.args[0], " ".join(a.args[1:]))
        pr.save()
        print(("正确 ✓" if r["ok"] else f"不对 ✗  正确答案: {r['answer']}") +
              (f"   (典型混淆: {r['confusion']})" if r["confusion"] else "") +
              (f"\n提示: {r['hint']}" if not r["ok"] else "") + f"\nlevel {r['level']}  score {r['score']:.2f}")
    elif a.action == "show":
        print(json.dumps(pr.data["pending"].get(a.args[0]), ensure_ascii=False, indent=1))
    elif a.action == "status":
        print(pr.status(ch))
    elif a.action == "auto":
        prof, rng = json.loads(a.profile), random.Random(0)
        for _ in range(a.rounds):
            ex, why = pr.next_exercise(ch)
            r = pr.answer(ex.id, simulated_answer(ex, prof, rng))
            print(f"{ex.id:<34} {why:<34} {'ok ' if r['ok'] else 'BAD'} {r['confusion'] or ''}")
        pr.save()
        print(pr.status(ch))
    return 0


# ------------------------------------------------------------------ chapter 7
from . import exercises07 as _x7  # noqa: E402  (needs Exercise defined above)

CONCEPTS.update(_x7.CONCEPTS)
CONFUSION_CONCEPT.update(_x7.CONFUSION_CONCEPT)
GENERATORS.update(_x7.GENERATORS)
