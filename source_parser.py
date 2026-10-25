"""Текст шестой лабы → JSON-AST; литералы входа и текст команд SM.

Рекурсивный спуск для операторов и разбор выражений по приоритетам.
for, elif, составные присваивания, списки и символы раскрываются в AST.
"""

import ast
import re

from values import Sexp


TOKEN = re.compile(
    r'"(?:[^"]|"")*"|'
    r"''''|'(?:\\.|[^'\\])'|"
    r"[A-Za-z][A-Za-z_0-9']*|[0-9]+|==|!=|<=|>=|&&|!!|[+*/%<>=;:(),{}\[\].-]"
)
IDENT = re.compile(r"[a-z][a-zA-Z_0-9']*\Z")
PRECEDENCE = {"!!": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, "<=": 3,
              ">": 3, ">=": 3, ":": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


def tokenize(source):
    result, position = [], 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        if source.startswith("--", position):
            end = source.find("\n", position)
            position = len(source) if end == -1 else end + 1
            continue
        if source.startswith("(*", position):
            depth = 1
            position += 2
            while depth and position < len(source):
                if source.startswith("(*", position):
                    depth += 1
                    position += 2
                elif source.startswith("*)", position):
                    depth -= 1
                    position += 2
                else:
                    position += 1
            if depth:
                raise SyntaxError("Незакрытый комментарий")
            continue
        match = TOKEN.match(source, position)
        if match is None:
            raise SyntaxError(f"Недопустимый символ в позиции {position}: {source[position]!r}")
        result.append(match.group())
        position = match.end()
    return result + ["<EOF>"]


def sequence(statements):
    if not statements:
        raise SyntaxError("Блок должен содержать хотя бы один оператор")
    result = statements[-1]
    for statement in reversed(statements[:-1]):
        result = {"seq": {"left": statement, "right": result}}
    return result


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.position = 0

    def peek(self):
        return self.tokens[self.position]

    def take(self):
        token = self.peek()
        if token == "<EOF>":
            raise SyntaxError("Неожиданный конец ввода")
        self.position += 1
        return token

    def accept(self, token):
        if self.peek() == token:
            self.position += 1
            return True
        return False

    def expect(self, token):
        if not self.accept(token):
            raise SyntaxError(f"Ожидалось {token!r}, получено {self.peek()!r}")

    def arguments(self, closing):
        args = []
        if not self.accept(closing):
            args.append(self.expression())
            while self.accept(","):
                args.append(self.expression())
            self.expect(closing)
        return args

    def expression(self, minimum=0):
        token = self.take()
        if token == "(":
            left = self.expression()
            self.expect(")")
        elif token == "[":
            left = {"array": self.arguments("]")}
        elif token == "{":
            items = self.arguments("}")
            left = {"sexp": "nil", "args": []}
            for item in reversed(items):
                left = {"sexp": "cons", "args": [item, left]}
        elif token.startswith('"'):
            # Эталон сохраняет обратные слеши в STRING буквально.
            left = {"string": token[1:-1].replace('""', '"')}
        elif token.startswith("'"):
            try:
                char = "'" if token == "''''" else ast.literal_eval(token)
            except (SyntaxError, ValueError) as error:
                raise SyntaxError("Некорректный символьный литерал") from error
            if len(char) != 1 or ord(char) > 255:
                raise SyntaxError("CHAR должен задавать один байт")
            left = {"const": ord(char)}
        elif token.isdigit():
            left = {"const": int(token)}
        elif token == "-" and self.peek().isdigit():
            left = {"const": -int(self.take())}
        elif token[0].isupper() and token.isascii():
            left = {"sexp": token, "args": self.arguments(")") if self.accept("(") else []}
        elif IDENT.fullmatch(token):
            left = {"var": token}
        else:
            raise SyntaxError(f"Ожидалось выражение, получено {token!r}")

        compared = False
        while True:
            if minimum <= 7 and self.accept("["):
                index = self.expression()
                self.expect("]")
                left = {"elem": left, "index": index}
            elif minimum <= 7 and self.accept("."):
                self.expect("length")
                left = {"length": left}
            elif self.peek() in PRECEDENCE and PRECEDENCE[self.peek()] >= minimum:
                if self.tokens[self.position + 1] == "=":
                    break
                op = self.take()
                priority = PRECEDENCE[op]
                if priority == 3:
                    if compared:
                        raise SyntaxError("Сравнения нельзя объединять в цепочку без скобок")
                    compared = True
                right = self.expression(priority if op == ":" else priority + 1)
                left = ({"sexp": "cons", "args": [left, right]} if op == ":" else
                        {"binop": op, "left": left, "right": right})
            else:
                return left

    def condition(self):
        self.expect("(")
        result = self.expression()
        self.expect(")")
        return result

    def branch(self):
        condition = self.condition()
        then = self.statement()
        otherwise = "skip"
        if self.accept("else"):
            otherwise = self.statement()
        elif self.accept("elif"):
            otherwise = self.branch()
        return {"if": {"cond": condition, "then": then, "else": otherwise}}

    def statement(self):
        if self.accept("{"):
            body = []
            while not self.accept("}"):
                body.append(self.statement())
            return sequence(body)
        if self.accept("if"):
            return self.branch()
        if self.accept("while"):
            condition = self.condition()
            return {"while": {"cond": condition, "body": self.statement()}}
        if self.accept("do"):
            body = self.statement()
            self.expect("while")
            condition = self.condition()
            self.accept(";")
            return {"do": {"body": body, "cond": condition}}
        if self.accept("for"):
            self.expect("(")
            init = self.statement()
            condition = self.expression()
            self.expect(";")
            step = self.statement()
            self.expect(")")
            body = self.statement()
            return sequence([init, {"while": {"cond": condition, "body": sequence([body, step])}}])
        if self.accept("skip"):
            self.accept(";")
            return "skip"
        if self.peek() in ("read", "write"):
            name = self.take()
            self.expect("(")
            if name == "read":
                value = self.take()
                if not IDENT.fullmatch(value):
                    raise SyntaxError("read принимает имя переменной")
            else:
                value = self.expression()
            self.expect(")")
            self.accept(";")
            return {name: value}
        target = self.expression(7)
        if set(target) not in ({"var"}, {"elem", "index"}):
            raise SyntaxError("Присваивание требует переменную или элемент")
        op = self.take() if self.peek() in PRECEDENCE else None
        self.expect("=")
        value = self.expression()
        self.accept(";")
        if op is not None:
            value = {"binop": op, "left": target, "right": value}
        if "var" in target:
            return {"assn": {"dst": target["var"], "src": value}}
        return {"set": {"dst": target["elem"], "idx": target["index"], "value": value}}


def parse_source(source):
    parser = Parser(source)
    if parser.peek() != "{":
        raise SyntaxError("Программа должна быть заключена в { ... }")
    result = parser.statement()
    parser.expect("<EOF>")
    return result


def parse_values(source):
    """Вход read: литералы через запятую (или пробел для прежнего CLI)."""
    def literal(node):
        if "const" in node:
            return node["const"]
        if "string" in node:
            return bytearray(node["string"], "utf-8")
        if "array" in node:
            return [literal(item) for item in node["array"]]
        if "sexp" in node:
            return Sexp(node["sexp"], [literal(item) for item in node["args"]])
        raise ValueError("Во входе разрешены только литералы значений")

    parser = Parser(source)
    result = []
    while parser.peek() != "<EOF>":
        result.append(literal(parser.expression(7)))
        if parser.accept(",") and parser.peek() == "<EOF>":
            raise SyntaxError("После запятой ожидается значение")
    return result


def parse_machine(source):
    parser = Parser(source)
    code = []
    no_args = {"READ", "WRITE", "LENGTH", "ELEM", "SET"}
    names = {"LD", "ST", "LABEL", "JMP", "JZ", "JNZ"}

    def integer():
        sign = -1 if parser.accept("-") else 1
        token = parser.take()
        if not token.isdigit():
            raise SyntaxError("Ожидался целочисленный операнд")
        return sign * int(token)

    def string():
        token = parser.take()
        if not token.startswith('"'):
            raise SyntaxError("Ожидалась строка в кавычках")
        return token[1:-1].replace('""', '"')

    while parser.peek() != "<EOF>":
        op = parser.take()
        if op in no_args:
            code.append(op)
        elif op in names:
            name = parser.take()
            if not re.fullmatch(r"[A-Za-z][A-Za-z_0-9']*", name):
                raise SyntaxError("Ожидалось имя переменной или метки")
            code.append({op: name})
        elif op in ("CONST", "ARRAY"):
            code.append({op: integer()})
        elif op == "STRING":
            code.append({op: string()})
        elif op == "SEXP":
            tag = string()
            code.append({op: [tag, integer()]})
        elif op == "BINOP":
            operator = parser.take()
            if operator not in PRECEDENCE:
                raise SyntaxError("Неизвестный BINOP")
            code.append({op: operator})
        else:
            raise SyntaxError(f"Неизвестная инструкция: {op}")
    return code
