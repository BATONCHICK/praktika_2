"""Автономная проверка транзитивного обхода реальных типов NuGet."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.graph import GraphError
from src.nuget import Dependency, DependencyGroup, NuGetError
from src.nuget_graph import GraphOptions, NuGetSource, build_nuget_graph


PACKAGE_BASE = "https://example.test/flat"
REPOSITORY = "https://example.test/v3/index.json"
RESOURCE_INDEX = json.dumps({"resources": [
    {"@type": "PackageBaseAddress/3.0.0", "@id": PACKAGE_BASE}
]}).encode("utf-8")
VERSION_LIST = b'{"versions": ["1.0.0"]}'


def _manifest(*packages):
    """Создать корректный XML с прямыми зависимостями для net6.0."""
    dependencies = "".join(
        f'<dependency id="{name}" version="[1.0.0]" />'
        for name in packages
    )
    text = ('<package><metadata><dependencies>'
            '<group targetFramework="net6.0">'
            + dependencies + '</group></dependencies></metadata></package>')
    return text.encode("utf-8")


def _urls():
    """Подготовить фиктивные ответы по адресам NuGet Flat Container."""
    results = {REPOSITORY: RESOURCE_INDEX}
    for name, dependencies in (("a", ("B", "C")),
                               ("b", ("D",)),
                               ("c", ("D",)),
                               ("d", ("A",))):
        results[f"{PACKAGE_BASE}/{name}/index.json"] = VERSION_LIST
        results[f"{PACKAGE_BASE}/{name}/1.0.0/{name}.nuspec"] = _manifest(
            *dependencies
        )
    return results


class NuGetGraphTests(unittest.TestCase):
    """Проверить рекурсивную загрузку, кеш и ограничение обхода."""

    def test_recursive_cycle(self):
        """В настоящем протоколе DFS выявляет цикл из четырёх пакетов."""
        replies = _urls()
        with patch("src.nuget_graph._read_url",
                   side_effect=replies.__getitem__):
            with redirect_stdout(io.StringIO()):
                result = build_nuget_graph(REPOSITORY, "A", "1.0.0",
                                           GraphOptions())
        self.assertEqual(result.nodes_count, 4)
        self.assertEqual(result.edges_count, 5)
        self.assertEqual(result.cycles, (("a@1.0.0", "b@1.0.0",
                                          "d@1.0.0", "a@1.0.0"),))

    def test_cache_manifest_and_versions(self):
        """Общий узел D не скачивается повторно для двух ветвей."""
        replies = _urls()
        with patch("src.nuget_graph._read_url",
                   side_effect=replies.__getitem__) as mocked:
            with redirect_stdout(io.StringIO()):
                build_nuget_graph(REPOSITORY, "A", "1.0.0", GraphOptions())
        calls = [args.args[0] for args in mocked.call_args_list]
        self.assertEqual(calls.count(
            f"{PACKAGE_BASE}/d/1.0.0/d.nuspec"
        ), 1)
        self.assertEqual(calls.count(f"{PACKAGE_BASE}/d/index.json"), 1)

    def test_reuses_root_manifest(self):
        """Корневой манифест из второго этапа не скачивается заново."""
        groups = (DependencyGroup("net6.0", ()),)
        source = _urls()
        with patch("src.nuget_graph._read_url",
                   side_effect=source.__getitem__):
            with redirect_stdout(io.StringIO()):
                graph = build_nuget_graph(
                    REPOSITORY, "A", "1.0.0", GraphOptions(), groups,
                )
        self.assertEqual(graph.nodes_count, 1)

    def test_limit_nodes(self):
        """Большой граф останавливается с ошибкой, не обрезаясь молча."""
        with patch("src.nuget_graph._read_url",
                   side_effect=_urls().__getitem__):
            with redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(GraphError, "лимит"):
                    build_nuget_graph(REPOSITORY, "A", "1.0.0",
                                      GraphOptions(max_nodes=2))

    def test_deadline(self):
        """Истечение общего времени приводит к явной ошибке."""
        with patch("src.nuget_graph.monotonic", side_effect=(0, 100)):
            source = NuGetSource(REPOSITORY, GraphOptions(max_seconds=1))
            with self.assertRaisesRegex(GraphError, "время"):
                source.check_time()

    def test_bad_json_versions(self):
        """Некорректный список версий не попадает в обход."""
        with self.assertRaises(NuGetError):
            NuGetSource.parse_versions(b"not json")
        with self.assertRaises(NuGetError):
            NuGetSource.parse_versions(b'{"versions": [123]}')

    def test_version_not_available(self):
        """Отсутствие нужной версии зависимости приводит к ошибке."""
        source = NuGetSource(REPOSITORY, GraphOptions())
        source.versions["b"] = ("1.0.0",)
        with self.assertRaisesRegex(NuGetError, "нет версии"):
            source.resolve(Dependency("B", "[2.0.0]"))


if __name__ == "__main__":
    unittest.main()
