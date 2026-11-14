"""Чтение тестового графа и рекурсивный обход зависимостей DFS."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple


PACKAGE_LETTER_PATTERN = re.compile(r"[A-Z]+")
GRAPH_SEPARATOR = "->"
EXPECTED_SEPARATOR_COUNT = 1
EMPTY_NEIGHBORS = ("", "-")


class GraphError(ValueError):
    """Ошибка в исходном графе или его обходе."""


@dataclass(frozen=True)
class GraphResult:
    """Результат DFS: вершины, их связи и найденные циклы."""

    edges: Dict[str, Tuple[str, ...]]
    cycles: Tuple[Tuple[str, ...], ...]

    @property
    def nodes_count(self) -> int:
        """Количество достижимых вершин."""
        return len(self.edges)

    @property
    def edges_count(self) -> int:
        """Количество направленных связей между вершинами."""
        return sum(len(items) for items in self.edges.values())


def _check_letter(value: str, line: int) -> None:
    """Требовать имена пакетов из заглавных латинских букв."""
    if PACKAGE_LETTER_PATTERN.fullmatch(value) is None:
        raise GraphError(f"строка {line}: неверное имя пакета '{value}'")


def _parse_line(text: str, line: int) -> Tuple[str, Tuple[str, ...]]:
    """Разобрать строку A -> B, C или A -> без зависимостей."""
    if text.count(GRAPH_SEPARATOR) != EXPECTED_SEPARATOR_COUNT:
        raise GraphError(f"строка {line}: ожидается A -> B, C")
    source, remainder = text.split(GRAPH_SEPARATOR)
    source = source.strip()
    _check_letter(source, line)
    names = remainder.strip()
    if names in EMPTY_NEIGHBORS:
        return source, ()
    targets = tuple(item.strip() for item in names.split(","))
    for name in targets:
        _check_letter(name, line)
    return source, tuple(dict.fromkeys(targets))


def read_test_graph(path: Path) -> Dict[str, Tuple[str, ...]]:
    """Загрузить текстовый тестовый репозиторий из файла."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise GraphError(f"не удалось прочитать граф: {exc}") from exc
    graph = {}
    for number, text in enumerate(lines, start=1):
        if not text.strip():
            continue
        name, targets = _parse_line(text, number)
        if name in graph:
            raise GraphError(f"строка {number}: повтор вершины {name}")
        graph[name] = targets
    if not graph:
        raise GraphError("тестовый граф пуст")
    for targets in tuple(graph.values()):
        for name in targets:
            graph.setdefault(name, ())
    return graph


def dfs_graph(
    root: str, get_neighbors: Callable[[str], Tuple[str, ...]],
) -> GraphResult:
    """Обойти достижимые узлы DFS и обнаружить обратные рёбра."""
    edges = {}
    state = {}
    stack: List[str] = []
    cycles = []

    def visit(node: str) -> None:
        """Рекурсивно обойти соседей текущей вершины."""
        state[node] = "active"
        stack.append(node)
        targets = tuple(dict.fromkeys(get_neighbors(node)))
        edges[node] = targets
        for target in targets:
            if state.get(target) == "active":
                cycles.append(tuple(stack[stack.index(target):] + [target]))
            elif target not in state:
                visit(target)
        stack.pop()
        state[node] = "done"

    visit(root)
    return GraphResult(edges, tuple(cycles))
