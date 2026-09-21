import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import interpreter


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(Path(__file__).with_name("spec_cases.json").read_text())


def const(value):
    return {"const": value}


def binop(op, left, right):
    return {"binop": op, "left": const(left), "right": const(right)}


class SpecTests(unittest.TestCase):
    """Каждый метод test_01 … test_27 соответствует номеру в ТЗ."""


def spec_test(case):
    def test(self):
        if "error" in case:
            with self.assertRaises(RuntimeError) as caught:
                interpreter.run(case["ast"], case["input"])
            self.assertEqual(str(caught.exception), case["error"])
        else:
            self.assertEqual(
                interpreter.run(case["ast"], case["input"]), case["output"]
            )
    test.__doc__ = case["name"]
    return test


for case in CASES:
    setattr(SpecTests, f"test_{case['number']:02}", spec_test(case))


class EdgeTests(unittest.TestCase):
    def test_comparisons_false(self):
        for op, left, right in [
            ("==", 1, 2), ("!=", 2, 2), ("<", 2, 1),
            ("<=", 2, 1), (">", 1, 2), (">=", 1, 2),
        ]:
            with self.subTest(op=op):
                self.assertEqual(interpreter.run({"write": binop(op, left, right)}), [0])

    def test_signed_division_and_remainder(self):
        for left, right, quotient, remainder in [
            (-10, 3, -3, -1), (10, -3, -3, 1), (-10, -3, 3, -1),
            (-2, 3, 0, -2), (0, -3, 0, 0), (10**100, 3, 10**100 // 3, 1),
        ]:
            with self.subTest(left=left, right=right):
                self.assertEqual(interpreter.apply_binop("/", left, right), quotient)
                self.assertEqual(interpreter.apply_binop("%", left, right), remainder)

    def test_modulo_zero(self):
        with self.assertRaisesRegex(RuntimeError, "^Division_by_zero$"):
            interpreter.run({"write": binop("%", 1, 0)})

    def test_negative_condition(self):
        ast = {"if": {"cond": binop("-", 0, 1),
                      "then": {"write": const(7)}, "else": "skip"}}
        self.assertEqual(interpreter.run(ast), [7])

    def test_while_false_does_not_execute_body(self):
        ast = {"while": {"cond": const(0), "body": {"write": {"var": "x"}}}}
        self.assertEqual(interpreter.run(ast), [])

    def test_unselected_branch_does_not_execute(self):
        ast = {"if": {"cond": const(1), "then": "skip",
                      "else": {"write": {"var": "x"}}}}
        self.assertEqual(interpreter.run(ast), [])

    def test_both_logical_operands_are_evaluated(self):
        for op, left in [("&&", 0), ("!!", 1)]:
            with self.subTest(op=op):
                ast = {"write": {"binop": op, "left": const(left), "right": {"var": "x"}}}
                with self.assertRaises(RuntimeError) as caught:
                    interpreter.run(ast)
                self.assertEqual(str(caught.exception), 'L0.State.Undefined_variable("x")')

    def test_read_consumes_values_in_order(self):
        ast = {"seq": {"left": {"read": "x"}, "right": {"seq": {
            "left": {"read": "y"}, "right": {"write": {
                "binop": "-", "left": {"var": "x"}, "right": {"var": "y"}
            }}
        }}}}
        self.assertEqual(interpreter.run(ast, [12, 5, 99]), [7])

    def test_run_resets_state_and_keeps_previous_result(self):
        previous = interpreter.run(CASES[1]["ast"])
        self.assertEqual(interpreter.run("skip"), [])
        self.assertEqual(previous, [5])
        with self.assertRaises(RuntimeError):
            interpreter.run({"write": {"var": "x"}})
        self.assertEqual(interpreter.run(CASES[16]["ast"], [2]), [2])
        with self.assertRaisesRegex(RuntimeError, "^L0.Stmt.No_input$"):
            interpreter.run({"read": "x"})

    def test_output_before_runtime_error_is_preserved(self):
        ast = {"seq": {"left": {"write": const(5)}, "right": {"read": "x"}}}
        with self.assertRaises(RuntimeError):
            interpreter.run(ast)
        self.assertEqual(interpreter.output, [5])

    def test_unknown_nodes_and_operators_rejected(self):
        for ast in [{"for": {}}, {"write": {"unknown": 1}},
                    {"write": binop("||", 1, 0)}]:
            with self.subTest(ast=ast), self.assertRaises(ValueError):
                interpreter.run(ast)


class CliTests(unittest.TestCase):
    def invoke(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, str(ROOT / "interpreter.py"), *args],
            input=stdin, text=True, capture_output=True, timeout=5,
        )

    def test_ast_from_stdin(self):
        result = self.invoke("-", stdin=json.dumps(CASES[11]["ast"]))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "0; 1; 2\n", ""))

    def test_explicit_read_values(self):
        result = self.invoke("-", "--input", "-42", stdin=json.dumps(CASES[16]["ast"]))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "-42\n", ""))

    def test_file_with_read_values_on_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.json"
            path.write_text(json.dumps(CASES[16]["ast"]))
            result = self.invoke(str(path), stdin="42\n")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "42\n", ""))

    def test_runtime_errors_exact(self):
        for case in CASES:
            if "error" not in case:
                continue
            with self.subTest(number=case["number"]):
                result = self.invoke("-", "--input", *map(str, case["input"]),
                                     stdin=json.dumps(case["ast"]))
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (1, "", case["error"] + "\n"))

    def test_partial_output_on_error(self):
        ast = {"seq": {"left": {"write": const(5)}, "right": {"read": "x"}}}
        result = self.invoke("-", stdin=json.dumps(ast))
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, "5\n", "L0.Stmt.No_input\n"))

    def test_skip_empty_output(self):
        result = self.invoke("-", stdin='"skip"')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_invalid_json_or_ast(self):
        for source in ["{", "null", "[]", '{"seq": {}}', '{"write": {"const": true}}']:
            with self.subTest(source=source):
                result = self.invoke("-", stdin=source)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.invoke(str(Path(directory) / "missing.json"))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_input(self):
        result = self.invoke("-", "--input", "abc", stdin='"skip"')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
