"""Тесты чтения CSV и обработки ошибок пяти параметров."""

import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src.config import ConfigError, load_config
from src.main import main


GOOD_SETTINGS = {
    "package_name": "Newtonsoft.Json",
    "repository": "https://api.nuget.org/v3/index.json",
    "test_mode": "false",
    "package_version": "13.0.3",
    "output_file": "dependencies.png",
}


class ConfigTests(unittest.TestCase):
    """Проверить корректные и некорректные настройки."""

    def setUp(self):
        """Подготовить изолированную временную папку."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = Path(self.temp_dir.name) / "config.csv"

    def tearDown(self):
        """Удалить временную папку после теста."""
        self.temp_dir.cleanup()

    def write_settings(self, values=None):
        """Сохранить словарь настроек в CSV."""
        data = GOOD_SETTINGS if values is None else values
        with self.config.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(("key", "value"))
            writer.writerows(data.items())

    def check_invalid(self, field, bad_value):
        """Убедиться, что неверный параметр вызывает ошибку."""
        data = dict(GOOD_SETTINGS)
        data[field] = bad_value
        self.write_settings(data)
        with self.assertRaisesRegex(ConfigError, field):
            load_config(self.config)

    def test_valid_settings(self):
        """Пять параметров успешно считываются из CSV."""
        self.write_settings()
        parsed = load_config(self.config)
        self.assertEqual(parsed.package_name, "Newtonsoft.Json")
        self.assertFalse(parsed.test_mode)

    def test_cli_prints_settings(self):
        """CLI выводит значения как пары ключ-значение."""
        self.write_settings()
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["--config", str(self.config), "--config-only"])
        self.assertEqual(status, 0)
        self.assertIn("package_name = Newtonsoft.Json", output.getvalue())
        self.assertIn("test_mode = false", output.getvalue())

    def test_cli_error_status(self):
        """CLI завершает выполнение с ошибкой при плохом CSV."""
        self.write_settings({"package_name": "wrong name"})
        errors = io.StringIO()
        with redirect_stderr(errors):
            status = main(["--config", str(self.config), "--config-only"])
        self.assertNotEqual(status, 0)
        self.assertIn("Ошибка конфигурации", errors.getvalue())

    def test_missing_file(self):
        """Отсутствие файла конфигурации обрабатывается."""
        with self.assertRaises(ConfigError):
            load_config(self.config)

    def test_invalid_header(self):
        """Файл без заголовка key,value отвергается."""
        self.config.write_text("parameter,value\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigError, "первая строка"):
            load_config(self.config)

    def test_invalid_column_count(self):
        """CSV с лишним столбцом не принимается."""
        self.config.write_text(
            "key,value\npackage_name,A,B\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ConfigError, "два столбца"):
            load_config(self.config)

    def test_duplicate_key(self):
        """Повторяющаяся настройка распознаётся."""
        self.config.write_text(
            "key,value\npackage_name,A\npackage_name,B\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigError, "повтор"):
            load_config(self.config)

    def test_unknown_key(self):
        """Неизвестные ключи отклоняются."""
        self.config.write_text(
            "key,value\nunknown,abc\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ConfigError, "неизвестный"):
            load_config(self.config)

    def test_missing_parameters(self):
        """Для отсутствующих параметров сообщаются ошибки."""
        self.write_settings({})
        with self.assertRaises(ConfigError) as result:
            load_config(self.config)
        for field in GOOD_SETTINGS:
            self.assertIn(field, str(result.exception))

    def test_bad_package(self):
        """Имя пакета с пробелами запрещено."""
        self.check_invalid("package_name", "Bad Name")

    def test_bad_repository(self):
        """FTP не принимается вместо HTTP/HTTPS."""
        self.check_invalid("repository", "ftp://example.com")

    def test_bad_test_mode(self):
        """Невозможно указать произвольный режим."""
        self.check_invalid("test_mode", "sometimes")

    def test_bad_version(self):
        """Текст latest не считается допустимой версией."""
        self.check_invalid("package_version", "latest")

    def test_bad_output_file(self):
        """Изображение должно иметь расширение PNG."""
        self.check_invalid("output_file", "graph.jpg")

    def test_test_mode_existing_file(self):
        """Тестовый режим принимает существующий локальный файл."""
        (self.config.parent / "graph.txt").write_text("A -> B")
        values = dict(GOOD_SETTINGS)
        values.update({"repository": "graph.txt", "test_mode": "true"})
        self.write_settings(values)
        self.assertTrue(load_config(self.config).test_mode)

    def test_test_mode_missing_file(self):
        """Несуществующий файл тестового репозитория отклоняется."""
        values = dict(GOOD_SETTINGS)
        values.update({"repository": "absent.txt", "test_mode": "true"})
        self.write_settings(values)
        with self.assertRaisesRegex(ConfigError, "repository"):
            load_config(self.config)

    def test_prerelease_version(self):
        """Версия с меткой предварительного выпуска разрешена."""
        values = dict(GOOD_SETTINGS)
        values["package_version"] = "1.2.3-beta.1"
        self.write_settings(values)
        self.assertEqual(load_config(self.config).package_version,
                         "1.2.3-beta.1")

    def test_bad_url_whitespace(self):
        """URL с пробелом внутри адреса отвергается."""
        self.check_invalid("repository", "https://bad host/example")

    def test_output_directory_forbidden(self):
        """Значение output_file должно быть именем, не путём."""
        self.check_invalid("output_file", "build/graph.png")


if __name__ == "__main__":
    unittest.main()
