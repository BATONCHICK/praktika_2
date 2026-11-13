"""Консольное приложение для конфигурации и зависимостей NuGet."""

import argparse
import sys
from typing import List, Optional, Tuple

from .config import Config, ConfigError, load_config
from .nuget import DependencyGroup, NuGetError, get_direct_dependencies


EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def _print_config(config: Config) -> None:
    """Вывести параметры CSV для совместимости с первым этапом."""
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


def _run(config: Config, config_only: bool) -> None:
    """Выполнить текущий этап или только вывести настройки."""
    _print_config(config)
    if config_only:
        return
    if config.test_mode:
        raise NuGetError("Чтение тестового репозитория — этап 3")
    groups = get_direct_dependencies(
        config.repository, config.package_name, config.package_version,
    )
    _print_dependencies(groups, config)


def main(argv: Optional[List[str]] = None) -> int:
    """Прочитать CSV и вывести прямые зависимости либо ошибку."""
    parser = argparse.ArgumentParser(
        description="NuGet: прямые зависимости, практическая №2, этап 2"
    )
    parser.add_argument("--config", default="config.csv")
    parser.add_argument("--config-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        _run(config, args.config_only)
    except ConfigError as exc:
        print(f"Ошибка конфигурации:\n{exc}", file=sys.stderr)
        return EXIT_FAILURE
    except NuGetError as exc:
        print(f"Ошибка NuGet: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
