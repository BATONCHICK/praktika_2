"""Проверка выбора совместимых версий для NuGet Flat Container."""

import unittest

from src.nuget import NuGetError
from src.versions import compare_versions, select_version


class VersionTests(unittest.TestCase):
    """Проверить NuGet-диапазоны и порядок версий."""

    def test_exact_version(self):
        """Квадратные скобки без запятой требуют точной версии."""
        versions = ("1.1.0", "1.2.0", "1.3.0")
        self.assertEqual(select_version(versions, "[1.2.0]"), "1.2.0")

    def test_lower_bound(self):
        """Обычная запись версии — включительная нижняя граница."""
        versions = ("1.0.0", "1.5.0", "2.0.0")
        self.assertEqual(select_version(versions, "1.2"), "1.5.0")

    def test_open_range(self):
        """Открытая верхняя граница исключает версию справа."""
        versions = ("1.0.0", "1.9.0", "2.0.0")
        self.assertEqual(select_version(versions, "[1,2)"), "1.0.0")

    def test_upper_only(self):
        """Диапазон (,2.0) допускает версии ниже верхней границы."""
        versions = ("1.0", "2.0", "3.0")
        self.assertEqual(select_version(versions, "(,2.0)"), "1.0")

    def test_exclusive_lower(self):
        """Круглая скобка исключает нижнюю границу."""
        versions = ("1.0", "1.1", "2.0")
        self.assertEqual(select_version(versions, "(1.0,2.0]"), "1.1")

    def test_no_matching(self):
        """При отсутствии подходящей версии возникает ошибка."""
        with self.assertRaisesRegex(NuGetError, "нет версии"):
            select_version(("1.0",), "[2.0]")

    def test_invalid_range(self):
        """Ошибочный диапазон нельзя молча игнорировать."""
        with self.assertRaises(NuGetError):
            select_version(("1.0",), "(1.0")

    def test_prerelease(self):
        """Пробную версию берём только если она явно разрешена."""
        versions = ("1.0.0-alpha", "1.0.0", "2.0.0-beta")
        self.assertEqual(select_version(versions, ""), "1.0.0")
        self.assertEqual(
            select_version(versions, "[1.0.0-alpha]"), "1.0.0-alpha"
        )

    def test_prerelease_comparison(self):
        """Числовые идентификаторы сравниваются как целые числа."""
        self.assertLess(
            compare_versions("1.0.0-beta.2", "1.0.0-beta.10"), 0
        )
        self.assertGreater(compare_versions("1.0.0", "1.0.0-rc"), 0)

    def test_build_metadata(self):
        """Метаданные сборки не меняют порядок версий."""
        self.assertEqual(compare_versions("1.0+build", "1.0"), 0)

    def test_fourth_part(self):
        """NuGet-версия может состоять из четырёх числовых частей."""
        self.assertGreater(compare_versions("1.0.0.2", "1.0.0.1"), 0)


if __name__ == "__main__":
    unittest.main()
