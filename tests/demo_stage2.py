"""Демонстрация получения зависимостей без доступа к NuGet."""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.main import main
from tests.test_nuget import TEST_INDEX, TEST_MANIFEST


def demo():
    """Подставить типовые ответы API и показать вывод CLI."""
    print("Демонстрация второго этапа без интернета:\n")
    with patch("src.nuget._read_url", side_effect=(
        TEST_INDEX, TEST_MANIFEST,
    )):
        status = main(["--config", str(Path("config.csv"))])
    print(f"\nКод возврата: {status}")


if __name__ == "__main__":
    demo()
