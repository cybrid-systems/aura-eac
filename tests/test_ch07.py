"""Chapter 7 tests: every lab check, the minimal loop for every named mutation (observable, restored byte-for-byte,
and the restored code matches the language again), code shape facts read off the emitted ILOC, the exercise
generators (engine-computed answers, distractors never equal to the answer), and chapter-scoped confusion targeting.
Needs the Aura binary (AURA_BIN, default /workspace/aura-eac-bin/aura); run via scripts/test.sh --docker."""
from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from eac import exercises as X
from eac import lab as L

CH7 = [c for c in X.CONCEPTS if X.chapter_of(c) == "ch07"]


class TestLabs07(unittest.TestCase):
    def test_all_checks(self):
        for lb in L.all_labs("ch07"):
            for c in L.run_checks(lb):
                with self.subTest(lab=lb.name, check=c["check"]):
                    self.assertTrue(c["ok"], c["errors"])

    def test_minimal_loop_every_mutation(self):
        for lb in L.all_labs("ch07"):
            for m in lb.spec["mutations"]:
                with self.subTest(lab=lb.name, mutation=m):
                    _, v = L.minimal_loop(lb, m)
                    self.assertTrue(v["observable"], v)
                    self.assertTrue(v["restored"], v)
                    self.assertTrue(v["matches_reference"][0] and v["matches_reference"][2], v)

    def test_every_wrong_mutation_is_caught_by_some_check(self):
        """Each mutation whose reason starts with 'wrong' must appear in a check that expects a mismatch, an error,
        or a changed register count."""
        for lb in L.all_labs("ch07"):
            caught = set()
            for chk in lb.spec["checks"]:
                if chk.get("expect_matches_reference") is False or "expect_error" in chk or "registers" in chk.get("expect_stats", {}):
                    caught.update(chk.get("mutations", []))
            for m, spec in lb.spec["mutations"].items():
                if spec.get("reason", "").startswith("wrong"):
                    with self.subTest(lab=lb.name, mutation=m):
                        self.assertIn(m, caught)

    def test_su_code_evaluates_bigger_subtree_first(self):
        lb = L.Lab.open("ch07/lab1-eval-order")
        with lb.engine() as eng:
            eng.load(lb.program())
            code = eng.run()["code"]
        # e2 = a + (b * (c - (d / (e + f)))): Sethi-Ullman loads e and f before a
        loads = [i[2] for i in code if i[0] == "loadAI"][-6:]
        syms = {0: "a", 4: "b", 8: "c", 12: "d", 16: "e", 20: "f"}
        self.assertEqual([syms[o] for o in loads], ["e", "f", "d", "c", "b", "a"])

    def test_policy_error_is_reported_not_swallowed(self):
        lb = L.Lab.open("ch07/lab1-eval-order")
        with lb.engine() as eng:
            eng.load(lb.program())
            r = eng.mutate("eval-first", "(lambda (op lneed rneed) 2)", "bad type")
            self.assertTrue(r["ok"])
            out = eng.run()
            self.assertIn("policy eval-first returned an invalid value", out["error"])
            eng.rollback()
            self.assertTrue(L.matches_reference(eng.run()))

    def test_address_formulas(self):
        lb = L.Lab.open("ch07/lab3-arrays")
        with lb.engine() as eng:
            eng.load(lb.program())
            base = eng.address("A", 1, 1)["address"]
            for i in range(1, 4):
                for j in range(1, 5):
                    self.assertEqual(eng.address("A", i, j)["address"], base + 4 * ((i - 1) * 4 + (j - 1)))
            L.apply(eng, lb, ["column-major"])
            for i in range(1, 4):
                for j in range(1, 5):
                    self.assertEqual(eng.address("A", i, j)["address"], base + 4 * ((j - 1) * 3 + (i - 1)))
            L.unwind(eng, 1)


class TestExercises07(unittest.TestCase):
    def test_generators_self_check(self):
        for c in CH7:
            for level in (1, 2, 3):
                for contrast in (False, True):
                    with self.subTest(concept=c, level=level, contrast=contrast):
                        ex = X.generate(c, level, 11, contrast)
                        self.assertTrue(ex.answer)
                        self.assertNotIn(X.norm(ex.answer), [X.norm(w) for w in ex.distractors])

    def test_contrast_variants_separate_the_confusion(self):
        for c, tag in (("su-registers", "left-first-registers"), ("reorder-effects", "reorder-side-effects"),
                       ("short-circuit", "no-short-circuit")):
            for seed in (1, 2, 3):
                with self.subTest(concept=c, seed=seed):
                    ex = X.generate(c, 2, seed, True)
                    self.assertIn(tag, ex.distractors.values())

    def test_confusion_targeting_in_chapter_7(self):
        with tempfile.TemporaryDirectory() as d:
            pr = X.Progress.load(Path(d) / "p.json")
            rng = random.Random(3)
            prof = {"misconceptions": {"no-short-circuit": 1.0}, "skill": {}}
            picks = []
            for _ in range(10):
                ex, _ = pr.next_exercise("ch07")
                self.assertEqual(X.chapter_of(ex.concept), "ch07")
                picks.append(ex.concept)
                pr.answer(ex.id, X.simulated_answer(ex, prof, rng))
            pr.save()
            again = X.Progress.load(Path(d) / "p.json")
            self.assertGreater(again.data["confusions"].get("no-short-circuit", 0), 0)
            self.assertGreaterEqual(picks.count("short-circuit"), 5)
            self.assertFalse(again.mastered("short-circuit"))


if __name__ == "__main__":
    unittest.main()
