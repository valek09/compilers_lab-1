import argparse
import json
import sys

from compiler import compile_program
from machine import run as run_machine


def run(ast, values=(), *, stats=None):
    return run_machine(compile_program(ast), values, stats=stats)


def main():
    parser = argparse.ArgumentParser(description="Выполнить JSON-AST через стековую машину")
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать из stdin")
    parser.add_argument("--input", nargs="*", type=int, metavar="N", default=[],
                        help="целые значения для read в порядке чтения")
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
        result = run(ast, args.input, stats=stats)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2

    if result:
        print("; ".join(map(str, result)))
    if stats is not None:
        print(f"Шагов: {stats['steps']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
