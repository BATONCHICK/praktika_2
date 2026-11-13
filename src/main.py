"""Командный интерфейс первого этапа практической работы."""

import argparse
import sys
from typing import List, Optional

from .config import ConfigError, load_config


EXIT_SUCCESS = 0
EXIT_FAILURE = 1


def main(argv: Optional[List[str]] = None) -> int:
    """Прочитать CSV и вывести пять параметров в формате ключ-значение."""
    parser = argparse.ArgumentParser(
        description="NuGet: конфигурация, практическая №2, этап 1"
    )
    parser.add_argument(
        "--config", default="config.csv",
        help="путь к CSV-файлу настроек",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Ошибка конфигурации:\n{exc}", file=sys.stderr)
        return EXIT_FAILURE

    print(f"package_name = {config.package_name}")
    print(f"repository = {config.repository}")
    print(f"test_mode = {str(config.test_mode).lower()}")
    print(f"package_version = {config.package_version}")
    print(f"output_file = {config.output_file}")
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
