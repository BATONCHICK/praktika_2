"""Минимальный выбор версии пакета для диапазонов NuGet."""

import re
from functools import cmp_to_key
from typing import Tuple

from .nuget import NuGetError


VERSION_PATTERN = re.compile(
    r"^(\d+(?:\.\d+){0,3})(?:-([A-Za-z0-9.-]+))?"
    r"(?:\+[A-Za-z0-9.-]+)?$"
)
VERSION_COMPONENTS = 4
EQUAL = 0


def _split_version(value: str) -> Tuple[Tuple[int, ...], Tuple[str, ...]]:
    """Разделить номер версии и идентификаторы предварительного выпуска."""
    matched = VERSION_PATTERN.fullmatch(value)
    if matched is None:
        raise NuGetError(f"некорректная версия NuGet: {value}")
    digits = tuple(int(part) for part in matched.group(1).split("."))
    prerelease = (matched.group(2) or "").lower()
    return digits + (0,) * (VERSION_COMPONENTS - len(digits)), tuple(
        prerelease.split(".") if prerelease else ()
    )


def _compare_identifiers(left: str, right: str) -> int:
    """Сравнить числовые и текстовые идентификаторы SemVer."""
    if left.isdigit() and right.isdigit():
        a, b = int(left), int(right)
        return (a > b) - (a < b)
    if left.isdigit() != right.isdigit():
        return -1 if left.isdigit() else 1
    return (left > right) - (left < right)


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Стабильная версия старше предварительной той же версии."""
    if not left or not right:
        return (not left) - (not right)
    for first, second in zip(left, right):
        comparison = _compare_identifiers(first, second)
        if comparison:
            return comparison
    return (len(left) > len(right)) - (len(left) < len(right))


def compare_versions(first: str, second: str) -> int:
    """Сравнить NuGet-версии без метаданных сборки."""
    left, left_pre = _split_version(first)
    right, right_pre = _split_version(second)
    if left != right:
        return (left > right) - (left < right)
    return _compare_prerelease(left_pre, right_pre)


def _range_parts(constraint: str) -> Tuple[str, str, bool, bool]:
    """Разобрать диапазон в версии нижней/верхней границы."""
    value = constraint.strip()
    if not value:
        return "", "", True, True
    if not value.startswith(("[", "(")):
        _split_version(value)
        return value, "", True, True
    if not value.endswith(("]", ")")):
        raise NuGetError(f"некорректный диапазон: {value}")
    return _bracket_parts(value)


def _bracket_parts(value: str) -> Tuple[str, str, bool, bool]:
    """Разобрать интервал с квадратными и круглыми скобками."""
    interior = value[1:-1]
    if "," not in interior:
        if not (value.startswith("[") and value.endswith("]")):
            raise NuGetError(f"некорректный диапазон: {value}")
        _split_version(interior)
        return interior, interior, True, True
    low, high = (part.strip() for part in interior.split(",", 1))
    if not low and not high:
        raise NuGetError(f"некорректный диапазон: {value}")
    for bound in (low, high):
        if bound:
            _split_version(bound)
    return low, high, value.startswith("["), value.endswith("]")


def _fits_bound(version: str, bound: str, inclusive: bool, lower: bool) -> bool:
    """Проверить одну сторону интервала версий."""
    if not bound:
        return True
    comparison = compare_versions(version, bound)
    if lower:
        return comparison >= EQUAL if inclusive else comparison > EQUAL
    return comparison <= EQUAL if inclusive else comparison < EQUAL


def _in_range(version: str, constraint: str) -> bool:
    """Проверить версию на попадание в заданный диапазон."""
    low, high, include_low, include_high = _range_parts(constraint)
    return (_fits_bound(version, low, include_low, True)
            and _fits_bound(version, high, include_high, False))


def select_version(versions: Tuple[str, ...], constraint: str) -> str:
    """Выбрать минимальную подходящую стабильную версию пакета."""
    _range_parts(constraint)
    allow_prerelease = "-" in constraint
    candidates = [item for item in versions
                  if (allow_prerelease or "-" not in item)
                  and _in_range(item, constraint)]
    if not candidates:
        raise NuGetError(f"нет версии для ограничения '{constraint}'")
    return min(candidates, key=cmp_to_key(compare_versions))
