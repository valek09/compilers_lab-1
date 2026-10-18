"""Lab 5 array, string and reference semantics."""

import unittest

import lab5


class Lab5Tests(unittest.TestCase):
    def test_nested_list_from_class_example(self):
        source = """{
            read(list);
            while (list[0]) {
                write(list[1]);
                list = list[2];
            }
        }"""
        self.assertEqual(lab5.run(source, [[1, 1, [1, 2, [1, 3, [0]]]]]), [1, 2, 3])

    def test_array_aliasing_and_nested_assignment(self):
        source = """{
            a = [[1], 2];
            b = a;
            b[0][0] = 9;
            write(a[0][0]);
            b[1] += 3;
            write(a);
        }"""
        self.assertEqual(lab5.run(source), [9, [[9], 5]])

    def test_arrays_strings_and_length(self):
        source = """{
            a = ["a", "b"] + ["c"];
            s = "ab" + "cd";
            write(a.length);
            write(a[2]);
            write(s.length);
            write(s[1]);
            write(s);
        }"""
        self.assertEqual(lab5.run(source), [3, "c", 4, "b", "abcd"])

    def test_number_and_array_are_distinct(self):
        self.assertEqual(lab5.run("{ write(1 == [1]); write([1] != 1); }"), [0, 1])
        for source in ("{ write([1] + 1); }", "{ write([1] * 2); }",
                       "{ if ([1]) skip; }", "{ write(1.length); }"):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                lab5.run(source)

    def test_input_and_for_loop(self):
        values = lab5.parse_input('[1, 2] "hi" 3')
        source = """{
            read(a); read(s); read(n);
            for (i = 0; i < n; i = i + 1;) write(a[0] + i);
            write(s);
        }"""
        self.assertEqual(lab5.run(source, values), [1, 2, 3, "hi"])

    def test_invalid_index_and_immutable_string(self):
        for source in ("{ a = []; write(a[0]); }", "{ a = [1]; a[-1] = 2; }",
                       '{ s = "hi"; s[0] = "H"; }'):
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                lab5.run(source)

    def test_array_equality_uses_identity(self):
        source = "{ a = [1]; b = a; c = [1]; write(a == b); write(a == c); }"
        self.assertEqual(lab5.run(source), [1, 0])

    def test_write_keeps_value_at_output_time(self):
        self.assertEqual(lab5.run("{ a = [1]; write(a); a[0] = 2; write(a); }"),
                         [[1], [2]])

    def test_comments_and_output_format(self):
        source = '{ -- line\n write([1, "x"]); (* block *) write("hi"); }'
        self.assertEqual(
            "; ".join(map(lab5.formatted, lab5.run(source))),
            '[1, "x"]; "hi"',
        )


if __name__ == "__main__":
    unittest.main()
