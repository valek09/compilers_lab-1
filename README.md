# Лабораторные работы по компиляторам

`interpreter.py` исполняет JSON-AST напрямую. `compiler.py` переводит AST в инструкции стековой машины (SM), `machine.py` исполняет эти инструкции, а `program.py` запускает весь путь AST → SM → вывод одной командой.

```bash
python3 program.py ast.json --input 7 8
python3 compiler.py ast.json > sm.json
python3 machine.py sm.json --input 7 8
```

Вместо имени файла можно указать `-`, чтобы прочитать JSON из стандартного ввода. `read` потребляет числа из `--input` по порядку; `write` печатает их через `; `.

Проверка лабораторных:

```bash
python3 -m unittest discover -s tests
```
