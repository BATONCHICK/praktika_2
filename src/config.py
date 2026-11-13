"""Чтение и проверка CSV-конфигурации визуализатора NuGet."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlsplit


CSV_HEADER = ("key", "value")
CSV_COLUMN_COUNT = len(CSV_HEADER)
FIRST_DATA_ROW = 2
CONFIG_KEYS = (
    "package_name",
    "repository",
    "test_mode",
    "package_version",
    "output_file",
)
PACKAGE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
VERSION_PATTERN = re.compile(
    r"[0-9]+(?:\.[0-9]+){1,3}"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


class ConfigError(ValueError):
    """Некорректное содержание или расположение файла настроек."""


@dataclass(frozen=True)
class Config:
    """Настройки первого этапа, считанные из CSV."""

    package_name: str
    repository: str
    test_mode: bool
    package_version: str
    output_file: str


def _read_csv(path: Path) -> Dict[str, str]:
    """Прочитать таблицу ключ-значение и проверить её структуру."""
    settings = {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream, strict=True)
            if next(rows, None) != list(CSV_HEADER):
                raise ConfigError("первая строка должна быть key,value")
            for line_no, row in enumerate(rows, start=FIRST_DATA_ROW):
                if len(row) != CSV_COLUMN_COUNT:
                    raise ConfigError(
                        f"строка {line_no}: ожидаются два столбца"
                    )
                key, value = (cell.strip() for cell in row)
                if key not in CONFIG_KEYS:
                    raise ConfigError(f"неизвестный параметр: {key}")
                if key in settings:
                    raise ConfigError(f"повтор параметра: {key}")
                settings[key] = value
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ConfigError(f"ошибка чтения {path}: {exc}") from exc
    return settings


def _parse_test_mode(value: str, errors: List[str]) -> Optional[bool]:
    """Преобразовать строку режима работы в логическое значение."""
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    errors.append("test_mode: укажите true/false или 1/0")
    return None


def _check_package(value: str, errors: List[str]) -> None:
    """Проверить имя пакета на допустимые символы NuGet."""
    if not PACKAGE_PATTERN.fullmatch(value):
        errors.append("package_name: недопустимое имя пакета")


def _is_web_url(value: str) -> bool:
    """Определить, является ли строка адресом HTTP/HTTPS."""
    if any(character.isspace() for character in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:
        return False


def _check_repository(
    value: str, mode: Optional[bool], folder: Path,
    errors: List[str],
) -> None:
    """Проверить адрес сервера либо путь к тестовому репозиторию."""
    if not value:
        errors.append("repository: адрес или путь не указан")
    elif mode is True:
        file_path = Path(value).expanduser()
        if not file_path.is_absolute():
            file_path = folder / file_path
        if not file_path.is_file():
            errors.append("repository: файл тестового репозитория не найден")
    elif mode is False and not _is_web_url(value):
        errors.append("repository: ожидается URL http/https")


def _check_version(value: str, errors: List[str]) -> None:
    """Проверить запись версии пакета."""
    if not VERSION_PATTERN.fullmatch(value):
        errors.append("package_version: некорректная версия пакета")


def _check_output(value: str, errors: List[str]) -> None:
    """Проверить имя будущего PNG-файла."""
    name = Path(value)
    if (not value or name.name != value or "\\" in value
            or name.suffix.lower() != ".png"):
        errors.append("output_file: укажите имя файла с расширением .png")


def load_config(path: Union[str, Path]) -> Config:
    """Загрузить настройки или сообщить об ошибках параметров."""
    config_path = Path(path)
    settings = _read_csv(config_path)
    errors = []
    mode = _parse_test_mode(settings.get("test_mode", ""), errors)
    _check_package(settings.get("package_name", ""), errors)
    _check_repository(
        settings.get("repository", ""), mode, config_path.parent,
        errors,
    )
    _check_version(settings.get("package_version", ""), errors)
    _check_output(settings.get("output_file", ""), errors)
    if errors:
        raise ConfigError("\n".join(errors))
    return Config(
        settings["package_name"], settings["repository"],
        bool(mode), settings["package_version"],
        settings["output_file"],
    )
