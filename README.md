# Практическая работа №2. Граф зависимостей NuGet

**Дисциплина:** Конфигурационное управление  
**Группа:** ИКБО-22-25  
**Вариант:** 20  
**Язык:** Python 3.9+

## Описание

Консольный инструмент для анализа зависимостей пакетов NuGet.

- **Этап 1:** чтение параметров из CSV и проверка ошибок.
- **Этап 2:** получение прямых зависимостей заданной версии пакета
  из репозитория NuGet V3 через HTTP и вывод по платформам .NET.

Для получения зависимостей используются только стандартные модули
Python (`urllib`, `json`, `xml.etree.ElementTree`). Менеджеры пакетов
и сторонние библиотеки не используются.

Транзитивный обход и работа с локальным тестовым графом относятся
к третьему этапу; построения изображения пока нет.

## Структура

- `src/config.py` — чтение CSV и проверка пяти параметров.
- `src/nuget.py` — обращения к NuGet V3 и обработка манифеста `.nuspec`.
- `src/main.py` — вывод настроек и прямых зависимостей.
- `config.csv` — конфигурация по умолчанию.
- `tests/test_config.py`, `tests/test_nuget.py` — автоматические тесты.
- `tests/demo_errors.py`, `tests/demo_stage2.py` — демонстрации.
- `run.sh` — запуск приложения.

## Настройки

Конфигурационный файл `config.csv` имеет формат `key,value`.

| Параметр | Назначение |
| --- | --- |
| `package_name` | Имя пакета NuGet |
| `repository` | URL индекса NuGet V3 или путь к тестовому файлу |
| `test_mode` | `true` / `false` или `1` / `0` |
| `package_version` | Версия пакета, например `13.0.3` |
| `output_file` | Имя будущего PNG-файла |

```csv
key,value
package_name,Newtonsoft.Json
repository,https://api.nuget.org/v3/index.json
test_mode,false
package_version,13.0.3
output_file,dependencies.png
```

На втором этапе для запросов к NuGet нужен `test_mode=false`.
При `test_mode=true` настройки проверяются, но локальный граф пока
не обрабатывается.

## Запуск и тестирование

Сборка и установка дополнительных пакетов не требуются.
Из корня репозитория на macOS/Linux:

```bash
./run.sh
./run.sh --config-only
python3 -m tests.demo_errors
python3 -m tests.demo_stage2
python3 -m unittest discover -s tests -v
```

`./run.sh` обращается к реальному репозиторию; необходим интернет.
`python3 -m tests.demo_stage2` показывает получение зависимостей
с имитацией ответов сервера и не требует доступа к интернету.

## Как работает второй этап

1. Из URL в CSV загружается служебный индекс NuGet V3 (`index.json`).
2. В индексе ищется ресурс `PackageBaseAddress/3.0.0`.
3. По имени и указанной версии пакета загружается XML-файл `.nuspec`.
4. Выводятся только прямые зависимости из раздела `dependencies`,
   в том числе пустые группы целевых платформ.

Для `Newtonsoft.Json 13.0.3` среди прочих выводятся зависимости
`.NETStandard1.0`: `Microsoft.CSharp`, `NETStandard.Library` и другие.
Для `net6.0` прямых зависимостей нет.

Ошибки некорректного CSV, отсутствующего пакета, сетевого доступа,
JSON и XML обрабатываются и завершают программу с ненулевым кодом.

Документация протокола:
[NuGet Service Index](https://learn.microsoft.com/nuget/api/service-index),
[Package Content](https://learn.microsoft.com/nuget/api/package-base-address-resource),
[Формат NUSPEC](https://learn.microsoft.com/nuget/reference/nuspec).
