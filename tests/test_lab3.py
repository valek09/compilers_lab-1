import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import compiler
import interpreter
import machine
import program


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(Path(__file__).with_name("spec_cases.json").read_text(encoding="utf-8"))


class Lab3Tests(unittest.TestCase):
    def test_all_spec_cases_through_stack_machine(self):
        for case in CASES:
            with self.subTest(number=case["number"]):
                code = compiler.compile_program(case["ast"])
                if "error" in case:
                    with self.assertRaises(RuntimeError) as caught:
                        machine.run(code, case["input"])
                    self.assertEqual(str(caught.exception), case["error"])
                else:
                    self.assertEqual(machine.run(code, case["input"]), case["output"])
                    self.assertEqual(program.run(case["ast"], case["input"]),
                                     interpreter.run(case["ast"], case["input"]))

    def test_compiled_program_can_be_saved_and_executed(self):
        ast = {"seq": {"left": {"read": "x"}, "right": {"write": {
            "binop": "*", "left": {"var": "x"}, "right": {"const": 3}
        }}}}
        with tempfile.TemporaryDirectory() as directory:
            ast_path = Path(directory) / "ast.json"
            sm_path = Path(directory) / "sm.json"
            ast_path.write_text(json.dumps(ast), encoding="utf-8")
            compiled = subprocess.run(
                [sys.executable, str(ROOT / "compiler.py"), str(ast_path)],
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            sm_path.write_text(compiled.stdout, encoding="utf-8")
            executed = subprocess.run(
                [sys.executable, str(ROOT / "machine.py"), str(sm_path), "--input", "7"],
                capture_output=True, text=True, timeout=5,
            )
        self.assertEqual((executed.returncode, executed.stdout, executed.stderr),
                         (0, "21\n", ""))

    def test_program_cli_from_stdin(self):
        ast = {"seq": {"left": {"read": "x"}, "right": {"write": {"var": "x"}}}}
        result = subprocess.run(
            [sys.executable, str(ROOT / "program.py"), "-", "--input", "-42"],
            input=json.dumps(ast), capture_output=True, text=True, timeout=5,
        )
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "-42\n", ""))

    def test_program_cli_reports_runtime_and_ast_errors(self):
        for ast, code, message in [
            ({"write": {"var": "missing"}}, 1, "L0.State.Undefined_variable"),
            ({"seq": {}}, 2, "Ошибка входных данных"),
        ]:
            with self.subTest(ast=ast):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "program.py"), "-"],
                    input=json.dumps(ast), capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, code)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
