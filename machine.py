"""Стековая виртуальная машина для языка инструкций лабораторной работы №2.

Программа задаётся JSON-массивом. Инструкции без операнда записываются строкой
(`"READ"`, `"WRITE"`), а с операндом — объектом с одним ключом
(`{"CONST": 10}`).
"""

import argparse
import json
import sys

import values as runtime
from source_parser import parse_machine, parse_values


ARGUMENT_INSTRUCTIONS = {"LD", "ST", "CONST", "BINOP", "LABEL", "JMP", "JZ", "JNZ",
                         "ARRAY", "STRING", "SEXP"}
NO_ARGUMENT_INSTRUCTIONS = {"READ", "WRITE", "LENGTH", "ELEM", "SET"}


def decode_program(program):
    """Возвращает исполняемые инструкции и адреса меток (без самих LABEL)."""
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
            if opcode in ("CONST", "ARRAY") and type(operand) is not int:
                raise ValueError(f"Операнд {opcode} должен быть целым числом")
            if opcode == "ARRAY" and operand < 0:
                raise ValueError("Размер ARRAY не может быть отрицательным")
            if opcode == "SEXP":
                if (not isinstance(operand, list) or len(operand) != 2
                        or not isinstance(operand[0], str) or type(operand[1]) is not int
                        or operand[1] < 0):
                    raise ValueError("SEXP требует [строковый тег, неотрицательное число полей]")
            elif opcode not in ("CONST", "ARRAY") and not isinstance(operand, str):
                raise ValueError(f"Операнд {opcode} должен быть строкой")
        else:
            raise ValueError(f"Неизвестная инструкция: {opcode}")
        if opcode == "LABEL":
            if operand in labels:
                raise ValueError(f"Повторная метка: {operand}")
            # Метка указывает на следующую команду и не требует шага VM.
            # Несколько меток подряд могут обозначать один и тот же адрес.
            labels[operand] = len(instructions)
        else:
            instructions.append((opcode, operand))

    for opcode, operand in instructions:
        if opcode in {"JMP", "JZ", "JNZ"} and operand not in labels:
            raise ValueError(f"Неизвестная метка: {operand}")
    return instructions, labels


def run(program, values=(), *, stats=None):

    if stats is not None:
        stats["steps"] = 0
    instructions, labels = decode_program(program)
    variables, stack, output = {}, [], []
    input_values, input_position, pc = runtime.normalize_inputs(values), 0, 0

    def pop():
        if not stack:
            raise RuntimeError("Stack_underflow")
        return stack.pop()

    def pop_many(count):
        if count > len(stack):
            raise RuntimeError("Stack_underflow")
        if count == 0:
            return []
        result = stack[-count:]
        del stack[-count:]
        return result

    while pc < len(instructions):
        opcode, operand = instructions[pc]
        pc += 1
        if stats is not None:
            stats["steps"] += 1
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
        elif opcode == "STRING":
            stack.append(bytearray(operand, "utf-8"))
        elif opcode == "ARRAY":
            stack.append(pop_many(operand))
        elif opcode == "SEXP":
            tag, count = operand
            stack.append(runtime.Sexp(tag, pop_many(count)))
        elif opcode == "LENGTH":
            stack.append(runtime.length(pop()))
        elif opcode == "ELEM":
            index, container = pop(), pop()
            stack.append(runtime.element(container, index))
        elif opcode == "SET":
            value, index, container = pop(), pop(), pop()
            runtime.set_element(container, index, value)
        elif opcode == "BINOP":
            right, left = pop(), pop()
            stack.append(runtime.binary(operand, left, right))
        elif opcode == "JMP":
            pc = labels[operand]
        elif opcode == "JZ":
            if runtime.number(pop()) == 0:
                pc = labels[operand]
        elif opcode == "JNZ":
            if runtime.number(pop()) != 0:
                pc = labels[operand]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", help="путь к JSON-программе; '-' — прочитать из stdin")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--input", nargs="*", type=int, metavar="N", default=[],
                        help="целые значения для READ")
    inputs.add_argument("--values", help="значения READ в синтаксисе языка")
    parser.add_argument("--text", action="store_true", help="читать текст команд вместо JSON")
    parser.add_argument("--stats", action="store_true",
                        help="после успешного выполнения вывести число шагов в stderr")
    args = parser.parse_args()
    stats = {} if args.stats else None
    try:
        source = sys.stdin if args.program == "-" else open(args.program, encoding="utf-8")
        with source:
            program = parse_machine(source.read()) if args.text else json.load(source)
        inputs = parse_values(args.values) if args.values is not None else args.input
        result = run(program, inputs, stats=stats)
        rendered = "; ".join(map(runtime.format_value, result))
    except (OSError, ValueError, SyntaxError, RecursionError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    if result:
        print(rendered)
    if stats is not None:
        print(f"Шагов: {stats['steps']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
