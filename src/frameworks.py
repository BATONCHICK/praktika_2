"""Подбор совместимой группы зависимостей для целевой платформы .NET."""

import re
from typing import Optional, Tuple

from .nuget import DependencyGroup, NuGetError


TFM_PATTERN = re.compile(
    r"^(netstandard|netcoreapp|netframework|net)(\d+(?:\.\d+)*)$"
)
MODERN_NET = (5, 0)
MAXIMUM_NETSTANDARD = (2, 1)
LEGACY_NETSTANDARD = (2, 0)
LEGACY_NETFRAMEWORK = (4, 6, 1)
OLD_NETCOREAPP = (3, 1)
NETCOREAPP_STANDARD = (3, 0)
MATCH_EXACT_FAMILY = 3
MATCH_OLD_NETCORE = 2
MATCH_NETSTANDARD = 1


def _parse_tfm(value: str) -> Optional[Tuple[str, Tuple[int, ...]]]:
    """Разобрать имя .NETFramework, netstandard и netcoreapp."""
    normalized = value.strip().lower().replace(".net", "net")
    found = TFM_PATTERN.fullmatch(normalized)
    if not found:
        return None
    family, version = found.groups()
    if family == "net" and version.startswith("4."):
        family = "netframework"
    return family, tuple(int(part) for part in version.split("."))


def _standard_limit(family: str, version: Tuple[int, ...]):
    """Узнать поддерживаемую версию .NET Standard при совместимости."""
    if family == "net" and version >= MODERN_NET:
        return MAXIMUM_NETSTANDARD
    if family == "netcoreapp":
        if version >= NETCOREAPP_STANDARD:
            return MAXIMUM_NETSTANDARD
        return LEGACY_NETSTANDARD
    if family == "netframework" and version >= LEGACY_NETFRAMEWORK:
        return LEGACY_NETSTANDARD
    return None


def _framework_score(target: str, candidate: str):
    """Оценить совместимость двух распространённых платформ .NET."""
    requested = _parse_tfm(target)
    available = _parse_tfm(candidate)
    if requested is None or available is None:
        return None
    family, version = requested
    kind, found_version = available
    return _family_score(family, version, kind, found_version)


def _family_score(family, version, kind, found_version):
    """Сравнить семейства платформ и допустимые версии."""
    if family == kind and found_version <= version:
        return MATCH_EXACT_FAMILY, found_version
    if (family == "net" and version >= MODERN_NET
            and kind == "netcoreapp" and found_version <= OLD_NETCOREAPP):
        return MATCH_OLD_NETCORE, found_version
    limit = _standard_limit(family, version)
    if kind == "netstandard" and limit is not None:
        if found_version <= limit:
            return MATCH_NETSTANDARD, found_version
    return None


def _rank_groups(groups, framework):
    """Собрать кандидатов со степенью совместимости."""
    ranked = []
    for group in groups:
        score = _framework_score(framework, group.framework)
        if score is not None:
            ranked.append((score, group))
    return ranked


def selected_groups(
    groups: Tuple[DependencyGroup, ...], framework: str,
) -> Tuple[DependencyGroup, ...]:
    """Выбрать общую и лучшую совместимую группу зависимостей."""
    common = tuple(group for group in groups if group.framework == "Общие")
    specific = tuple(group for group in groups if group.framework != "Общие")
    if not specific:
        return common
    for group in specific:
        if group.framework.lower() == framework.lower():
            return common + (group,)
    ranked = _rank_groups(specific, framework)
    if not ranked:
        raise NuGetError(f"нет совместимых зависимостей для {framework}")
    return common + (max(ranked, key=lambda item: item[0])[1],)
