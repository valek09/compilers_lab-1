import argparse
import json
import sys

from compiler import compile_program
from machine import run as run_machine


def run(ast, values=()):
    return run_machine(compile_program(ast), values)


def main():
    parser = argparse.ArgumentParser(description="Выполнить JSON-AST через стековую машину")
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать из stdin")
    parser.add_argument("--input", nargs="*", type=int, metavar="N", default=[],
                        help="целые значения для read в порядке чтения")
    args = parser.parse_args()

    try:
        if args.ast == "-":
            ast = json.load(sys.stdin)
        else:
            with open(args.ast, encoding="utf-8") as source:
                ast = json.load(source)
        result = run(ast, args.input)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2

    if result:
        print("; ".join(map(str, result)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
