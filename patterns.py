from values import Sexp


def match(pattern, value):
    bindings = {}

    def visit(node, current):
        if type(node) is int:
            return type(current) is int and node == current
        if isinstance(node, str):
            types = {"#int": int, "#string": bytearray, "#array": list, "#sexp": Sexp}
            if node in types:
                return type(current) is types[node]
            return isinstance(current, bytearray) and current == node.encode("utf-8")
        if not isinstance(node, dict):
            raise ValueError("Некорректный образец")
        if set(node) == {"wildcard"} and node["wildcard"] == []:
            return True
        if set(node) == {"bind"}:
            binding = node["bind"]
            if not isinstance(binding, dict) or set(binding) != {"name", "pattern"}:
                raise ValueError("Некорректная привязка образца")
            if not visit(binding["pattern"], current):
                return False
            bindings[binding["name"]] = current
            return True
        if set(node) == {"array"}:
            items = node["array"]
            return (isinstance(current, list) and isinstance(items, list)
                    and len(current) == len(items)
                    and all(visit(p, v) for p, v in zip(items, current)))
        if set(node) == {"sexp", "args"}:
            items = node["args"]
            return (isinstance(current, Sexp) and current.tag == node["sexp"]
                    and isinstance(items, list) and len(current.args) == len(items)
                    and all(visit(p, v) for p, v in zip(items, current.args)))
        raise ValueError("Некорректный образец")

    return bindings if visit(pattern, value) else None
