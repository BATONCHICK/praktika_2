"""Демонстрация обработки ошибок пяти параметров CSV."""

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

from .test_config import GOOD_SETTINGS


BAD_VALUES = (
    ("package_name", "Invalid Package"),
    ("repository", "ftp://example.com"),
    ("test_mode", "unknown"),
    ("package_version", "latest"),
    ("output_file", "graph.jpg"),
)


def main():
    """Запустить программу пять раз с неверными параметрами."""
    with tempfile.TemporaryDirectory() as folder:
        config = Path(folder) / "bad.csv"
        for key, bad_value in BAD_VALUES:
            values = dict(GOOD_SETTINGS)
            values[key] = bad_value
            with config.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("key", "value"))
                writer.writerows(values.items())
            result = subprocess.run(
                [sys.executable, "-m", "src.main", "--config", str(config)],
                capture_output=True, text=True, check=False,
            )
            print(f"[{key} = {bad_value}] Код возврата: {result.returncode}")
            print(result.stderr.strip())
            print()


if __name__ == "__main__":
    main()
