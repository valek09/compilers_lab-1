import unittest

import compiler
import interpreter
import machine


EXAMPLE = [
    {"CONST": 2}, {"ST": "x"}, {"LD": "x"}, {"LD": "x"},
    {"BINOP": "*"}, {"CONST": 40}, {"BINOP": "+"}, "WRITE",
]


class MachineTests(unittest.TestCase):
    def test_given_example(self):
        self.assertEqual(machine.run(EXAMPLE, [111]), [44])

    def test_read_and_conditional_jumps(self):
        program = ["READ", {"JZ": "zero"}, {"CONST": 1}, "WRITE",
                   {"JMP": "done"}, {"LABEL": "zero"}, {"CONST": 0},
                   "WRITE", {"LABEL": "done"}]
        self.assertEqual(machine.run(program, [2]), [1])
        self.assertEqual(machine.run(program, [0]), [0])

    def test_invalid_programs(self):
        with self.assertRaisesRegex(ValueError, "Неизвестная метка"):
            machine.run([{"JMP": "missing"}])
        with self.assertRaisesRegex(RuntimeError, "Stack_underflow"):
            machine.run(["WRITE"])


class CompilerTests(unittest.TestCase):
    def test_example_compilation(self):
        ast = {"seq": {"left": {"assn": {"dst": "x", "src": {"const": 2}}},
                       "right": {"write": {"binop": "+", "left": {
                           "binop": "*", "left": {"var": "x"}, "right": {"var": "x"}
                       }, "right": {"const": 40}}}}}
        self.assertEqual(compiler.compile_program(ast), EXAMPLE)

    def test_compiled_program_matches_interpreter(self):
        ast = {"seq": {"left": {"read": "n"}, "right": {"seq": {
            "left": {"assn": {"dst": "sum", "src": {"const": 0}}},
            "right": {"while": {"cond": {"var": "n"}, "body": {"seq": {
                "left": {"assn": {"dst": "sum", "src": {"binop": "+", "left": {"var": "sum"}, "right": {"var": "n"}}}},
                "right": {"assn": {"dst": "n", "src": {"binop": "-", "left": {"var": "n"}, "right": {"const": 1}}}}
            }}}}
        }}}}
        ast = {"seq": {"left": ast, "right": {"write": {"var": "sum"}}}}
        self.assertEqual(machine.run(compiler.compile_program(ast), [4]), interpreter.run(ast, [4]))


if __name__ == "__main__":
    unittest.main()
