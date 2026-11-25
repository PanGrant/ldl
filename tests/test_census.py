"""ldl.census 单测（合成快照）。"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ldl.census import diff


def snap(**frames):
    return {k: v for k, v in frames.items()}


class TestCensusDiff(unittest.TestCase):
    def test_identical_passes(self):
        s = snap(a={"result": {"p": 1}}, b={"result": None})
        problems, _ = diff(s, s)
        self.assertEqual(problems, [])

    def test_both_none_is_same(self):
        s = snap(b={"result": None})
        problems, st = diff(s, dict(s))
        self.assertEqual(problems, [])
        self.assertEqual(st["same"], 1)

    def test_none_to_verdict_is_flip_not_allowed(self):
        old = snap(b={"result": None})
        new = snap(b={"result": {"p": 1}})
        problems, st = diff(old, new)
        self.assertEqual(len(problems), 1)
        self.assertEqual(st["none_flips"], 1)

    def test_verdict_change_detected(self):
        old = snap(a={"result": {"p": 1}})
        new = snap(a={"result": {"p": 2}})
        problems, st = diff(old, new)
        self.assertEqual(len(problems), 1)
        self.assertEqual(st["changed"], 1)

    def test_added_removed_frames_flagged(self):
        old = snap(a={"result": {}})
        new = snap(a={"result": {}}, b={"result": {}})
        problems, st = diff(old, new)
        self.assertEqual(st["added"], 1)
        old2 = snap(a={"result": {}}, b={"result": {}})
        new2 = snap(a={"result": {}})
        problems2, st2 = diff(old2, new2)
        self.assertEqual(st2["removed"], 1)

    def test_error_state_change_flagged(self):
        old = snap(a={"result": {}})
        new = snap(a={"error": "boom"})
        problems, st = diff(old, new)
        self.assertEqual(st["errors"], 1)


if __name__ == "__main__":
    unittest.main()
