# Практическая работа №2. Граф зависимостей NuGet

**Дисциплина:** Конфигурационное управление  
**Группа:** ИКБО-22-25  
**Вариант:** 20  
**Язык:** Python 3.9+

## Описание

Консольный инструмент для анализа зависимостей пакетов NuGet.
На **первом этапе** реализованы чтение конфигурации из CSV,
проверка пяти параметров и их вывод на экран.
Загрузка зависимостей и построение графа пока не реализованы.

## Структура

- `src/config.py` — загрузка CSV и проверка настроек.
- `src/main.py` — консольный интерфейс и вывод параметров.
- `config.csv` — настройки по умолчанию.
- `tests/test_config.py` — автоматические тесты.
- `tests/demo_errors.py` — демонстрация ошибок.
- `run.sh` — запуск приложения.

## Конфигурация

CSV содержит два столбца: `key,value`.

| Параметр | Назначение |
| --- | --- |
| `package_name` | Имя пакета NuGet |
| `repository` | HTTP/HTTPS URL или путь к тестовому файлу |
| `test_mode` | `true` / `false` или `1` / `0` |
| `package_version` | Версия пакета (например, `13.0.3`) |
| `output_file` | Имя будущего PNG-файла |

Пример `config.csv`:

```csv
key,value
package_name,Newtonsoft.Json
repository,https://api.nuget.org/v3/index.json
test_mode,false
package_version,13.0.3
output_file,dependencies.png
```

При `test_mode=false` проверяется URL репозитория.
При `test_mode=true` проверяется существование локального файла;
относительный путь считается от папки конфигурации.
На первом этапе запросы в сеть не отправляются.

## Запуск и тестирование

Сторонние библиотеки не нужны, сборка не требуется.
На macOS/Linux из корня проекта:

```bash
./run.sh
./run.sh --config config.csv
python3 -m tests.demo_errors
python3 -m unittest discover -s tests -v
```

Можно запустить напрямую: `python3 -m src.main --config config.csv`.

## Пример работы

```text
package_name = Newtonsoft.Json
repository = https://api.nuget.org/v3/index.json
test_mode = false
package_version = 13.0.3
output_file = dependencies.png
```

При неверных данных выводится сообщение с названием параметра,
а программа завершается с кодом ошибки.
