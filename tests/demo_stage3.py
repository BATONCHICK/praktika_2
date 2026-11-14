"""Три автономных примера DFS для демонстрации третьего этапа."""

from pathlib import Path

from src.main import main


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLES = (
    ("Граф с циклом", "config_cycle.csv"),
    ("Общий узел без цикла", "config_diamond.csv"),
    ("Пакет без зависимостей", "config_no_deps.csv"),
)


def demo() -> None:
    """Вывести результаты трёх тестовых графов без интернета."""
    for title, filename in EXAMPLES:
        print("\n" + "=" * 48)
        print(title)
        print("=" * 48)
        status = main(["--config", str(EXAMPLES_DIR / filename)])
        if status:
            raise SystemExit(status)


if __name__ == "__main__":
    demo()
