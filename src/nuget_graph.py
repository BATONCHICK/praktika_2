"""Построение транзитивного графа пакетов NuGet с помощью DFS."""

import json
from dataclasses import dataclass
from time import monotonic
from typing import Dict, Optional, Tuple
from urllib.parse import quote

from .frameworks import selected_groups
from .graph import GraphError, GraphResult, dfs_graph
from .nuget import (
    Dependency, DependencyGroup, NuGetError, _find_package_base,
    _manifest_url, _parse_manifest, _read_url,
)
from .versions import select_version


@dataclass(frozen=True)
class GraphOptions:
    """Платформа и ограничения на длительность обхода репозитория."""

    framework: str = "net6.0"
    max_nodes: int = 80
    max_seconds: int = 30


class NuGetSource:
    """Источник соседей графа с кешированием запросов NuGet V3."""

    def __init__(self, repository: str, options: GraphOptions):
        """Подготовить загрузчик и предельный срок обхода."""
        self.repository = repository
        self.options = options
        self.base: Optional[str] = None
        self.deadline = monotonic() + options.max_seconds
        self.versions: Dict[str, Tuple[str, ...]] = {}
        self.manifests: Dict[str, Tuple[DependencyGroup, ...]] = {}
        self.visits = 0

    def check_limits(self) -> None:
        """Прекратить работу, если превышено число пакетов или время."""
        if monotonic() >= self.deadline:
            raise GraphError("истекло время обхода графа NuGet")
        if self.visits >= self.options.max_nodes:
            raise GraphError("превышен лимит числа пакетов")

    def fetch(self, url: str) -> bytes:
        """Получить ответ сервера с проверкой общего срока обхода."""
        self.check_time()
        data = _read_url(url)
        self.check_time()
        return data

    def check_time(self) -> None:
        """Проверить только срок, не ограничивая число HTTP-запросов."""
        if monotonic() >= self.deadline:
            raise GraphError("истекло время обхода графа NuGet")

    def package_base(self) -> str:
        """Определить ресурс Flat Container из индекса репозитория."""
        if self.base is None:
            self.base = _find_package_base(self.fetch(self.repository))
        return self.base

    def get_versions(self, name: str) -> Tuple[str, ...]:
        """Прочитать и сохранить доступные версии пакета."""
        key = name.lower()
        if key not in self.versions:
            url = f"{self.package_base()}/{quote(key, safe='')}/index.json"
            data = self.fetch(url)
            self.versions[key] = self.parse_versions(data)
        return self.versions[key]

    @staticmethod
    def parse_versions(data: bytes) -> Tuple[str, ...]:
        """Проверить JSON-ответ со списком версий пакета."""
        try:
            payload = json.loads(data.decode("utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise NuGetError("некорректный JSON списка версий") from exc
        if not isinstance(payload, dict):
            raise NuGetError("неверный список версий пакета")
        values = payload.get("versions")
        if not isinstance(values, list):
            raise NuGetError("не найден список версий пакета")
        if not all(isinstance(item, str) for item in values):
            raise NuGetError("список версий содержит недопустимые значения")
        return tuple(values)

    def get_manifest(self, name: str, version: str):
        """Кешировать XML-манифест для конкретной версии пакета."""
        node = f"{name.lower()}@{version.lower()}"
        if node not in self.manifests:
            url = _manifest_url(self.package_base(), name, version)
            self.manifests[node] = _parse_manifest(self.fetch(url))
        return self.manifests[node]

    def neighbors(self, node: str) -> Tuple[str, ...]:
        """Возвратить прямых соседей узла выбранной платформы."""
        self.check_limits()
        self.visits += 1
        print(f"DFS: пакет {self.visits} — {node}", flush=True)
        package, version = node.rsplit("@", maxsplit=1)
        groups = selected_groups(
            self.get_manifest(package, version), self.options.framework,
        )
        dependencies = (dep for group in groups for dep in group.dependencies)
        return tuple(dict.fromkeys(self.resolve(dep) for dep in dependencies))

    def resolve(self, dependency: Dependency) -> str:
        """Выбрать подходящую версию одной прямой зависимости."""
        versions = self.get_versions(dependency.name)
        version = select_version(versions, dependency.version)
        return f"{dependency.name.lower()}@{version.lower()}"


def build_nuget_graph(
    repository: str, package: str, version: str, options: GraphOptions,
    root_groups: Optional[Tuple[DependencyGroup, ...]] = None,
) -> GraphResult:
    """Рекурсивно построить граф NuGet из пакета заданной версии."""
    source = NuGetSource(repository, options)
    root = f"{package.lower()}@{version.lower()}"
    if root_groups is not None:
        source.manifests[root] = root_groups
    return dfs_graph(root, source.neighbors)
