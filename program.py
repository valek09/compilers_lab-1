import argparse
import json
import sys

from compiler import compile_program
from machine import run as run_machine
from source_parser import parse_values
from values import format_value


def run(ast, values=(), *, stats=None):
    return run_machine(compile_program(ast), values, stats=stats)


def main():
    parser = argparse.ArgumentParser(description="Выполнить JSON-AST через стековую машину")
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать из stdin")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--input", nargs="*", type=int, metavar="N", default=[],
                        help="целые значения для read в порядке чтения")
    inputs.add_argument("--values", help="значения read в синтаксисе языка")
    parser.add_argument("--stats", action="store_true",
                        help="после успешного выполнения вывести число шагов в stderr")
    args = parser.parse_args()
    stats = {} if args.stats else None

    try:
        if args.ast == "-":
            ast = json.load(sys.stdin)
        else:
            with open(args.ast, encoding="utf-8") as source:
                ast = json.load(source)
        inputs = parse_values(args.values) if args.values is not None else args.input
        result = run(ast, inputs, stats=stats)
        rendered = "; ".join(map(format_value, result))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, SyntaxError, KeyError, TypeError, RecursionError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2

    if result:
        print(rendered)
    if stats is not None:
        print(f"Шагов: {stats['steps']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
