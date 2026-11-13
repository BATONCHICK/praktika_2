"""Автономные проверки получения прямых зависимостей NuGet V3."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.main import main
from src.nuget import (
    MAX_RESPONSE_BYTES,
    NuGetError,
    _find_package_base,
    _manifest_url,
    _normalize_version,
    _parse_manifest,
    _read_url,
    get_direct_dependencies,
)
from tests.test_config import GOOD_SETTINGS


TEST_INDEX = json.dumps({
    "version": "3.0.0",
    "resources": [
        {"@id": "https://example.test/other", "@type": "Other/1.0.0"},
        {
            "@id": "https://example.test/flat/",
            "@type": ["PackageBaseAddress/3.0.0", "Other/1.0.0"],
        },
    ],
}).encode("utf-8")

TEST_MANIFEST = b'''<?xml version="1.0"?>
<package xmlns="http://schemas.microsoft.com/packaging/2012/06/nuspec.xsd">
  <metadata>
    <dependencies>
      <group targetFramework=".NETFramework4.5" />
      <group targetFramework=".NETStandard1.0">
        <dependency id="Microsoft.CSharp" version="4.3.0" />
        <dependency id="NETStandard.Library" version="[1.6.1, )" />
      </group>
      <group targetFramework="net6.0" />
    </dependencies>
  </metadata>
</package>'''


class NuGetTests(unittest.TestCase):
    """Проверить реальный протокол без обращения к интернету."""

    def test_package_base_resource(self):
        """Найти ресурс API даже при массиве значений @type."""
        self.assertEqual(
            _find_package_base(TEST_INDEX), "https://example.test/flat"
        )

    def test_manifest_path(self):
        """URL использует нижний регистр имени и версии пакета."""
        result = _manifest_url(
            "https://example.test/flat", "Newtonsoft.Json", "13.0.3"
        )
        self.assertEqual(
            result, "https://example.test/flat/"
            "newtonsoft.json/13.0.3/newtonsoft.json.nuspec"
        )

    def test_normalized_version(self):
        """Нормализовать числовые компоненты и служебную часть версии."""
        self.assertEqual(_normalize_version("1.2"), "1.2.0")
        self.assertEqual(_normalize_version("1.02.0.0"), "1.2.0")
        self.assertEqual(
            _normalize_version("1.2.3-Beta+build"), "1.2.3-beta"
        )

    def test_groups_and_empty_groups(self):
        """Получить зависимости по платформам, в том числе пустым."""
        groups = _parse_manifest(TEST_MANIFEST)
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0].framework, ".NETFramework4.5")
        self.assertEqual(groups[0].dependencies, ())
        self.assertEqual(groups[1].dependencies[0].name, "Microsoft.CSharp")
        self.assertEqual(groups[1].dependencies[1].version, "[1.6.1, )")
        self.assertEqual(groups[2].framework, "net6.0")

    def test_flat_dependencies(self):
        """Прочитать старый формат без групп целевых платформ."""
        manifest = b'<package><metadata><dependencies>' \
            b'<dependency id="A" version="[1.0]" />' \
            b'</dependencies></metadata></package>'
        groups = _parse_manifest(manifest)
        self.assertEqual(groups[0].framework, "Общие")
        self.assertEqual(groups[0].dependencies[0].name, "A")

    def test_no_dependencies(self):
        """Вернуть пустой список, если зависимостей нет."""
        manifest = b"<package><metadata/></package>"
        self.assertEqual(_parse_manifest(manifest), ())

    def test_invalid_xml(self):
        """Повреждённый XML приводит к понятной ошибке."""
        with self.assertRaisesRegex(NuGetError, "XML"):
            _parse_manifest(b"<package><metadata>")

    def test_missing_metadata(self):
        """Манифест без metadata не принимается."""
        with self.assertRaisesRegex(NuGetError, "metadata"):
            _parse_manifest(b"<package></package>")

    def test_missing_dependency_name(self):
        """Обязательное поле id не может отсутствовать."""
        xml = b'<package><metadata><dependencies>' \
            b'<dependency version="1.0" />' \
            b'</dependencies></metadata></package>'
        with self.assertRaisesRegex(NuGetError, "id"):
            _parse_manifest(xml)

    def test_bad_json(self):
        """Повреждённый JSON не приводит к необработанному исключению."""
        with self.assertRaisesRegex(NuGetError, "JSON"):
            _find_package_base(b"{")

    def test_missing_resource(self):
        """В индексе должна быть служба PackageBaseAddress."""
        with self.assertRaisesRegex(NuGetError, "PackageBaseAddress"):
            _find_package_base(b'{"resources": []}')

    def test_missing_resource_list(self):
        """В индексе должен находиться массив resources."""
        with self.assertRaisesRegex(NuGetError, "списка ресурсов"):
            _find_package_base(b'{}')

    def test_invalid_resource_url(self):
        """Ресурс не может использовать локальный протокол file."""
        index = b'{"resources": [{"@type": ' \
            b'"PackageBaseAddress/3.0.0", "@id": "file:///tmp"}]}'
        with self.assertRaisesRegex(NuGetError, "URL"):
            _find_package_base(index)

    def test_gets_index_and_manifest(self):
        """Получение зависимостей выполняет два HTTP-запроса."""
        with patch("src.nuget._read_url", side_effect=(
            TEST_INDEX, TEST_MANIFEST,
        )) as mocked:
            groups = get_direct_dependencies(
                "https://example.test/index.json", "Newtonsoft.Json",
                "13.0.3",
            )
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(len(groups), 3)
        self.assertIn("newtonsoft.json.nuspec", mocked.call_args.args[0])

    def test_http_404(self):
        """Проверить сообщение об отсутствующем пакете или версии."""
        error = HTTPError("https://example.test", 404, "Not Found", {}, None)
        with patch("src.nuget.urlopen", side_effect=error):
            with self.assertRaisesRegex(NuGetError, "HTTP 404"):
                _read_url("https://example.test")

    def test_connection_failure(self):
        """Проверить обработку недоступного репозитория."""
        with patch("src.nuget.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(NuGetError, "Не удалось"):
                _read_url("https://example.test")

    def test_too_large_response(self):
        """Не загружать чрезмерно большой ответ сервера."""
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"x" * (
            MAX_RESPONSE_BYTES + 1
        )
        with patch("src.nuget.urlopen", return_value=response):
            with self.assertRaisesRegex(NuGetError, "размер"):
                _read_url("https://example.test")

    def test_cli_outputs_platforms(self):
        """CLI правильно выводит зависимости и пустые платформы."""
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.csv"
            self.write_config(config)
            output = io.StringIO()
            with patch("src.nuget._read_url", side_effect=(
                TEST_INDEX, TEST_MANIFEST,
            )), redirect_stdout(output):
                status = main(["--config", str(config)])
        self.assertEqual(status, 0)
        self.assertIn("[.NETStandard1.0]", output.getvalue())
        self.assertIn("NETStandard.Library ([1.6.1, ))", output.getvalue())
        self.assertIn("[net6.0]", output.getvalue())

    def test_cli_repo_error(self):
        """Ошибка репозитория приводит к ненулевому коду CLI."""
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.csv"
            self.write_config(config)
            error = io.StringIO()
            with patch("src.nuget._read_url", side_effect=NuGetError(
                "сбой сети"
            )), redirect_stderr(error):
                status = main(["--config", str(config)])
        self.assertEqual(status, 1)
        self.assertIn("Ошибка NuGet", error.getvalue())

    def test_config_only_skips_network(self):
        """При флаге --config-only сеть не используется."""
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.csv"
            self.write_config(config)
            output = io.StringIO()
            with patch("src.nuget._read_url") as mocked:
                with redirect_stdout(output):
                    status = main([
                        "--config", str(config), "--config-only",
                    ])
            mocked.assert_not_called()
        self.assertEqual(status, 0)

    def test_test_mode_is_reserved(self):
        """Режим локального графа появится только в третьем этапе."""
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.csv"
            graph_file = Path(folder) / "graph.txt"
            graph_file.write_text("A -> B", encoding="utf-8")
            values = dict(GOOD_SETTINGS)
            values.update({"repository": "graph.txt", "test_mode": "true"})
            self.write_config(config, values)
            output = io.StringIO()
            with redirect_stderr(output):
                status = main(["--config", str(config)])
        self.assertEqual(status, 1)
        self.assertIn("этап 3", output.getvalue())

    @staticmethod
    def write_config(path, values=None):
        """Создать временный корректный CSV без сторонних библиотек."""
        import csv
        data = GOOD_SETTINGS if values is None else values
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(("key", "value"))
            writer.writerows(data.items())


if __name__ == "__main__":
    unittest.main()
