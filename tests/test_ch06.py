"""Chapter 6 tests: every lab's auto-checks, the minimal loop for every named mutation, the exercise generators
(answers come from the engine and must round-trip through the progress file), and confusion targeting.
Needs the Aura binary (AURA_BIN, default /workspace/aura-eac-bin/aura); run via scripts/test.sh --docker."""
from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from eac import exercises as X
from eac import lab as L
from eac import sexpr


class TestReader(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(sexpr.parse('(a "in r" ; c\n -3 (b))'), ["a", "in r", -3, ["b"]])
        with self.assertRaises(SyntaxError):
            sexpr.parse("(a (b)")


class TestLabs(unittest.TestCase):
    def test_all_checks(self):
        for lb in L.all_labs("ch06"):
            for c in L.run_checks(lb):
                with self.subTest(lab=lb.name, check=c["check"]):
                    self.assertTrue(c["ok"], c["errors"])

    def test_minimal_loop_every_mutation(self):
        for lb in L.all_labs("ch06"):
            if "program" not in lb.spec:
                continue
            for m in lb.spec["mutations"]:
                with self.subTest(lab=lb.name, mutation=m):
                    _, v = L.minimal_loop(lb, m)
                    self.assertTrue(v["observable"], v)
                    self.assertTrue(v["restored"], v)

    def test_lab2_frames_show_the_wrong_link(self):
        lb = L.Lab.open("ch06/lab2-static-links")
        with lb.engine() as eng:
            eng.load(lb.program())
            good = eng.run()["snaps"][0]["frames"]
            L.apply(eng, lb, ["link-to-caller"])
            bad = eng.run()["snaps"][0]["frames"]
            L.unwind(eng, 1)

        def static_of(frames, proc):
            names = {f["id"]: f["proc"] for f in frames}
            f = next(f for f in frames if f["proc"] == proc)
            return names[next(v for _, n, v in f["fields"] if n == "static")]
        self.assertEqual(static_of(good, "q"), "main")
        self.assertEqual(static_of(bad, "q"), "p")

    def test_lab4_layout_offsets(self):
        lb = L.Lab.open("ch06/lab4-linkage")
        with lb.engine() as eng:
            eng.load(lb.program("t3-locals"))
            self.assertEqual(L.layout_of(eng, "tri"),
                             [[0, "ret"], [1, "dynamic"], [2, "static"], [3, "p:m"], [4, "l:acc"]])

    def test_policy_error_is_reported_not_swallowed(self):
        lb = L.Lab.open("ch06/lab2-static-links")
        with lb.engine() as eng:
            eng.load(lb.program())
            r = eng.mutate("static-link-hops", '(lambda (caller-level callee-level) "two")', "bad type")
            self.assertTrue(r["ok"])
            out = eng.run()
            self.assertIn("policy static-link-hops returned an invalid value", out["error"])
            eng.rollback()
            self.assertEqual(eng.run()["output"], [7, 8, 9])


class TestExercises(unittest.TestCase):
    def test_generators_self_check(self):
        for c in [c for c in X.CONCEPTS if X.chapter_of(c) == "ch06"]:
            for level in (1, 2, 3):
                for contrast in (False, True):
                    with self.subTest(concept=c, level=level, contrast=contrast):
                        ex = X.generate(c, level, 7, contrast)
                        self.assertTrue(ex.answer)
                        self.assertNotIn(X.norm(ex.answer), [X.norm(w) for w in ex.distractors])
                        if contrast and c == "static-link-target":
                            self.assertTrue(ex.distractors, "contrast variant must separate static from dynamic")

    def test_progress_round_trip_and_targeting(self):
        with tempfile.TemporaryDirectory() as d:
            pr = X.Progress.load(Path(d) / "p.json")
            rng = random.Random(1)
            prof = {"misconceptions": {"static-vs-dynamic": 1.0}, "skill": {}}
            picks = []
            for _ in range(10):
                ex, why = pr.next_exercise("ch06")
                picks.append(ex.concept)
                pr.answer(ex.id, X.simulated_answer(ex, prof, rng))
            pr.save()
            again = X.Progress.load(Path(d) / "p.json")
            self.assertGreater(again.data["confusions"].get("static-vs-dynamic", 0), 0)
            self.assertGreaterEqual(picks.count("static-link-target"), 5)
            self.assertFalse(again.mastered("static-link-target"))

    def test_correct_learner_levels_up(self):
        with tempfile.TemporaryDirectory() as d:
            pr = X.Progress.load(Path(d) / "p.json")
            ch6 = [c for c in X.CONCEPTS if X.chapter_of(c) == "ch06"]
            for _ in range(len(ch6) * 4):   # EWMA 0.4 -> 0.64 -> 0.78 -> 0.87
                ex, _ = pr.next_exercise("ch06")
                pr.answer(ex.id, ex.answer)
            self.assertTrue(all(pr.mastered(c) for c in ch6), pr.status("ch06"))


if __name__ == "__main__":
    unittest.main()
