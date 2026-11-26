"""ldl.schema 单测（合成数据，无真名）。"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ldl.schema import LayoutDef, RowSpec, ContractSpec, ColumnSpec


def _example_def():
    return LayoutDef(
        app="demo-app",
        columns={"photo": ColumnSpec("photo", "pane.x0+0.02", "text.x0-0.008")},
        rows=[RowSpec("header", "fixed(header_h)",
                      ContractSpec(shape="hug_block_top",
                                   gates=["hug_window"],
                                   content_blind=True,
                                   exceptions=["sponsor_arrow"],
                                   emits=[]))],
        thresholds={"header_h": {"value": 0.032, "evidence": "合成: 10 帧量定"},
                    "hug_window": {"value": 0.01, "evidence": "合成: 10 帧量定"}})


class TestSchema(unittest.TestCase):
    def test_valid_definition_passes(self):
        self.assertEqual(_example_def().validate(), [])

    def test_duplicate_role_rejected(self):
        d = _example_def()
        d.rows.append(RowSpec("header", "variable",
                              ContractSpec(shape="x")))
        errs = d.validate()
        self.assertTrue(any("角色重复" in e for e in errs))

    def test_content_blind_false_requires_reason(self):
        d = _example_def()
        d.rows[0].contract.content_blind = False
        self.assertTrue(any("content_blind_why" in e for e in d.validate()))

    def test_gate_must_be_in_thresholds(self):
        d = _example_def()
        d.rows[0].contract.gates.append("nonexistent_gate")
        self.assertTrue(any("nonexistent_gate" in e for e in d.validate()))

    def test_threshold_needs_evidence(self):
        d = _example_def()
        d.thresholds["no_evidence"] = {"value": 1}
        self.assertTrue(any("no_evidence" in e for e in d.validate()))

    def test_fixed_height_unknown_key_rejected(self):
        d = _example_def()
        d.rows[0].height = "fixed(unknown_h)"
        self.assertTrue(any("unknown_h" in e for e in d.validate()))

    def test_fixed_height_may_reference_measured_slot(self):
        d = _example_def()
        d.rows[0].height = "fixed(slot_h)"
        d.measured = ["slot_h"]
        self.assertEqual(d.validate(), [])

    def test_threshold_and_measured_must_not_clash(self):
        d = _example_def()
        d.measured = [next(iter(d.thresholds))]
        self.assertTrue(any("同时出现" in e for e in d.validate()))

    def test_measured_roundtrip(self):
        d = _example_def()
        d.measured = ["slot_a", "slot_b"]
        self.assertEqual(d.validate(), [])
        d2 = LayoutDef.from_dict(d.to_dict())
        self.assertEqual(d2.measured, ["slot_a", "slot_b"])
        self.assertEqual(d2.to_dict(), d.to_dict())

    def test_roundtrip(self):
        d = _example_def()
        self.assertEqual(d.validate(), [])
        d2 = LayoutDef.from_dict(d.to_dict())
        self.assertEqual(d2.validate(), [])
        self.assertEqual(d2.to_dict(), d.to_dict())


if __name__ == "__main__":
    unittest.main()
