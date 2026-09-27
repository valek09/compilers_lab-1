"""Стековая виртуальная машина для языка инструкций лабораторной работы №2.

Программа задаётся JSON-массивом. Инструкции без операнда записываются строкой
(`"READ"`, `"WRITE"`), а с операндом — объектом с одним ключом
(`{"CONST": 10}`).
"""

import argparse
import json
import sys

from interpreter import apply_binop


ARGUMENT_INSTRUCTIONS = {"LD", "ST", "CONST", "BINOP", "LABEL", "JMP", "JZ", "JNZ"}
NO_ARGUMENT_INSTRUCTIONS = {"READ", "WRITE"}


def decode_program(program):
    """Проверяет JSON-представление и возвращает список (opcode, operand)."""
    if not isinstance(program, list):
        raise ValueError("Программа должна быть JSON-массивом")

    instructions = []
    labels = {}
    for position, item in enumerate(program):
        if isinstance(item, str):
            opcode, operand = item, None
        elif isinstance(item, dict) and len(item) == 1:
            opcode, operand = next(iter(item.items()))
        else:
            raise ValueError(f"Некорректная инструкция #{position}")
        if opcode in NO_ARGUMENT_INSTRUCTIONS:
            if operand is not None:
                raise ValueError(f"Инструкция {opcode} не принимает операнд")
        elif opcode in ARGUMENT_INSTRUCTIONS:
            if opcode == "CONST" and type(operand) is not int:
                raise ValueError("Операнд CONST должен быть целым числом")
            if opcode != "CONST" and not isinstance(operand, str):
                raise ValueError(f"Операнд {opcode} должен быть строкой")
        else:
            raise ValueError(f"Неизвестная инструкция: {opcode}")
        if opcode == "LABEL":
            if operand in labels:
                raise ValueError(f"Повторная метка: {operand}")
            labels[operand] = position
        instructions.append((opcode, operand))

    for opcode, operand in instructions:
        if opcode in {"JMP", "JZ", "JNZ"} and operand not in labels:
            raise ValueError(f"Неизвестная метка: {operand}")
    return instructions, labels


def run(program, values=()):
    """Исполняет программу и возвращает значения, переданные в WRITE."""
    instructions, labels = decode_program(program)
    if any(type(value) is not int for value in values):
        raise ValueError("Входные значения должны быть целыми числами")

    variables, stack, output = {}, [], []
    input_values, input_position, pc = list(values), 0, 0

    def pop():
        if not stack:
            raise RuntimeError("Stack_underflow")
        return stack.pop()

    while pc < len(instructions):
        opcode, operand = instructions[pc]
        pc += 1
        if opcode == "READ":
            if input_position >= len(input_values):
                raise RuntimeError("L0.Stmt.No_input")
            stack.append(input_values[input_position])
            input_position += 1
        elif opcode == "WRITE":
            output.append(pop())
        elif opcode == "LD":
            if operand not in variables:
                raise RuntimeError(f"L0.State.Undefined_variable({json.dumps(operand)})")
            stack.append(variables[operand])
        elif opcode == "ST":
            variables[operand] = pop()
        elif opcode == "CONST":
            stack.append(operand)
        elif opcode == "BINOP":
            right, left = pop(), pop()
            stack.append(apply_binop(operand, left, right))
        elif opcode == "JMP":
            pc = labels[operand]
        elif opcode == "JZ":
            if pop() == 0:
                pc = labels[operand]
        elif opcode == "JNZ":
            if pop() != 0:
                pc = labels[operand]
        # LABEL intentionally does nothing.
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", help="путь к JSON-программе; '-' — прочитать из stdin")
    parser.add_argument("--input", nargs="*", type=int, metavar="N", default=[],
                        help="целые значения для READ")
    args = parser.parse_args()
    try:
        source = sys.stdin if args.program == "-" else open(args.program, encoding="utf-8")
        with source:
            program = json.load(source)
        result = run(program, args.input)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    if result:
        print("; ".join(map(str, result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
