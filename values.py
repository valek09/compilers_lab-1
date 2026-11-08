import json


class Sexp:
    def __init__(self, tag, args):
        if not isinstance(tag, str) or not isinstance(args, list):
            raise ValueError("Sexp требует строковый тег и список полей")
        self.tag = tag
        self.args = args


def normalize_inputs(inputs):
    memo = {}

    def convert(value):
        if type(value) is int:
            return value
        if isinstance(value, bytearray):
            if id(value) not in memo:
                memo[id(value)] = value.copy()
            return memo[id(value)]
        if isinstance(value, str):
            return bytearray(value, "utf-8")
        if isinstance(value, Sexp):
            if id(value) not in memo:
                result = Sexp(value.tag, [])
                memo[id(value)] = result
                result.args.extend(convert(item) for item in value.args)
            return memo[id(value)]
        if isinstance(value, list):
            if id(value) not in memo:
                result = []
                memo[id(value)] = result
                result.extend(convert(item) for item in value)
            return memo[id(value)]
        raise ValueError("Вход: ожидается число, строка, массив или S-выражение")

    return [convert(value) for value in inputs]


def format_value(value, active=None):
    if type(value) is int:
        return str(value)
    if isinstance(value, bytearray):
        return '"' + value.decode("utf-8", errors="replace") + '"'
    if active is None:
        active = set()
    if id(value) in active:
        raise RuntimeError("Cyclic_value: невозможно вывести циклическое значение")
    active = active | {id(value)}
    if isinstance(value, list):
        return "[" + ", ".join(format_value(item, active) for item in value) + "]"
    if isinstance(value, Sexp):
        if value.tag == "nil" and not value.args:
            return "{}"
        if value.tag == "cons" and len(value.args) == 2:
            parts, seen = [], set()
            current = value
            while isinstance(current, Sexp) and current.tag == "cons" and len(current.args) == 2:
                if id(current) in seen:
                    raise RuntimeError("Cyclic_value: невозможно вывести циклический список")
                seen.add(id(current))
                parts.append(format_value(current.args[0], active | seen))
                current = current.args[1]
            if not isinstance(current, Sexp) or current.tag != "nil" or current.args:
                raise RuntimeError("Invalid_list: хвост списка должен быть nil или cons")
            return "{" + ", ".join(parts) + "}"
        if not value.args:
            return value.tag
        return value.tag + " (" + ", ".join(format_value(item, active) for item in value.args) + ")"
    raise ValueError("Неизвестный тип значения")


def number(value):
    if type(value) is not int:
        raise RuntimeError(f'ERROR: integer value expected but "{format_value(value)}" given')
    return value


def length(value):
    if isinstance(value, Sexp):
        return len(value.args)
    if isinstance(value, (list, bytearray)):
        return len(value)
    raise RuntimeError(f'ERROR: array/string/sexp value expected but "{format_value(value)}" given')


def checked_index(container, index):
    index = number(index)
    if not isinstance(container, (list, bytearray, Sexp)):
        raise RuntimeError(f'ERROR: array/string value expected but "{format_value(container)}" is given')
    size = length(container)
    if not 0 <= index < size:
        raise RuntimeError(f"ERROR: index {index} is out of bounds [0, {size})")
    return index


def element(container, index):
    index = checked_index(container, index)
    return (container.args if isinstance(container, Sexp) else container)[index]


def set_element(container, index, value):
    index = checked_index(container, index)
    if isinstance(container, bytearray):
        value = number(value)
        if not 0 <= value <= 255:
            raise RuntimeError('Invalid_argument("Char.chr")')
    (container.args if isinstance(container, Sexp) else container)[index] = value


def compare(op, left, right, active=None):
    if type(left) is int and type(right) is int:
        return (left > right) - (left < right)
    if isinstance(left, bytearray) and isinstance(right, bytearray):
        return (left > right) - (left < right)
    if active is None:
        active = set()
    pair = (id(left), id(right))
    if pair in active:
        raise RuntimeError("Stack overflow")
    active = active | {pair}
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return (len(left) > len(right)) - (len(left) < len(right))
        for a, b in zip(left, right):
            result = compare(op, a, b, active)
            if result:
                return result
        return 0
    if isinstance(left, Sexp) and isinstance(right, Sexp):
        if left.tag != right.tag:
            return (left.tag > right.tag) - (left.tag < right.tag)
        if len(left.args) != len(right.args):
            return (len(left.args) > len(right.args)) - (len(left.args) < len(right.args))
        for a, b in zip(left.args, right.args):
            result = compare(op, a, b, active)
            if result:
                return result
        return 0
    error_op = {"==": "=", "!=": "<>"}.get(op, op)
    raise RuntimeError(f'ERROR: binary operator "{error_op}" is applied to '
                       f'{format_value(left)} and {format_value(right)}')


def binary(op, left, right):
    if op == ":":
        return Sexp("cons", [left, right])
    if op in ("==", "!=", "<", "<=", ">", ">="):
        result = compare(op, left, right)
        return int({"==": result == 0, "!=": result != 0, "<": result < 0,
                    "<=": result <= 0, ">": result > 0, ">=": result >= 0}[op])
    if op not in ("+", "-", "*", "/", "%", "&&", "!!"):
        raise ValueError(f"Неизвестная бинарная операция: {op}")
    right, left = number(right), number(left)
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
        return quotient if op == "/" else left - quotient * right
    if op == "&&":
        return int(left != 0 and right != 0)
    return int(left != 0 or right != 0)


def reference_error(error):
    message = str(error)
    if message == "L0.Stmt.No_input":
        return "ERROR: input exhausted"
    if message == "Stack_underflow":
        return "ERROR: stack exhausted"
    prefix = "L0.State.Undefined_variable("
    if message.startswith(prefix) and message.endswith(")"):
        name = json.loads(message[len(prefix):-1])
        return f'ERROR: variable "{name}" is undefined'
    return message
