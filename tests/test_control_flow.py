"""Схемы с доски и сокращение числа шагов без изменения семантики."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import compiler
import interpreter
import machine
import program


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/spec_cases.json").read_text(encoding="utf-8"))


class BoardTranslationTests(unittest.TestCase):
    def test_if_else_matches_board(self):
        ast = {"if": {"cond": {"var": "x"},
                      "then": {"write": {"const": 1}},
                      "else": {"write": {"const": 2}}}}
        self.assertEqual(compiler.compile_program(ast), [
            {"LD": "x"}, {"JZ": "L0"}, {"CONST": 1}, "WRITE",
            {"JMP": "L1"}, {"LABEL": "L0"}, {"CONST": 2}, "WRITE",
            {"LABEL": "L1"},
        ])

    def test_while_matches_board(self):
        ast = {"while": {"cond": {"var": "x"}, "body": {"read": "x"}}}
        self.assertEqual(compiler.compile_program(ast), [
            {"LABEL": "L0"}, {"LD": "x"}, {"JZ": "L1"},
            "READ", {"ST": "x"}, {"JMP": "L0"}, {"LABEL": "L1"},
        ])

    def test_do_checks_condition_after_body(self):
        ast = {"do": {"body": {"read": "x"}, "cond": {"var": "x"}}}
        self.assertEqual(compiler.compile_program(ast), [
            {"LABEL": "L0"}, "READ", {"ST": "x"},
            {"LD": "x"}, {"JNZ": "L0"},
        ])

    def test_if_without_else_has_no_unconditional_jump(self):
        ast = {"if": {"cond": {"var": "x"},
                      "then": {"write": {"const": 1}}, "else": "skip"}}
        self.assertEqual(compiler.compile_program(ast), [
            {"LD": "x"}, {"JZ": "L0"}, {"CONST": 1}, "WRITE", {"LABEL": "L0"},
        ])

    def test_nested_branches_keep_unique_labels_and_correct_destinations(self):
        ast = {"seq": {"left": {"read": "x"}, "right": {"if": {
            "cond": {"var": "x"},
            "then": {"if": {"cond": {"binop": "<", "left": {"var": "x"},
                                      "right": {"const": 0}},
                            "then": {"write": {"const": 1}}, "else": "skip"}},
            "else": {"write": {"const": 2}},
        }}}}
        code = compiler.compile_program(ast)
        labels = [item["LABEL"] for item in code if isinstance(item, dict) and "LABEL" in item]
        self.assertEqual(len(labels), len(set(labels)))
        for value, expected in [(-3, [1]), (0, [2]), (3, [])]:
            with self.subTest(value=value):
                self.assertEqual(program.run(ast, [value]), expected)

    def test_empty_branches_still_evaluate_condition(self):
        for condition, error in [
            ({"var": "missing"}, 'L0.State.Undefined_variable("missing")'),
            ({"binop": "&&", "left": {"const": 0}, "right": {
                "binop": "/", "left": {"const": 10}, "right": {"const": 0}
            }}, "Division_by_zero"),
        ]:
            with self.subTest(condition=condition):
                with self.assertRaises(RuntimeError) as caught:
                    program.run({"if": {"cond": condition, "then": "skip", "else": "skip"}})
                self.assertEqual(str(caught.exception), error)


class LabelResolutionTests(unittest.TestCase):
    def test_labels_are_addresses_not_executable_instructions(self):
        code = [{"LABEL": "start"}, {"LABEL": "alias"}, {"CONST": 7},
                "WRITE", {"JMP": "end"}, {"LABEL": "end"}]
        original = copy.deepcopy(code)
        instructions, labels = machine.decode_program(code)
        self.assertEqual(instructions, [("CONST", 7), ("WRITE", None), ("JMP", "end")])
        self.assertEqual(labels, {"start": 0, "alias": 0, "end": 3})
        self.assertEqual(machine.run(code), [7])
        self.assertEqual(code, original)

    def test_consecutive_and_trailing_labels_accept_all_jump_types(self):
        for jump, prefix in [("JMP", []), ("JZ", [{"CONST": 0}]),
                             ("JNZ", [{"CONST": -1}])]:
            with self.subTest(jump=jump):
                code = prefix + [{jump: "a"}, {"CONST": 99}, "WRITE",
                                 {"LABEL": "a"}, {"LABEL": "b"}]
                self.assertEqual(machine.run(code), [])

    def test_empty_and_label_only_programs(self):
        for code in [[], [{"LABEL": "end"}], [{"LABEL": "a"}, {"LABEL": "b"}]]:
            with self.subTest(code=code):
                stats = {}
                self.assertEqual(machine.run(code, stats=stats), [])
                self.assertEqual(stats["steps"], 0)

    def test_invalid_labels_are_still_rejected(self):
        for code, message in [
            ([{"LABEL": "x"}, {"LABEL": "x"}], "Повторная метка"),
            ([{"CONST": 1}, {"JZ": "missing"}], "Неизвестная метка"),
        ]:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, message):
                machine.run(code)

    def test_conditional_jump_consumes_condition_on_both_paths(self):
        for jump in ["JZ", "JNZ"]:
            for value in [0, -2]:
                with self.subTest(jump=jump, value=value):
                    code = [{"CONST": value}, {jump: "end"}, {"LABEL": "end"}, "WRITE"]
                    with self.assertRaisesRegex(RuntimeError, "^Stack_underflow$"):
                        machine.run(code)


class StepCountTests(unittest.TestCase):
    def test_fewer_steps_with_same_results(self):
        # Числа before измерены на f07abe2: одна итерация цикла VM = один шаг.
        for number, before, after in [(9, 10, 8), (10, 10, 8), (11, 16, 13),
                                      (12, 44, 39), (14, 35, 32), (15, 9, 8), (16, 44, 39)]:
            case = CASES[number - 1]
            with self.subTest(number=number):
                stats = {}
                self.assertEqual(program.run(case["ast"], case["input"], stats=stats), case["output"])
                self.assertEqual(stats["steps"], after)
                self.assertLess(stats["steps"], before)

    def test_stats_reset_and_include_failing_instruction(self):
        stats = {"steps": 100}
        with self.assertRaisesRegex(RuntimeError, "^L0.Stmt.No_input$"):
            machine.run([{"LABEL": "start"}, "READ"], stats=stats)
        self.assertEqual(stats["steps"], 1)
        self.assertEqual(machine.run([], stats=stats), [])
        self.assertEqual(stats["steps"], 0)

    def test_all_original_cases_with_statistics(self):
        for case in CASES:
            with self.subTest(number=case["number"]):
                stats = {}
                if "error" in case:
                    with self.assertRaises(RuntimeError) as caught:
                        program.run(case["ast"], case["input"], stats=stats)
                    self.assertEqual(str(caught.exception), case["error"])
                else:
                    result = program.run(case["ast"], case["input"], stats=stats)
                    self.assertEqual(result, interpreter.run(case["ast"], case["input"]))
                self.assertGreater(stats["steps"], 0)

    def test_cli_stats_do_not_change_stdout(self):
        sources = {
            "machine.py": [{"LABEL": "start"}, {"CONST": 7}, "WRITE"],
            "program.py": {"write": {"const": 7}},
        }
        for script, source in sources.items():
            for enabled in [False, True]:
                with self.subTest(script=script, enabled=enabled):
                    args = [sys.executable, str(ROOT / script), "-"]
                    if enabled:
                        args.append("--stats")
                    result = subprocess.run(args, input=json.dumps(source), text=True,
                                            capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "7\n")
                    self.assertEqual(result.stderr, "Шагов: 2\n" if enabled else "")


if __name__ == "__main__":
    unittest.main()
