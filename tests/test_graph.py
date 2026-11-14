"""Тесты текстового графа, рекурсивного DFS и циклических зависимостей."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src.graph import GraphError, dfs_graph, read_test_graph
from src.main import main
from tests.test_config import GOOD_SETTINGS


class GraphTests(unittest.TestCase):
    """Проверить обход достижимых узлов и ошибки тестового графа."""

    def test_cycle(self):
        """DFS обнаруживает цикл, но не зацикливается сам."""
        graph = {"A": ("B", "C"), "B": ("D",),
                 "C": ("D",), "D": ("A",)}
        result = dfs_graph("A", graph.__getitem__)
        self.assertEqual(result.nodes_count, 4)
        self.assertEqual(result.edges_count, 5)
        self.assertEqual(result.cycles, (("A", "B", "D", "A"),))

    def test_diamond(self):
        """Общая зависимость в двух ветках не считается циклом."""
        graph = {"A": ("B", "C"), "B": ("D",),
                 "C": ("D",), "D": ()}
        result = dfs_graph("A", graph.__getitem__)
        self.assertEqual(result.nodes_count, 4)
        self.assertEqual(result.edges_count, 4)
        self.assertEqual(result.cycles, ())

    def test_isolated_node(self):
        """Для отдельного пакета граф состоит из одной вершины."""
        result = dfs_graph("A", lambda _: ())
        self.assertEqual(result.edges, {"A": ()})

    def test_self_cycle(self):
        """Петля A -> A также является циклом."""
        result = dfs_graph("A", lambda _: ("A",))
        self.assertEqual(result.cycles, (("A", "A"),))

    def test_multiple_cycles(self):
        """Обход находит несколько обратных рёбер."""
        graph = {"A": ("B", "C"), "B": ("A",), "C": ("A",)}
        result = dfs_graph("A", graph.__getitem__)
        self.assertEqual(len(result.cycles), 2)

    def test_unreachable_node(self):
        """Недостижимая от выбранного пакета вершина не включается."""
        graph = {"A": ("B",), "B": (), "Z": ("Z",)}
        result = dfs_graph("A", graph.__getitem__)
        self.assertEqual(result.nodes_count, 2)
        self.assertEqual(result.cycles, ())

    def test_duplicate_edge(self):
        """Повтор одной связи не увеличивает количество рёбер."""
        result = dfs_graph("A", lambda node: ("B", "B")
                           if node == "A" else ())
        self.assertEqual(result.edges_count, 1)

    def test_parser_implicit_leaf(self):
        """Пакет справа от стрелки тоже становится вершиной."""
        graph = self.read_graph("A -> B, C\nB ->\n")
        self.assertEqual(graph["C"], ())

    def test_parser_empty_leaf(self):
        """Пустое множество соседей записывается после стрелки."""
        graph = self.read_graph("A ->\n")
        self.assertEqual(graph, {"A": ()})

    def test_parser_deduplicates(self):
        """Повтор зависимости внутри строки сокращается."""
        graph = self.read_graph("A -> B, B\n")
        self.assertEqual(graph["A"], ("B",))

    def test_invalid_case(self):
        """В тестовом репозитории разрешены только заглавные буквы."""
        with self.assertRaises(GraphError):
            self.read_graph("A -> a\n")

    def test_bad_separator(self):
        """Проверить некорректную стрелку и повтор разделителя."""
        for text in ("A: B", "A -> B -> C"):
            with self.subTest(text=text), self.assertRaises(GraphError):
                self.read_graph(text)

    def test_trailing_comma(self):
        """Пустое имя зависимости не допускается."""
        with self.assertRaises(GraphError):
            self.read_graph("A -> B, ")

    def test_duplicate_definition(self):
        """Нельзя дважды объявлять одну вершину слева."""
        with self.assertRaisesRegex(GraphError, "повтор вершины"):
            self.read_graph("A -> B\nA -> C")

    def test_empty_graph(self):
        """Пустой файл нельзя считать графом зависимостей."""
        with self.assertRaises(GraphError):
            self.read_graph("\n   \n")

    def test_missing_graph_file(self):
        """Отсутствующий файл даёт понятную ошибку."""
        with self.assertRaises(GraphError):
            read_test_graph(Path("/no/such/graph/file.txt"))

    def test_cli_cycle(self):
        """CLI читает граф относительно CSV и сообщает о цикле."""
        code, output, errors = self.run_cli("A -> B\nB -> A\n")
        self.assertEqual(code, 0)
        self.assertIn("Цикл: A -> B -> A", output)
        self.assertEqual(errors, "")

    def test_cli_missing_root(self):
        """Неверный выбранный пакет не скрывает ошибку."""
        code, _, errors = self.run_cli("B -> C\n")
        self.assertEqual(code, 1)
        self.assertIn("отсутствует A", errors)

    @staticmethod
    def read_graph(contents):
        """Создать временный тестовый граф и загрузить его."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "graph.txt"
            path.write_text(contents, encoding="utf-8")
            return read_test_graph(path)

    @staticmethod
    def run_cli(contents):
        """Запустить CLI на временном тестовом файле и CSV."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "graph.txt").write_text(contents, encoding="utf-8")
            values = dict(GOOD_SETTINGS)
            values.update({"package_name": "A", "test_mode": "true",
                           "repository": "graph.txt"})
            config = path / "config.csv"
            config.write_text("key,value\n" + "".join(
                f"{key},{value}\n" for key, value in values.items()
            ), encoding="utf-8")
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                status = main(["--config", str(config)])
            return status, output.getvalue(), errors.getvalue()


if __name__ == "__main__":
    unittest.main()
