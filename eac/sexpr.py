"""Tiny s-expression reader for MAL lab programs (.mal). Symbols become strings, integers become ints.
`;` starts a comment. The result is shipped to the Aura engine as JSON (Aura has no reader for data)."""
from __future__ import annotations

import re

_TOK = re.compile(r";[^\n]*|\(|\)|[^\s()]+")


def parse(text: str):
    toks = [t for t in _TOK.findall(text) if not t.startswith(";")]
    pos = 0

    def atom(t: str):
        if re.fullmatch(r"-?\d+", t):
            return int(t)
        return t

    def read():
        nonlocal pos
        if pos >= len(toks):
            raise SyntaxError("unexpected end of input")
        t = toks[pos]
        pos += 1
        if t == "(":
            out = []
            while pos < len(toks) and toks[pos] != ")":
                out.append(read())
            if pos >= len(toks):
                raise SyntaxError("missing )")
            pos += 1
            return out
        if t == ")":
            raise SyntaxError("unexpected )")
        return atom(t)

    form = read()
    if pos != len(toks):
        raise SyntaxError("trailing input after the program form")
    return form


def unparse(x, indent: int = 0) -> str:
    if isinstance(x, list):
        return "(" + " ".join(unparse(y) for y in x) + ")"
    return str(x)
