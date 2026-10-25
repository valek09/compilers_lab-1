"""Контракты шестой лабы: результаты получены из L0.js преподавателя."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

import compiler
import interpreter
import machine
import program
import source_parser
import values


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/lab6_reference_cases.json").read_text(encoding="utf-8"))


class ReferenceTests(unittest.TestCase):
    def test_parser_matches_reference_ast(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                self.assertEqual(source_parser.parse_source(case["source"]), case["ast"])

    def test_ast_interpreter_matches_reference(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                self.check_run(interpreter.run, case["ast"], case, "eval")

    def test_our_machine_executes_reference_code(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                self.check_run(machine.run, case["code"], case, "sm")

    def test_our_compiler_matches_reference_behavior(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                self.check_run(program.run, case["ast"], case, "sm")

    def check_run(self, run, code, case, mode):
        inputs = source_parser.parse_values(case["input"])
        expected = case[mode]
        if expected["error"]:
            with self.assertRaises(RuntimeError) as caught:
                run(code, inputs)
            self.assertEqual(values.reference_error(caught.exception), expected["error"])
        else:
            output = run(code, inputs)
            self.assertEqual(", ".join(map(values.format_value, output)), expected["output"])

    def test_new_compilation_without_labels_matches_reference(self):
        for case in CASES:
            if any(isinstance(item, dict) and "LABEL" in item for item in case["code"]):
                continue
            with self.subTest(case=case["name"]):
                self.assertEqual(compiler.compile_program(case["ast"]), case["code"])


class NewMachineTests(unittest.TestCase):
    def test_array_and_sexp_pop_in_source_order(self):
        result = machine.run([{"CONST": 10}, {"CONST": 20}, {"ARRAY": 2},
                              {"SEXP": ["Box", 1]}, "WRITE"])
        self.assertEqual(values.format_value(result[0]), "Box ([10, 20])")

    def test_zero_arity_does_not_pop_existing_values(self):
        result = machine.run([{"CONST": 7}, {"ARRAY": 0}, "WRITE",
                              {"SEXP": ["Nil", 0]}, "WRITE", "WRITE"])
        self.assertEqual(list(map(values.format_value, result)), ["[]", "Nil", "7"])

    def test_new_instructions_detect_stack_underflow(self):
        for code in [["LENGTH"], ["ELEM"], [{"CONST": 1}, "ELEM"], ["SET"],
                     [{"CONST": 1}, {"CONST": 2}, "SET"],
                     [{"CONST": 1}, {"ARRAY": 2}], [{"SEXP": ["Pair", 1]}]]:
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, "Stack_underflow"):
                machine.run(code)

    def test_bad_instruction_operands(self):
        for item in [{"ARRAY": -1}, {"ARRAY": True}, {"STRING": 1},
                     {"SEXP": "Foo"}, {"SEXP": [1, 2]}, {"SEXP": ["Foo", -1]},
                     {"SEXP": ["Foo", True]}, {"SEXP": ["Foo", 1, 2]},
                     {"ELEM": 2}, {"LENGTH": 1}, {"SET": 0}]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                machine.run([item])

    def test_input_iterator_is_consumed_once(self):
        self.assertEqual(machine.run(["READ", "WRITE"], iter([42])), [42])

    def test_shared_input_refs_inside_sexp(self):
        ast = source_parser.parse_source('{ read(a); read(b); a[0]=1; write(b[0][0]); }')
        for run in (interpreter.run, program.run):
            with self.subTest(engine=run.__module__):
                shared = [0]
                self.assertEqual(run(ast, [shared, values.Sexp('Box', [shared])]), [1])

    def test_string_literal_is_fresh_on_each_execution(self):
        source = '{ i=0; while(i<2) { s="a"; write(s[0]); s[0]=98; i+=1; } }'
        ast = source_parser.parse_source(source)
        self.assertEqual(program.run(ast), [97, 97])
        self.assertEqual(interpreter.run(ast), [97, 97])

    def test_set_consumes_three_stack_values(self):
        code = [{"CONST": 1}, {"ARRAY": 1}, {"ST": "a"}, {"LD": "a"},
                {"CONST": 0}, {"CONST": 2}, "SET", "WRITE"]
        with self.assertRaisesRegex(RuntimeError, "Stack_underflow"):
            machine.run(code)

    def test_text_machine_program(self):
        text = 'STRING "ab" ST s LD s CONST 1 CONST 88 SET LD s WRITE'
        self.assertEqual(values.format_value(machine.run(source_parser.parse_machine(text))[0]), '"aX"')
        self.assertEqual(source_parser.parse_machine('SEXP "Pair" 2 ARRAY 0'),
                         [{"SEXP": ["Pair", 2]}, {"ARRAY": 0}])

    def test_colon_binop_builds_cons(self):
        code = [{"CONST": 1}, {"SEXP": ["nil", 0]}, {"BINOP": ":"}, "WRITE"]
        self.assertEqual(values.format_value(machine.run(code)[0]), "{1}")

    def test_bad_ast_types(self):
        for expr in [{"array": 1}, {"string": 4}, {"sexp": 3, "args": []},
                     {"sexp": "Box", "args": 0}]:
            for run in [interpreter.run, program.run]:
                with self.subTest(expr=expr, run=run.__module__), self.assertRaises(ValueError):
                    run({"write": expr})


class SourceTests(unittest.TestCase):
    def test_apostrophe_identifiers_and_optional_semicolons(self):
        ast = source_parser.parse_source("{ x'=2 write(x') skip }")
        self.assertEqual(program.run(ast), [2])

    def test_empty_arrays_and_comments(self):
        ast = source_parser.parse_source('{ (* outer (* inner *) *) a=[]; write(a.length); }')
        self.assertEqual(program.run(ast), [0])

    def test_invalid_source_and_instructions(self):
        for source in ['{ a=[1; }', '{ write(1)', '{ a=1; } junk', '{ read([1]); }',
                       '{ 3=4; }', '{ (* unfinished', '{ write("unfinished); }']:
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                source_parser.parse_source(source)
        for source in ['CONST', 'BOGUS', 'SEXP "Pair"', 'STRING 1', 'ARRAY -1']:
            with self.subTest(source=source), self.assertRaises((SyntaxError, ValueError)):
                machine.run(source_parser.parse_machine(source))

    def test_input_accepts_only_literal_values(self):
        for text in ['x', '1 + 2', 'Foo(x)', '[1, x]', 'true']:
            with self.subTest(text=text), self.assertRaises((SyntaxError, ValueError)):
                source_parser.parse_values(text)

    def test_whitespace_separated_negative_inputs(self):
        self.assertEqual(source_parser.parse_values('1 -2 3'), [1, -2, 3])


class Lab6CliTests(unittest.TestCase):
    def invoke(self, script, *args, stdin):
        return subprocess.run([sys.executable, str(ROOT / script), *args],
                              input=stdin, text=True, capture_output=True, timeout=5)

    def test_source_eval_compile_run(self):
        source = '{ a=[1,2]; a[0]=9; write(Pair(a, "ok")); }'
        for mode in ['eval', 'run']:
            with self.subTest(mode=mode):
                result = self.invoke('lab6.py', '-', '--mode', mode, stdin=source)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, 'Pair ([9, 2], "ok")\n', ''))
        compiled = self.invoke('lab6.py', '-', '--mode', 'compile', stdin=source)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        executed = self.invoke('machine.py', '-', stdin=compiled.stdout)
        self.assertEqual(executed.stdout, 'Pair ([9, 2], "ok")\n')
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_json_entrypoints_accept_complex_inputs(self):
        ast = {"seq": {"left": {"read": "x"}, "right": {"write": {"var": "x"}}}}
        for script, data in [('interpreter.py', ast), ('program.py', ast),
                             ('machine.py', ['READ', 'WRITE'])]:
            with self.subTest(script=script):
                result = self.invoke(script, '-', '--values', 'Pair(1, "x")', stdin=json.dumps(data))
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, 'Pair (1, "x")\n', ''))

    def test_lab6_error_matches_reference_and_suppresses_partial_output(self):
        result = self.invoke('lab6.py', '-', stdin='{ write(1); write(x); }')
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, '', 'ERROR: variable "x" is undefined\n'))

    def test_lab6_stats(self):
        result = self.invoke('lab6.py', '-', '--stats', stdin='{ write("ok"); }')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '"ok"\n', 'Шагов: 2\n'))

    def test_text_machine_cli(self):
        result = self.invoke('machine.py', '-', '--text', stdin='CONST 7 SEXP "Box" 1 WRITE')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'Box (7)\n', ''))

    def test_cycles_report_error_without_traceback(self):
        source = '{ a=[0]; a[0]=a; write(a); }'
        ast = source_parser.parse_source(source)
        for script, data in [('lab6.py', source), ('interpreter.py', json.dumps(ast)),
                             ('program.py', json.dumps(ast)),
                             ('machine.py', json.dumps(compiler.compile_program(ast)))]:
            with self.subTest(script=script):
                result = self.invoke(script, '-', stdin=data)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Cyclic_value', result.stderr)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
