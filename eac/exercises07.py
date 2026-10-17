"""Chapter 7 exercise generators. Same contract as chapter 6 (eac/exercises.py): every answer comes from running the
Aura code generator and ILOC machine (engine/codeshape.aura) under the workspace policies, and every distractor is
what a specific wrong policy produces, tagged with the confusion it reveals."""
from __future__ import annotations

import random

from .client import ROOT, Engine
from .exercises import Exercise

POLICY = ROOT / "ch07" / "policy.aura"
ENGINE = ROOT / "engine" / "codeshape.aura"

CONCEPTS = {
    "su-registers": ("ch07/lab1-eval-order", "先算寄存器需求大的子树（Sethi-Ullman），寄存器需求最小"),
    "reorder-effects": ("ch07/lab1-eval-order", "操作数有副作用时不能为了省寄存器而调换求值顺序"),
    "short-circuit": ("ch07/lab2-booleans", "and/or 短路：右操作数可能根本不执行"),
    "array-address": ("ch07/lab3-arrays", "行主序 / 列主序的地址公式，下界和长度"),
    "case-cost": ("ch07/lab4-case", "case 的线性查找、二分查找、跳转表：比较次数与表大小"),
}
CONFUSION_CONCEPT = {
    "left-first-registers": "su-registers", "leaf-count": "su-registers",
    "reorder-side-effects": "reorder-effects",
    "no-short-circuit": "short-circuit",
    "row-vs-column": "array-address", "lower-bound-omitted": "array-address", "extent-off-by-one": "array-address",
    "linear-vs-binary": "case-cost", "density": "case-cost",
}
LEFT_FIRST = ("eval-first", '(lambda (op lneed rneed) "left")')


def run07(src: str, mutations=()) -> dict:
    with Engine(POLICY, ENGINE) as eng:
        eng.load(src)
        for d, body in mutations:
            r = eng.mutate(d, body, "exercise variant")
            if not r.get("ok"):
                raise RuntimeError(f"exercise mutation rejected: {r}")
        r = eng.run()
    if r.get("error") and "codegen" in str(r["error"]):
        raise RuntimeError(r["error"])
    return r


def _tree(rng, depth, leaves, shape):
    """Random expression tree. shape: 'right' (right-deep spine), 'left', 'bushy' or 'mixed'."""
    if depth == 0:
        return rng.choice(leaves)
    op = rng.choice(["+", "-", "*"])
    if shape == "right":
        return [op, rng.choice(leaves), _tree(rng, depth - 1, leaves, shape)]
    if shape == "left":
        return [op, _tree(rng, depth - 1, leaves, shape), rng.choice(leaves)]
    if shape == "bushy":
        return [op, _tree(rng, depth - 1, leaves, shape), _tree(rng, depth - 1, leaves, shape)]
    return [op, _tree(rng, rng.randint(0, depth - 1), leaves, "mixed"), _tree(rng, depth - 1, leaves, "mixed")]


def _s(e) -> str:
    return e if isinstance(e, str) else str(e) if isinstance(e, int) else "(" + " ".join(_s(x) for x in e) + ")"


def _leaves(e):
    return 1 if not isinstance(e, list) else _leaves(e[1]) + _leaves(e[2])


VARS = ["a", "b", "c", "d", "e", "f"]


def _prog(vals: dict, body: str, extra_vars=()) -> str:
    vs = list(vals) + [v for v in extra_vars if v not in vals]
    sets = " ".join(f"(set! {k} {v})" for k, v in vals.items())
    return f"(program (vars {' '.join(vs)}) (body {sets} {body}))"


def gen_su_registers(rng, level, contrast):
    depth = 2 + level
    shape = "right" if contrast else rng.choice(["right", "bushy", "mixed", "left"][: 2 + level])
    e = _tree(rng, depth, VARS, shape)
    src = _prog({v: rng.randint(1, 9) for v in VARS}, f"(print {_s(e)})")
    su = run07(src)["stats"]["registers"]
    lf = run07(src, [LEFT_FIRST])["stats"]["registers"]
    ask_lf = not contrast and rng.random() < 0.25
    ans, other = (lf, su) if ask_lf else (su, lf)
    d = {str(other): "left-first-registers"}
    d.setdefault(str(_leaves(e)), "leaf-count")
    how = "总是先算左操作数" if ask_lf else "按 Sethi-Ullman 顺序（先算寄存器需求大的子树）"
    return Exercise("", "su-registers", level,
                    f"表达式 {_s(e)}：{how}生成代码（叶子都先 load 进寄存器，运算结果写回其中一个操作数寄存器，用完的寄存器立即复用）。生成的代码一共用到几个寄存器？",
                    src, str(ans), d, "Sethi-Ullman：两边需求相等时 +1，否则取较大者；先算需求大的一边，算另一边时只多占一个寄存器。")


def gen_reorder_effects(rng, level, contrast):
    x0, k, k2 = rng.randint(2, 9), rng.randint(2, 5), rng.randint(1, 4)
    op = rng.choice(["+", "-", "*"][: 1 + level])
    forms = [f"({op} x (* (inc! x) {k}))", f"({op} (+ x {k2}) (* (inc! x) (+ x {k})))",
             f"({op} x (- (* (inc! x) {k}) (+ x {k2})))"]
    e = rng.choice(forms[: 1 + level])
    src = _prog({"x": x0}, f"(print {e})")
    good = run07(src)
    bad = run07(src, [("may-reorder?", "(lambda (left-effects right-effects) #t)")])
    ans, wrong = str(good["output"][0]), str(bad["output"][0])
    return Exercise("", "reorder-effects", level,
                    f"x 初值为 {x0}，(inc! x) 把 x 加 1 并返回新值；语言规定操作数从左到右求值。正确编译后，(print {e}) 打印什么？",
                    src, ans, {wrong: "reorder-side-effects"} if wrong != ans else {},
                    "右边需要的寄存器更多，但它有副作用：编译器不能为了省寄存器把它提到左边之前算。")


def gen_short_circuit(rng, level, contrast):
    n_iter = rng.randint(5, 6 + 2 * level)
    op = rng.choice(["and", "or"])
    m, t = rng.randint(2, 4), rng.randint(1, n_iter - 1)
    cond = rng.choice([f"(= (% k {m}) 0)", f"(< k {t})", f"(!= (% k {m}) 0)"][: 1 + level])
    body = (f"(set! k 0) (while (< k {n_iter}) (if ({op} {cond} (> (inc! n) 0)) (set! hits (+ hits 1))) (set! k (+ k 1))) "
            f"(print n)")
    src = _prog({"n": 0, "hits": 0}, body, extra_vars=["k"])
    good = run07(src)["output"][0]
    bad = run07(src, [("short-circuit?", "(lambda (op rhs-effects rhs-may-trap) #f)")])["output"][0]
    d = {str(bad): "no-short-circuit"} if bad != good else {}
    return Exercise("", "short-circuit", level,
                    f"k 从 0 到 {n_iter - 1} 循环，每次执行 (if ({op} {cond} (> (inc! n) 0)) ...)，n 初值 0。循环结束后打印的 n 是多少？",
                    src, str(good), d, f"{op} 短路：{'左边为假' if op == 'and' else '左边为真'}时右边的 (inc! n) 不执行。")


def gen_array_address(rng, level, contrast):
    lo1 = rng.choice([0, 1, 1, 2] + ([-1, 3] if level >= 2 else []))
    lo2 = rng.choice([0, 1, 1] + ([-2, 5] if level >= 3 else []))
    h1, h2 = lo1 + rng.randint(2, 4), lo2 + rng.randint(2, 5)
    i, j = rng.randint(lo1, h1), rng.randint(lo2, h2)
    layout = "column" if contrast or rng.random() < 0.4 else "row"
    src = f"(program (vars) (arrays (A ({lo1} {h1}) ({lo2} {h2}))) (body))"
    with Engine(POLICY, ENGINE) as eng:
        eng.load(src)

        def addr(muts):
            for dn, body in muts:
                eng.mutate(dn, body, "exercise variant")
            a = eng.address("A", i, j)["address"]
            for _ in muts:
                eng.rollback()
            return a
        lay = ("array-layout", f'(lambda (name) "{layout}")')
        other = ("array-layout", f'(lambda (name) "{"row" if layout == "column" else "column"}")')
        ans = addr([lay])
        d = {str(addr([other])): "row-vs-column",
             str(addr([lay, ("index-origin", "(lambda (lo) 0)")])): "lower-bound-omitted",
             str(addr([lay, ("extent", "(lambda (lo hi) (- hi lo))")])): "extent-off-by-one"}
        base = addr([lay]) - 4 * (((i - lo1) * (h2 - lo2 + 1) + (j - lo2)) if layout == "row"
                                  else ((j - lo2) * (h1 - lo1 + 1) + (i - lo1)))
    name = {"row": "行主序", "column": "列主序"}[layout]
    return Exercise("", "array-address", level,
                    f"数组 A[{lo1}..{h1}, {lo2}..{h2}] 按{name}存放，第一个元素 A[{lo1},{lo2}] 的地址是 {base}，每个元素 4 字节。A[{i},{j}] 的地址是多少？",
                    src, str(ans), d, "行主序：((i - lo1) * len2 + (j - lo2)) * w；列主序把两维对调；len = hi - lo + 1。")


def gen_case_cost(rng, level, contrast):
    n = rng.randint(4, 5 + 2 * level)
    if rng.random() < 0.5:
        keys = sorted(rng.sample(range(1, 10 * n * level + 20), n))
    else:
        start = rng.randint(0, 5)
        keys = sorted(rng.sample(range(start, start + n + rng.randint(0, n)), n))
    arms = " ".join(f"({k} (print {100 + idx}))" for idx, k in enumerate(keys))
    if rng.random() < 0.3 and not contrast:
        src = f"(program (vars k) (body (set! k {keys[0]}) (case k {arms} (else (print 0)))))"
        r = run07(src)
        ans = r["cases"][0]["strategy"]
        d = {s: "density" for s in ("linear", "binary", "jump") if s != ans}
        return Exercise("", "case-cost", level,
                        f"case 有 {n} 个分支，键为 {keys}。按 v0 的密度规则（≤3 个分支用线性查找；键的跨度 ≤ 2×分支数用跳转表；否则二分），"
                        f"编译器选哪种实现？（linear / binary / jump）", src, ans, d,
                        "密度 = 分支数 / (最大键 - 最小键 + 1)；密的用表，稀的用比较。")
    sel = rng.choice(keys + [keys[-1] + 1, keys[0] - 1, rng.choice(keys)])
    strat = rng.choice(["linear", "binary"])
    src = f"(program (vars k) (body (set! k {sel}) (case k {arms} (else (print 0)))))"
    forced = {s: ("case-strategy", f'(lambda (n lo hi) "{s}")') for s in ("linear", "binary")}
    got = {s: run07(src, [forced[s]])["stats"].get("cmps", 0) for s in forced}
    other = "binary" if strat == "linear" else "linear"
    d = {str(got[other]): "linear-vs-binary"} if got[other] != got[strat] else {}
    how = {"linear": "按键的书写顺序逐个比较（每个键一条 cmp_EQ）",
           "binary": "二分查找（每个探测点先 cmp_EQ，不等再 cmp_LT 决定往哪边走）"}[strat]
    return Exercise("", "case-cost", level,
                    f"case 的键为 {keys}，选择子 k = {sel}。用{how}，执行到跳进分支（或 else）为止，一共执行几条比较指令？",
                    src, str(got[strat]), d, "线性查找命中第 i 个键要比较 i 次，落到 else 要比较全部；二分查找每层 1 到 2 次。")


GENERATORS = {"su-registers": gen_su_registers, "reorder-effects": gen_reorder_effects,
              "short-circuit": gen_short_circuit, "array-address": gen_array_address, "case-cost": gen_case_cost}
