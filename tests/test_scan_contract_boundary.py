"""P2.1 regression tests: pure selection contract and legacy API compatibility."""
import ast
from dataclasses import FrozenInstanceError
import inspect
import unittest

from forex_trading import scan_contract, scan_selection


UNIVERSE = tuple(f"TESTPAIR{i:02d}" for i in range(20))


class ScanContractBoundaryTests(unittest.TestCase):
    def test_reexports_are_the_exact_same_types_and_function(self):
        self.assertIs(scan_selection.ScanMode, scan_contract.ScanMode)
        self.assertIs(scan_selection.ScanSelection, scan_contract.ScanSelection)
        self.assertIs(scan_selection.plan_scan_selection,
                      scan_contract.plan_scan_selection)

    def test_pure_selection_contract_has_no_project_dependencies(self):
        source = inspect.getsource(scan_contract)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "Relative dependency in pure contract")
                self.assertIn(node.module, {"dataclasses", "enum", "re"})
            elif isinstance(node, ast.Import):
                self.assertTrue(all(name.name.split(".")[0]
                                    in {"dataclasses", "enum", "re"}
                                    for name in node.names))

    def test_old_and_new_imports_preserve_single_custom_all(self):
        examples = (
            (scan_contract.ScanMode.SINGLE, ("TESTPAIR04",), ("TESTPAIR04",)),
            (scan_contract.ScanMode.CUSTOM,
             ("TESTPAIR09", "TESTPAIR00"), ("TESTPAIR09", "TESTPAIR00")),
            (scan_contract.ScanMode.ALL, (), UNIVERSE),
        )
        for mode, request, expected in examples:
            with self.subTest(mode=mode):
                selection = scan_contract.plan_scan_selection(
                    UNIVERSE, mode, request)
                self.assertEqual(selection.selected_pairs, expected)
                self.assertEqual(
                    selection, scan_selection.plan_scan_selection(
                        UNIVERSE, mode, request))
                self.assertFalse(selection.may_fetch_real_data)
                self.assertFalse(selection.may_trade)

    def test_selection_value_is_immutable(self):
        selection = scan_contract.plan_scan_selection(
            UNIVERSE, scan_contract.ScanMode.SINGLE, ("TESTPAIR07",))
        with self.assertRaises(FrozenInstanceError):
            selection.may_trade = True

    def test_unknown_or_duplicate_pairs_continue_to_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "PAIR_NOT_IN_APPROVED_CATALOG"):
            scan_contract.plan_scan_selection(
                UNIVERSE, scan_contract.ScanMode.SINGLE, ("EURUSD",))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REQUESTED_PAIR"):
            scan_contract.plan_scan_selection(
                UNIVERSE, scan_contract.ScanMode.CUSTOM,
                ("TESTPAIR01", "TESTPAIR01"))

    def test_single_and_custom_cardinality_unchanged(self):
        with self.assertRaisesRegex(ValueError, "SINGLE_REQUIRES"):
            scan_contract.plan_scan_selection(
                UNIVERSE, scan_contract.ScanMode.SINGLE, ())
        with self.assertRaisesRegex(ValueError, "CUSTOM_REQUIRES"):
            scan_contract.plan_scan_selection(
                UNIVERSE, scan_contract.ScanMode.CUSTOM, ("TESTPAIR01",))


if __name__ == "__main__":
    unittest.main()
