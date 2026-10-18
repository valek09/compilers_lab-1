"""Lab 5: interpreter for the textual simple imperative language with arrays."""

import argparse
import copy
import json
import re
import sys


TOKEN = re.compile(r'''\s+|--[^\n]*|\(\*.*?\*\)|"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|==|!=|<=|>=|&&|!!|[+*/%<>=;(),{}\[\].-]''', re.DOTALL)
PRECEDENCE = {"!!": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3,
              ">": 3, ">=": 3, "+": 4, "-": 4, "*": 5, "/": 5, "%": 5}
IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")


def tokenize(source):
    result = []
    position = 0
    while position < len(source):
        match = TOKEN.match(source, position)
        if match is None:
            raise SyntaxError(f"Недопустимый символ в позиции {position}: {source[position]!r}")
        value = match.group()
        if not value.isspace() and not value.startswith("--") and not value.startswith("(*"):
            result.append(value)
        position = match.end()
    result.append("<EOF>")
    return result


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.position = 0

    def peek(self):
        return self.tokens[self.position]

    def take(self):
        token = self.peek()
        self.position += 1
        return token

    def accept(self, token):
        if self.peek() == token:
            self.take()
            return True
        return False

    def expect(self, token):
        if not self.accept(token):
            raise SyntaxError(f"Ожидалось {token!r}, получено {self.peek()!r}")

    def expression(self, minimum=0):
        token = self.take()
        if token == "(":
            left = self.expression()
            self.expect(")")
        elif token == "[":
            elements = []
            if not self.accept("]"):
                elements.append(self.expression())
                while self.accept(","):
                    elements.append(self.expression())
                self.expect("]")
            left = ("array", elements)
        elif token == "-":
            left = ("neg", self.expression(6))
        elif token.startswith('"'):
            left = ("literal", json.loads(token))
        elif token.isdigit():
            left = ("literal", int(token))
        elif IDENT.fullmatch(token):
            left = ("var", token)
        else:
            raise SyntaxError(f"Ожидалось выражение, получено {token!r}")

        while True:
            if self.peek() == "[" and minimum <= 6:
                self.take()
                index = self.expression()
                self.expect("]")
                left = ("index", left, index)
            elif self.peek() == "." and minimum <= 6:
                self.take()
                self.expect("length")
                left = ("length", left)
            elif self.peek() in PRECEDENCE and PRECEDENCE[self.peek()] >= minimum:
                op = self.take()
                right = self.expression(PRECEDENCE[op] + 1)
                left = ("binop", op, left, right)
            else:
                break
        return left

    def statement(self):
        token = self.peek()
        if token == "{":
            self.take()
            body = []
            while self.peek() != "}":
                if self.peek() == "<EOF>":
                    raise SyntaxError("Незакрытый блок")
                body.append(self.statement())
            self.take()
            return ("block", body)
        if token in ("read", "write"):
            self.take()
            self.expect("(")
            arg = self.expression()
            self.expect(")")
            self.expect(";")
            if token == "read" and arg[0] != "var":
                raise SyntaxError("read принимает имя переменной")
            return (token, arg)
        if token == "skip":
            self.take()
            self.expect(";")
            return ("skip",)
        if token in ("if", "while"):
            self.take()
            self.expect("(")
            condition = self.expression()
            self.expect(")")
            body = self.statement()
            if token == "if":
                alternative = None
                if self.accept("else"):
                    alternative = self.statement()
                elif self.accept("elif"):
                    self.position -= 1
                    alternative = self.elif_statement()
                return ("if", condition, body, alternative)
            return ("while", condition, body)
        if token == "do":
            self.take()
            body = self.statement()
            self.expect("while")
            self.expect("(")
            condition = self.expression()
            self.expect(")")
            self.expect(";")
            return ("do", body, condition)
        if token == "for":
            self.take()
            self.expect("(")
            init = self.statement()
            condition = self.expression()
            self.expect(";")
            step = self.statement()
            self.expect(")")
            return ("for", init, condition, step, self.statement())
        target = self.expression(6)
        if target[0] not in ("var", "index"):
            raise SyntaxError("Слева от присваивания нужна переменная или элемент массива")
        if self.peek() in PRECEDENCE and self.tokens[self.position + 1] == "=":
            op = self.take()
            self.take()
        else:
            self.expect("=")
            op = None
        value = self.expression()
        self.expect(";")
        return ("assign", target, op, value)

    def elif_statement(self):
        self.expect("elif")
        self.expect("(")
        condition = self.expression()
        self.expect(")")
        body = self.statement()
        alternative = None
        if self.accept("else"):
            alternative = self.statement()
        elif self.peek() == "elif":
            alternative = self.elif_statement()
        return ("if", condition, body, alternative)

    def parse(self):
        program = self.statement()
        self.expect("<EOF>")
        return program


def kind(value):
    if type(value) is int:
        return "number"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    raise TypeError(f"Недопустимое значение: {value!r}")


def binary(op, left, right):
    left_kind, right_kind = kind(left), kind(right)
    if op in ("==", "!="):
        equal = left_kind == right_kind and (left is right if left_kind == "array" else left == right)
        return int(equal if op == "==" else not equal)
    if op == "+" and left_kind == right_kind and left_kind in ("string", "array"):
        return left + right
    if left_kind != "number" or right_kind != "number":
        raise RuntimeError(f"Операция {op} не определена для {left_kind} и {right_kind}")
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op in ("/", "%"):
        if right == 0:
            raise RuntimeError("Division_by_zero")
        quotient = abs(left) // abs(right) * (-1 if (left < 0) != (right < 0) else 1)
        return quotient if op == "/" else left - quotient * right
    if op == "<":
        return int(left < right)
    if op == "<=":
        return int(left <= right)
    if op == ">":
        return int(left > right)
    if op == ">=":
        return int(left >= right)
    if op == "&&":
        return int(left != 0 and right != 0)
    if op == "!!":
        return int(left != 0 or right != 0)
    raise RuntimeError(f"Неизвестная операция: {op}")


def formatted(value):
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is list:
        return "[" + ", ".join(formatted(item) for item in value) + "]"
    return str(value)


class Interpreter:
    def __init__(self, values=()):
        self.variables = {}
        self.values = list(values)
        self.input_position = 0
        self.output = []
        for value in self.values:
            self.validate(value)

    def validate(self, value):
        if kind(value) == "array":
            for item in value:
                self.validate(item)

    def number(self, value):
        if type(value) is not int:
            raise RuntimeError(f"Ожидалось число, получено {kind(value)}")
        return value

    def index(self, container, index):
        self.number(index)
        if type(container) not in (list, str):
            raise RuntimeError(f"Индексирование не определено для {kind(container)}")
        if index < 0 or index >= len(container):
            raise RuntimeError("Index_out_of_bounds")
        return container[index]

    def evaluate(self, node):
        tag = node[0]
        if tag == "literal":
            return node[1]
        if tag == "var":
            if node[1] not in self.variables:
                raise RuntimeError(f"Undefined_variable({node[1]})")
            return self.variables[node[1]]
        if tag == "array":
            return [self.evaluate(item) for item in node[1]]
        if tag == "neg":
            return -self.number(self.evaluate(node[1]))
        if tag == "index":
            return self.index(self.evaluate(node[1]), self.evaluate(node[2]))
        if tag == "length":
            value = self.evaluate(node[1])
            if type(value) not in (list, str):
                raise RuntimeError(f"length не определён для {kind(value)}")
            return len(value)
        if tag == "binop":
            return binary(node[1], self.evaluate(node[2]), self.evaluate(node[3]))
        raise AssertionError(tag)

    def assign(self, target, value):
        if target[0] == "var":
            self.variables[target[1]] = value
            return
        container = self.evaluate(target[1])
        index = self.number(self.evaluate(target[2]))
        self.index(container, index)
        if type(container) is str:
            raise RuntimeError("Строка неизменяема")
        container[index] = value

    def execute(self, node):
        tag = node[0]
        if tag == "block":
            for item in node[1]:
                self.execute(item)
        elif tag == "skip":
            pass
        elif tag == "read":
            if self.input_position == len(self.values):
                raise RuntimeError("No_input")
            self.variables[node[1][1]] = self.values[self.input_position]
            self.input_position += 1
        elif tag == "write":
            self.output.append(copy.deepcopy(self.evaluate(node[1])))
        elif tag == "assign":
            target, op, expression = node[1:]
            value = self.evaluate(expression)
            if op is not None:
                value = binary(op, self.evaluate(target), value)
            self.assign(target, value)
        elif tag == "if":
            self.execute(node[2] if self.number(self.evaluate(node[1])) != 0 else node[3] or ("skip",))
        elif tag == "while":
            while self.number(self.evaluate(node[1])) != 0:
                self.execute(node[2])
        elif tag == "do":
            while True:
                self.execute(node[1])
                if self.number(self.evaluate(node[2])) == 0:
                    break
        elif tag == "for":
            self.execute(node[1])
            while self.number(self.evaluate(node[2])) != 0:
                self.execute(node[4])
                self.execute(node[3])
        else:
            raise AssertionError(tag)


def run(source, values=()):
    program = Parser(source).parse()
    interpreter = Interpreter(values)
    interpreter.execute(program)
    return interpreter.output


def parse_input(source):
    decoder = json.JSONDecoder()
    values = []
    position = 0
    while position < len(source):
        while position < len(source) and source[position].isspace():
            position += 1
        if position == len(source):
            break
        value, position = decoder.raw_decode(source, position)
        values.append(value)
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Файл с программой; '-' означает stdin")
    parser.add_argument("--input", default="", help="Значения read в формате JSON, разделённые пробелами")
    args = parser.parse_args()
    try:
        if args.source == "-":
            source = sys.stdin.read()
        else:
            with open(args.source, encoding="utf-8") as file:
                source = file.read()
        values = parse_input(args.input)
        result = run(source, values)
    except (OSError, SyntaxError, ValueError, TypeError, RuntimeError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    if result:
        print("; ".join(formatted(value) for value in result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
