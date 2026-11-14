"""Проверки выбора единой целевой платформы .NET для графа."""

import unittest

from src.frameworks import selected_groups
from src.nuget import Dependency, DependencyGroup, NuGetError


class FrameworkTests(unittest.TestCase):
    """Проверить точные группы, совместимость и пустые зависимости."""

    def test_exact_even_when_empty(self):
        """Пустая точная группа не подменяется чужими зависимостями."""
        groups = (
            DependencyGroup("net6.0", ()),
            DependencyGroup(".NETStandard1.0", (Dependency("B", "1.0"),)),
        )
        self.assertEqual(selected_groups(groups, "net6.0"), (groups[0],))

    def test_nearest_standard(self):
        """Для net8.0 можно выбрать netstandard2.0."""
        groups = (
            DependencyGroup("netstandard1.0", ()),
            DependencyGroup("netstandard2.0", (Dependency("B", "1.0"),)),
        )
        self.assertEqual(selected_groups(groups, "net8.0"), (groups[1],))

    def test_legacy_framework(self):
        """Разбираются старые названия .NETFramework4.5."""
        group = DependencyGroup(".NETFramework4.5", ())
        self.assertEqual(selected_groups((group,), "netframework4.5"),
                         (group,))

    def test_common(self):
        """Общие зависимости остаются вместе с выбранной группой."""
        common = DependencyGroup("Общие", (Dependency("A", "1.0"),))
        specific = DependencyGroup("net6.0", ())
        self.assertEqual(selected_groups((common, specific), "net6.0"),
                         (common, specific))

    def test_no_groups(self):
        """Пакет без зависимостей не требует выбора платформы."""
        self.assertEqual(selected_groups((), "net6.0"), ())

    def test_incompatible(self):
        """Несовместимые платформы должны давать ошибку."""
        group = DependencyGroup(".NETFramework4.0", ())
        with self.assertRaisesRegex(NuGetError, "совместимых"):
            selected_groups((group,), "net6.0")


if __name__ == "__main__":
    unittest.main()
