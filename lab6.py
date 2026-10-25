"""Лабораторная №6: текст → AST → интерпретация или компиляция и машина."""

import argparse
import json
from pathlib import Path
import sys

import compiler
import interpreter
import program
from source_parser import parse_source, parse_values
from values import format_value, reference_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="файл программы; '-' — stdin")
    parser.add_argument("--mode", choices=("eval", "run", "compile", "ast"), default="run",
                        help="по умолчанию компиляция и запуск на машине")
    parser.add_argument("--input", default="", help='входные значения: 1, "text", [2,3], Pair(4,5)')
    parser.add_argument("--stats", action="store_true", help="число шагов машины в stderr")
    args = parser.parse_args()
    if args.stats and args.mode != "run":
        parser.error("--stats доступен только в режиме run")
    stats = {} if args.stats else None
    try:
        source = sys.stdin.read() if args.source == "-" else Path(args.source).read_text(encoding="utf-8")
        ast = parse_source(source)
        if args.mode in ("ast", "compile"):
            result = ast if args.mode == "ast" else compiler.compile_program(ast)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        inputs = parse_values(args.input)
        result = (interpreter.run(ast, inputs) if args.mode == "eval"
                  else program.run(ast, inputs, stats=stats))
        rendered = ", ".join(map(format_value, result))
    except RecursionError:
        print("Ошибка: превышена допустимая глубина вложенности", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(reference_error(error), file=sys.stderr)
        return 1
    except (OSError, SyntaxError, ValueError, TypeError, KeyError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2
    if result:
        print(rendered)
    if stats is not None:
        print(f"Шагов: {stats['steps']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
