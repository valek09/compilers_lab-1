import argparse
import json
import sys

import values as runtime
import patterns
from source_parser import parse_values


variables = {}
input_values = []
input_position = 0
output = []


apply_binop = runtime.binary

def eval_expr(node):
    if not isinstance(node, dict):
        raise ValueError("Выражение должно быть JSON-объектом")
    if set(node) == {"const"}:
        if type(node["const"]) is not int:
            raise ValueError("Константа должна быть целым числом")
        return node["const"]
    if set(node) == {"string"}:
        if not isinstance(node["string"], str):
            raise ValueError("Строковый литерал должен быть строкой")
        return bytearray(node["string"], "utf-8")
    if set(node) == {"array"}:
        if not isinstance(node["array"], list):
            raise ValueError("array должен содержать список выражений")
        return [eval_expr(item) for item in node["array"]]
    if set(node) == {"sexp", "args"}:
        if not isinstance(node["sexp"], str) or not isinstance(node["args"], list):
            raise ValueError("sexp требует строковый тег и список args")
        return runtime.Sexp(node["sexp"], [eval_expr(item) for item in node["args"]])
    if set(node) == {"length"}:
        return runtime.length(eval_expr(node["length"]))
    if set(node) == {"elem", "index"}:
        index = eval_expr(node["index"])
        return runtime.element(eval_expr(node["elem"]), index)
    if set(node) == {"var"}:
        name = node["var"]
        if not isinstance(name, str):
            raise ValueError("Имя переменной должно быть строкой")
        if name not in variables:
            raise RuntimeError(f"L0.State.Undefined_variable({json.dumps(name)})")
        return variables[name]
    if set(node) == {"binop", "left", "right"}:
        right = eval_expr(node["right"])
        left = eval_expr(node["left"])
        return apply_binop(node["binop"], left, right)
    raise ValueError("Неизвестный узел выражения")


def execute(node):
    global input_position

    if node == "skip":
        return
    if not isinstance(node, dict) or len(node) != 1:
        raise ValueError("Оператор должен содержать ровно один ключ")

    if "seq" in node:
        execute(node["seq"]["left"])
        execute(node["seq"]["right"])
    elif "assn" in node:
        assignment = node["assn"]
        if not isinstance(assignment["dst"], str):
            raise ValueError("Имя переменной должно быть строкой")
        variables[assignment["dst"]] = eval_expr(assignment["src"])
    elif "set" in node:
        assignment = node["set"]
        value = eval_expr(assignment["value"])
        index = eval_expr(assignment["idx"])
        container = eval_expr(assignment["dst"])
        runtime.set_element(container, index, value)
    elif "read" in node:
        if not isinstance(node["read"], str):
            raise ValueError("Имя переменной должно быть строкой")
        if input_position >= len(input_values):
            raise RuntimeError("L0.Stmt.No_input")
        variables[node["read"]] = input_values[input_position]
        input_position += 1
    elif "write" in node:
        output.append(eval_expr(node["write"]))
    elif "if" in node:
        branch = node["if"]
        if runtime.number(eval_expr(branch["cond"])) != 0:
            execute(branch["then"])
        else:
            execute(branch["else"])
    elif "switch" in node:
        switch = node["switch"]
        value = eval_expr(switch["scrutinee"])
        for branch in switch["branches"]:
            bindings = patterns.match(branch["pattern"], value)
            if bindings is None:
                continue
            missing = object()
            previous = {name: variables.get(name, missing) for name in bindings}
            variables.update(bindings)
            try:
                execute(branch["branch"])
            finally:
                for name, old in previous.items():
                    if old is missing:
                        variables.pop(name, None)
                    else:
                        variables[name] = old
            return
        raise RuntimeError(f"match failure on {runtime.format_value(value)}")
    elif "while" in node:
        loop = node["while"]
        while runtime.number(eval_expr(loop["cond"])) != 0:
            execute(loop["body"])
    elif "do" in node:
        loop = node["do"]
        while True:
            execute(loop["body"])
            if runtime.number(eval_expr(loop["cond"])) == 0:
                break
    else:
        raise ValueError("Неизвестный узел оператора")


def run(ast, values=()):
    global variables, input_values, input_position, output

    variables = {}
    input_values = runtime.normalize_inputs(values)
    input_position = 0
    output = []
    execute(ast)
    return output.copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать AST из stdin")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--input", nargs="*", type=int, metavar="N",
                        help="целые значения для read в порядке чтения")
    inputs.add_argument("--values", help="значения read: числа, строки, массивы, S-выражения")
    args = parser.parse_args()

    try:
        if args.ast == "-":
            ast = json.load(sys.stdin)
        else:
            with open(args.ast, encoding="utf-8") as source:
                ast = json.load(source)
        values = parse_values(args.values) if args.values is not None else args.input
        if values is None:
            values = []
            if args.ast != "-" and not sys.stdin.isatty():
                values = [int(token) for token in sys.stdin.read().split()]
    except (OSError, ValueError, SyntaxError, RecursionError) as error:
        print(f"Ошибка входных данных: {error}", file=sys.stderr)
        return 2

    exit_code = 0
    try:
        run(ast, values)
    except RecursionError:
        print("Ошибка AST: превышена допустимая глубина вложенности", file=sys.stderr)
        exit_code = 2
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        exit_code = 1
    except (ValueError, KeyError, TypeError) as error:
        print(f"Ошибка AST: {error}", file=sys.stderr)
        exit_code = 2
    if output:
        try:
            print("; ".join(map(runtime.format_value, output)))
        except (RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
