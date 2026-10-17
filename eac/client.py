"""Host side of the Aura engine: a long-lived `aura engine/engine.aura` process spoken to over pipes."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import sexpr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIN = "/workspace/aura-eac-bin/aura"
DEFAULT_LIB = "/workspace/aura-eac-bin/lib"


def aura_env() -> tuple[str, dict]:
    aura = os.environ.get("AURA_BIN") or (DEFAULT_BIN if Path(DEFAULT_BIN).exists() else "aura")
    env = os.environ.copy()
    lib = os.environ.get("AURA_LIB") or (DEFAULT_LIB if Path(DEFAULT_LIB).exists() else "")
    if lib:
        env["AURA_PATH"] = lib + (":" + env["AURA_PATH"] if env.get("AURA_PATH") else "")
    # set-code / mutate:rebind from a local program still need the sandbox off: cybrid-systems/aura#4575
    env.setdefault("AURA_SANDBOX", "off")
    env.setdefault("AURA_PIPELINE_STRICT", "0")
    return aura, env


def _clean(s: str) -> str:
    return " ".join(str(s).split()) or "-"


class AuraError(RuntimeError):
    pass


class Engine:
    """One Aura process = one workspace (the policies) + one loaded MAL program."""

    def __init__(self, policy: str | Path | None = None):
        aura, env = aura_env()
        self.p = subprocess.Popen([aura, str(ROOT / "engine" / "engine.aura")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                                  env=env, cwd=str(ROOT))
        r = self._read()
        if not r.get("ready"):
            raise AuraError(f"engine failed to start: {r}")
        if policy is not None:
            self.policy(policy)

    def _read(self) -> dict:
        while True:
            line = self.p.stdout.readline()
            if not line:
                err = self.p.stderr.read()[-2000:] if self.p.stderr else ""
                raise AuraError(f"engine exited (rc={self.p.poll()}): {err}")
            if line.startswith("R "):
                return json.loads(line[2:])

    def call(self, cmd: str, *fields) -> dict:
        self.p.stdin.write("\t".join([cmd, *[_clean(f) for f in fields]]) + "\n")
        self.p.stdin.flush()
        r = self._read()
        if r.get("ready"):
            # the engine re-ran its file after an uncaught top-level error (see aura#4588 note in engine.aura)
            raise AuraError(f"engine restarted while handling {cmd}; Aura reported an uncaught error")
        return r

    # -- requests
    def policy(self, path) -> dict:
        r = self.call("POLICY", str(Path(path).resolve()))
        if not r.get("ok"):
            raise AuraError(f"policy load failed: {r}")
        return r

    def load(self, program) -> dict:
        if isinstance(program, (str, Path)) and str(program).endswith(".mal"):
            program = sexpr.parse(Path(program).read_text())
        elif isinstance(program, str):
            program = sexpr.parse(program)
        r = self.call("LOAD", json.dumps(program))
        if not r.get("ok"):
            raise AuraError(f"load failed: {r.get('error')}")
        return r

    def run(self) -> dict:
        r = self.call("RUN")
        for k in ("output", "trace", "snaps", "frames"):     # Aura encodes an empty list as null
            if k in r and r[k] is None:
                r[k] = []
        return r

    def mutate(self, name: str, body: str, reason: str = "lab mutation") -> dict:
        return self.call("MUTATE", name, body, reason)

    def rollback(self) -> dict:
        return self.call("ROLLBACK")

    def source(self) -> str:
        return self.call("SOURCE")["source"]

    def policy_call(self, name: str, *args) -> object:
        return self.call("CALL", name, *[str(a) for a in args])["value"]

    def close(self):
        try:
            self.p.stdin.write("QUIT\n")
            self.p.stdin.flush()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
