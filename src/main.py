"""Консольное приложение для анализа графа зависимостей NuGet."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from .config import Config, ConfigError, load_config
from .graph import GraphError, GraphResult, dfs_graph, read_test_graph
from .nuget import DependencyGroup, NuGetError, get_direct_dependencies
from .nuget_graph import GraphOptions, build_nuget_graph


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
MINIMUM_LIMIT = 1


def _print_config(config: Config) -> None:
    """Вывести настройки CSV для совместимости с первым этапом."""
    print(f"package_name = {config.package_name}")
    print(f"repository = {config.repository}")
    print(f"test_mode = {str(config.test_mode).lower()}")
    print(f"package_version = {config.package_version}")
    print(f"output_file = {config.output_file}")


def _print_dependencies(
    groups: Tuple[DependencyGroup, ...], config: Config,
) -> None:
    """Показать прямые зависимости с учётом целевой платформы."""
    print(f"\nПрямые зависимости {config.package_name} "
          f"(версия {config.package_version}):")
    if not groups:
        print("  Прямых зависимостей нет.")
    for group in groups:
        print(f"\n[{group.framework}]")
        if not group.dependencies:
            print("  Прямых зависимостей нет.")
        for dependency in group.dependencies:
            print(f"  - {dependency.name} ({dependency.version})")


def _print_graph(root: str, graph: GraphResult) -> None:
    """Напечатать рёбра, количество узлов и циклы графа."""
    print(f"\nГраф зависимостей от {root} (DFS):")
    for node, neighbors in graph.edges.items():
        print(f"  {node} -> {', '.join(neighbors) if neighbors else '—'}")
    print(f"\nУзлов: {graph.nodes_count}, рёбер: {graph.edges_count}")
    if not graph.cycles:
        print("Циклов не обнаружено.")
    else:
        print(f"Найдено циклов: {len(graph.cycles)}")
        for cycle in graph.cycles:
            print(f"  Цикл: {' -> '.join(cycle)}")


def _run_test(config: Config, config_file: Path) -> None:
    """Применить DFS к локальному графу из заглавных латинских букв."""
    file_path = Path(config.repository).expanduser()
    if not file_path.is_absolute():
        file_path = config_file.parent / file_path
    graph = read_test_graph(file_path)
    if config.package_name not in graph:
        raise GraphError(f"в графе отсутствует {config.package_name}")
    result = dfs_graph(config.package_name, graph.__getitem__)
    _print_graph(config.package_name, result)


def _run_real(config: Config, options: GraphOptions) -> None:
    """Получить прямые зависимости и полный транзитивный граф NuGet."""
    groups = get_direct_dependencies(
        config.repository, config.package_name, config.package_version,
    )
    _print_dependencies(groups, config)
    print(f"\nТранзитивный граф для платформы {options.framework}:")
    result = build_nuget_graph(
        config.repository, config.package_name, config.package_version,
        options, root_groups=groups,
    )
    root = f"{config.package_name.lower()}@{config.package_version.lower()}"
    _print_graph(root, result)


def _create_parser() -> argparse.ArgumentParser:
    """Описать доступные параметры командной строки."""
    parser = argparse.ArgumentParser(
        description="NuGet: прямые и транзитивные зависимости, этап 3"
    )
    parser.add_argument("--config", default="config.csv")
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--framework", default="net6.0")
    parser.add_argument("--max-nodes", type=int, default=80)
    parser.add_argument("--max-seconds", type=int, default=30)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Выполнить проверку CSV, рекурсивный DFS либо сообщить об ошибке."""
    args = _create_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        _print_config(config)
        if args.config_only:
            return EXIT_SUCCESS
        if args.max_nodes < MINIMUM_LIMIT or args.max_seconds < MINIMUM_LIMIT:
            raise GraphError("лимиты обхода должны быть положительными")
        options = GraphOptions(args.framework, args.max_nodes,
                               args.max_seconds)
        if config.test_mode:
            _run_test(config, Path(args.config))
        else:
            _run_real(config, options)
    except ConfigError as exc:
        print(f"Ошибка конфигурации:\n{exc}", file=sys.stderr)
        return EXIT_FAILURE
    except NuGetError as exc:
        print(f"Ошибка NuGet: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    except GraphError as exc:
        print(f"Ошибка графа: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
