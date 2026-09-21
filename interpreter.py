import argparse
import json
import sys


variables = {}
input_values = []
input_position = 0
output = []


def apply_binop(op, left, right):
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op in ("/", "%"):
        if right == 0:
            raise RuntimeError("Division_by_zero")
        quotient = abs(left) // abs(right)
        if (left < 0) != (right < 0):
            quotient = -quotient
        if op == "/":
            return quotient
        return left - quotient * right
    if op == "==":
        return int(left == right)
    if op == "!=":
        return int(left != right)
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
    raise ValueError(f"Неизвестная бинарная операция: {op}")


def eval_expr(node):
    if not isinstance(node, dict):
        raise ValueError("Выражение должно быть JSON-объектом")
    if set(node) == {"const"}:
        if type(node["const"]) is not int:
            raise ValueError("Константа должна быть целым числом")
        return node["const"]
    if set(node) == {"var"}:
        name = node["var"]
        if not isinstance(name, str):
            raise ValueError("Имя переменной должно быть строкой")
        if name not in variables:
            raise RuntimeError(f"L0.State.Undefined_variable({json.dumps(name)})")
        return variables[name]
    if set(node) == {"binop", "left", "right"}:
        
        left = eval_expr(node["left"])
        right = eval_expr(node["right"])
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
        if eval_expr(branch["cond"]) != 0:
            execute(branch["then"])
        else:
            execute(branch["else"])
    elif "while" in node:
        loop = node["while"]
        while eval_expr(loop["cond"]) != 0:
            execute(loop["body"])
    elif "do" in node:
        loop = node["do"]
        while True:
            execute(loop["body"])
            if eval_expr(loop["cond"]) == 0:
                break
    else:
        raise ValueError("Неизвестный узел оператора")


def run(ast, values=()):
    global variables, input_values, input_position, output

    variables = {}
    input_values = list(values)
    input_position = 0
    output = []
    if any(type(value) is not int for value in input_values):
        raise ValueError("Входные значения должны быть целыми числами")
    execute(ast)
    return output.copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ast", help="путь к JSON-AST; '-' — прочитать AST из stdin")
    parser.add_argument("--input", nargs="*", type=int, metavar="N",
                        help="целые значения для read в порядке чтения")
    args = parser.parse_args()

    try:
        if args.ast == "-":
            ast = json.load(sys.stdin)
        else:
            with open(args.ast, encoding="utf-8") as source:
                ast = json.load(source)
        values = args.input
        if values is None:
            values = []
            if args.ast != "-" and not sys.stdin.isatty():
                values = [int(token) for token in sys.stdin.read().split()]
    except (OSError, ValueError, RecursionError) as error:
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
        print("; ".join(map(str, output)))
    return exit_code

if __name__ == "__main__":
    sys.exit(main())