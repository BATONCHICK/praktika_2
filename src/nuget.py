"""Получение прямых зависимостей NuGet через официальный API V3."""

import json
from dataclasses import dataclass
from typing import Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


HTTP_TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAXIMUM_READ_BYTES = MAX_RESPONSE_BYTES + 1
RESOURCE_KIND = "PackageBaseAddress/3.0.0"
MIN_VERSION_SEGMENTS = 3
MAX_VERSION_SEGMENTS = 4


class NuGetError(ValueError):
    """Ошибка при получении или разборе данных репозитория NuGet."""


@dataclass(frozen=True)
class Dependency:
    """Прямая зависимость: идентификатор и допустимая версия."""

    name: str
    version: str


@dataclass(frozen=True)
class DependencyGroup:
    """Прямые зависимости, объявленные для целевой платформы .NET."""

    framework: str
    dependencies: Tuple[Dependency, ...]


def _read_url(url: str) -> bytes:
    """Получить HTTP-ответ с ограничением времени и размера."""
    request = Request(url, headers={"User-Agent": "NuGetGraphStudent/1.0"})
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            data = response.read(MAXIMUM_READ_BYTES)
    except HTTPError as exc:
        raise NuGetError(f"HTTP {exc.code}: {url}") from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise NuGetError(f"Не удалось получить {url}: {exc}") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise NuGetError("Ответ репозитория превышает допустимый размер")
    return data


def _resource_types(value: object) -> Tuple[str, ...]:
    """Преобразовать значение @type индекса NuGet к единому виду."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _validate_base_url(value: object) -> str:
    """Проверить адрес службы загрузки NuGet-пакетов."""
    if not isinstance(value, str):
        raise NuGetError("В индексе NuGet отсутствует адрес ресурса")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NuGetError("Недопустимый URL ресурса PackageBaseAddress")
    return value.rstrip("/")


def _find_package_base(data: bytes) -> str:
    """Прочитать индекс V3 и найти ресурс PackageBaseAddress."""
    try:
        index = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise NuGetError("Некорректный JSON индекса NuGet") from exc
    if not isinstance(index, dict):
        raise NuGetError("Индекс NuGet должен быть объектом JSON")
    resources = index.get("resources")
    if not isinstance(resources, list):
        raise NuGetError("В индексе NuGet нет списка ресурсов")
    for resource in resources:
        if isinstance(resource, dict):
            types = _resource_types(resource.get("@type"))
            if RESOURCE_KIND in types:
                return _validate_base_url(resource.get("@id"))
    raise NuGetError("В индексе нет ресурса PackageBaseAddress/3.0.0")


def _normalize_version(version: str) -> str:
    """Привести номер версии к форме URL NuGet Flat Container."""
    version_without_build = version.split("+", maxsplit=1)[0]
    release, separator, suffix = version_without_build.partition("-")
    numbers = [str(int(value)) for value in release.split(".")]
    while len(numbers) < MIN_VERSION_SEGMENTS:
        numbers.append("0")
    if len(numbers) == MAX_VERSION_SEGMENTS and numbers[-1] == "0":
        numbers.pop()
    return (".".join(numbers) + separator + suffix).lower()


def _manifest_url(base: str, package: str, version: str) -> str:
    """Составить путь к XML-манифесту конкретной версии пакета."""
    name = quote(package.lower(), safe="")
    release = quote(_normalize_version(version), safe="")
    return f"{base}/{name}/{release}/{name}.nuspec"


def _parse_dependencies(node: ElementTree.Element) -> Tuple[Dependency, ...]:
    """Прочитать зависимости из одного элемента XML."""
    result = []
    for item in node.findall("{*}dependency"):
        name = item.get("id")
        if not name:
            raise NuGetError("У зависимости в NUSPEC отсутствует id")
        result.append(Dependency(name, item.get("version", "")))
    return tuple(result)


def _parse_manifest(data: bytes) -> Tuple[DependencyGroup, ...]:
    """Разобрать NUSPEC, сохранив разделение по платформам .NET."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise NuGetError("Некорректный XML манифеста NUSPEC") from exc
    metadata = root.find("{*}metadata")
    if metadata is None:
        raise NuGetError("В NUSPEC отсутствует элемент metadata")
    dependencies = metadata.find("{*}dependencies")
    if dependencies is None:
        return ()
    groups = dependencies.findall("{*}group")
    if groups:
        return tuple(
            DependencyGroup(group.get("targetFramework") or "Общие",
                            _parse_dependencies(group))
            for group in groups
        )
    return (DependencyGroup("Общие", _parse_dependencies(dependencies)),)


def get_direct_dependencies(
    repository: str, package: str, version: str,
) -> Tuple[DependencyGroup, ...]:
    """Загрузить только прямые зависимости нужной версии NuGet-пакета."""
    base_url = _find_package_base(_read_url(repository))
    manifest_url = _manifest_url(base_url, package, version)
    return _parse_manifest(_read_url(manifest_url))
