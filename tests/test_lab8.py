from pathlib import Path
import subprocess
import sys
import unittest

import compiler
import interpreter
import machine
import program
from source_parser import parse_source
from values import format_value


ROOT = Path(__file__).resolve().parents[1]


class PatternTests(unittest.TestCase):
    def check_both(self, source, expected):
        ast = parse_source(source)
        for run in (interpreter.run, program.run):
            with self.subTest(engine=run.__module__, source=source):
                self.assertEqual(", ".join(map(format_value, run(ast))), expected)

    def test_reference_pattern_shapes(self):
        ast = parse_source('{ switch (A("abc")) { case A(x) -> write(x) } }')
        self.assertEqual(ast, {"switch": {
            "scrutinee": {"sexp": "A", "args": [{"string": "abc"}]},
            "branches": [{"pattern": {"sexp": "A", "args": [
                {"bind": {"pattern": {"wildcard": []}, "name": "x"}}]},
                "branch": {"write": {"var": "x"}}}]}})

    def test_patterns_and_first_matching_branch(self):
        cases = [
            ('{ switch ([1,2]) { case [1, x] -> write(x) | case _ -> write(9) } }', '2'),
            ('{ switch ([1,2]) { case [x] -> write(1) | case _ -> write(2) } }', '2'),
            ('{ switch ({1,2}) { case x : xs -> write(x); write(xs) } }', '1, {2}'),
            ('{ switch (Pair(1,2)) { case Pair(x,y) -> write(x); write(y) } }', '1, 2'),
            ('{ switch ([1,2]) { case both @ [x,y] -> write(both); write(x); write(y) } }',
             '[1, 2], 1, 2'),
            ('{ switch ([1,2]) { case [x,x] -> write(x) } }', '2'),
            ('{ switch (7) { case #int -> write(1) | case _ -> write(2) } }', '1'),
            ('{ switch ("ab") { case #string -> write(1) | case _ -> write(2) } }', '1'),
            ('{ switch (65) { case \'A\' -> write(1) | case _ -> write(2) } }', '1'),
            ('{ switch (Box) { case #sexp -> write(1) | case _ -> write(2) } }', '1'),
        ]
        for source, expected in cases:
            self.check_both(source, expected)

    def test_mutable_telescope_and_nested_shadowing(self):
        self.check_both('{ x=1; switch (A(2)) { case A(x) -> x=3; write(x) } write(x) }',
                        '3, 1')
        self.check_both('{ x=1; switch (A(2)) { case A(x) -> '
                        'switch (B(3)) { case B(x) -> write(x) }; write(x) } write(x) }',
                        '3, 2, 1')
        self.check_both('{ a=[1]; switch (a) { case x -> x[0]=2 } write(a[0]) }', '2')
        self.check_both('{ a=[1]; switch (a) { case x -> x=[2] } write(a[0]) }', '1')
        self.check_both('{ switch (A(2)) { case A(x) -> y=7; write(y) } write(y) }', '7, 7')

    def test_failed_match_and_unbound_binding(self):
        for source, expected in [
            ('{ switch (3) { case "x" -> write(1) } }', 'match failure on 3'),
            ('{ switch (A(2)) { case A(y) -> write(y) } write(y) }',
             'L0.State.Undefined_variable("y")'),
        ]:
            for run in (interpreter.run, program.run):
                with self.subTest(source=source, engine=run.__module__):
                    with self.assertRaises(RuntimeError) as caught:
                        run(parse_source(source))
                    self.assertEqual(str(caught.exception), expected)

    def test_sexp_comparison_and_mutable_cycle(self):
        self.check_both('{ write(Pair(1)==Pair(1)); write(Pair(1)<Pair(2)); }', '1, 1')
        source = '{ x={1,2,3}; x[1][1][1]=x; write(x==x); }'
        for run in (interpreter.run, program.run):
            with self.subTest(engine=run.__module__):
                with self.assertRaisesRegex(RuntimeError, 'Stack overflow'):
                    run(parse_source(source))

    def test_compiled_switch_and_machine_contract(self):
        code = compiler.compile_program(parse_source(
            '{ switch (A(7)) { case A(x) -> write(x) | case _ -> write(0) } }'))
        self.assertTrue(any(isinstance(item, dict) and "MATCH" in item for item in code))
        self.assertEqual(machine.run(code), [7])
        for bad in [[{"MATCH": ["#int", "missing"]}], [{"MATCH": "bad"}], ["UNBIND"]]:
            with self.subTest(code=bad), self.assertRaises((ValueError, RuntimeError)):
                machine.run(bad)

    def test_command_line_example(self):
        source = ROOT / 'examples/lab8_switch.sil'
        for mode in ('eval', 'run'):
            with self.subTest(mode=mode):
                result = subprocess.run([sys.executable, str(ROOT / 'lab8.py'), str(source),
                                         '--mode', mode], capture_output=True, text=True, timeout=5)
                self.assertEqual((result.returncode, result.stdout, result.stderr),
                                 (0, '1, 7, 7, 1\n', ''))


if __name__ == '__main__':
    unittest.main()
