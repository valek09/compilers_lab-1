"""Компилятор JSON-AST из лабораторной №1 в код стековой машины."""

import argparse
import json
import sys


class Compiler:
    def __init__(self):
        self.code = []
        self.label_number = 0

    def emit(self, opcode, operand=None):
        self.code.append(opcode if operand is None else {opcode: operand})

    def new_label(self):
        label = f"L{self.label_number}"
        self.label_number += 1
        return label

    def expression(self, node):
        if not isinstance(node, dict):
            raise ValueError("Выражение должно быть JSON-объектом")
        if set(node) == {"const"} and type(node["const"]) is int:
            self.emit("CONST", node["const"])
        elif set(node) == {"var"} and isinstance(node["var"], str):
            self.emit("LD", node["var"])
        elif set(node) == {"binop", "left", "right"} and isinstance(node["binop"], str):
            self.expression(node["left"])
            self.expression(node["right"])
            self.emit("BINOP", node["binop"])
        else:
            raise ValueError("Неизвестный узел выражения")

    def statement(self, node):
        if node == "skip":
            return
        if not isinstance(node, dict) or len(node) != 1:
            raise ValueError("Оператор должен содержать ровно один ключ")
        opcode, value = next(iter(node.items()))
        if opcode == "seq":
            self.statement(value["left"])
            self.statement(value["right"])
        elif opcode == "assn" and isinstance(value["dst"], str):
            self.expression(value["src"])
            self.emit("ST", value["dst"])
        elif opcode == "read" and isinstance(value, str):
            self.emit("READ")
            self.emit("ST", value)
        elif opcode == "write":
            self.expression(value)
            self.emit("WRITE")
        elif opcode == "if":
            otherwise, done = self.new_label(), self.new_label()
            self.expression(value["cond"])
            self.emit("JZ", otherwise)
            self.statement(value["then"])
            self.emit("JMP", done)
            self.emit("LABEL", otherwise)
            self.statement(value["else"])
            self.emit("LABEL", done)
        elif opcode == "while":
            start, done = self.new_label(), self.new_label()
            self.emit("LABEL", start)
            self.expression(value["cond"])
            self.emit("JZ", done)
            self.statement(value["body"])
            self.emit("JMP", start)
            self.emit("LABEL", done)
        elif opcode == "do":
            start = self.new_label()
            self.emit("LABEL", start)
            self.statement(value["body"])
            self.expression(value["cond"])
            self.emit("JNZ", start)
        else:
            raise ValueError("Неизвестный узел оператора")


def compile_program(ast):
    compiler = Compiler()
    compiler.statement(ast)
    return compiler.code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать из stdin")
    args = parser.parse_args()
    try:
        source = sys.stdin if args.ast == "-" else open(args.ast, encoding="utf-8")
        with source:
            ast = json.load(source)
        json.dump(compile_program(ast), sys.stdout, ensure_ascii=False, indent=2)
        print()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
