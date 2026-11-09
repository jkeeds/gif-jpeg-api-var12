# GIF → JPEG: асинхронный HTTP API — вариант №12

Дисциплина: **Прикладная разработка серверных частей веб-приложений на языке Питон**.  
Тема курсовой: **Веб-приложение с HTTP API для асинхронного преобразования файлов из формата GIF в формат JPEG**.

Реализованы три этапа задания: CLI-конвертер, HTTP API на **Bottle**, слой хранения на **SQLite с SQL-запросами**. Для этапа 2 также доступно файловое JSON-хранилище. При отправке задания API создаёт запись и немедленно возвращает её; фактическая конвертация выполняется отдельным потоком, который запускает CLI через `subprocess.run()`.

## Требования

- Python 3.10 или новее.
- Установленные зависимости из `requirements.txt`.
- Для реальной обработки: исходные `.gif` в `data/uploads/`.
- Все команды выполнять из **корня репозитория**.

## Установка

```bash
python -m pip install -r requirements.txt
cp config.ini.example config.ini
```

В Windows вместо `cp` можно выполнить `copy config.ini.example config.ini`. Настройте `username` и `password` в файле `config.ini`; этот файл исключён из git. Пример содержит только учебные учётные данные, меняйте пароль перед запуском в сети.

## Этап 1 — консольная утилита

```bash
python -m scripts.create_sample
python -m src.converter data/uploads/sample.gif data/outputs/sample.jpg
python -m scripts.demo_three_gifs
python -m unittest tests.test_converter -v
```

Команда принимает **путь к входному файлу** и **путь к выходному файлу**. Если GIF анимирован, используется **первый кадр**. Прозрачные области становятся белыми, потому что JPEG не поддерживает прозрачность. `demo_three_gifs` создаёт три различных входных GIF (64×48, 100×40, 32×96), превращает их в JPEG, проверяет формат и размеры, удаляет временные бинарные файлы. Бинарные примеры намеренно не коммитятся (правило Г2 методички).

Коммит по завершении этапа 1:

```bash
git add src/converter.py scripts/demo_three_gifs.py scripts/create_sample.py tests/test_converter.py

git commit -m "feat(cli): implement GIF to JPEG conversion"
```

## Этап 2 — Bottle API и JSON-файловая СУБД

```bash
python run.py --backend file
```

Либо в учебном тестовом режиме без реальной конвертации:

```bash
python run.py --backend file --test-mode
```

Адрес сервера: `http://127.0.0.1:8000`. Все запросы требуют **HTTP Basic Auth** (RFC 7617). Ответы — XML. Для демонстрации используются имя `admin` и пароль `change-me` из `config.ini.example` (или установленные вами собственные значения).

### Все 9 маршрутов по таблице 12

| № | Метод | Маршрут | Параметры |
|---|---|---|---|
| 1.1 | POST | `/core/api/stable/add-participant` | `locale`, `platform` |
| 1.2 | GET | `/core/api/stable/read-participant` | фильтры `locale`, `platform` |
| 1.3 | GET | `/core/api/stable/retrieve-participant` | `id` |
| 2.1 | POST | `/core/api/stable/add-assignment` | `participant`, `input`, `tags` |
| 2.2 | GET | `/core/api/stable/read-assignment/:participant` | путь, фильтр `stage` |
| 2.3 | GET | `/core/api/stable/retrieve-assignment` | `id` |
| 3.1 | GET | `/core/api/stable/read-result/:assignment` | путь, фильтр `stage` |
| 3.2 | GET | `/core/api/stable/retrieve-result` | `id` |
| 4.1 | GET | `/core/api/stable/read-report` | нет |

Маршруты и HTTP-методы дословно соответствуют заданию, названия параметров выбраны в рамках собственной реализации, поскольку таблица методички их не задаёт.

### Примеры запросов (из терминала)

Создать участника:

```bash
curl -i -u admin:change-me -X POST "http://127.0.0.1:8000/core/api/stable/add-participant?locale=ru&platform=windows"
```

Вывести участников и прочитать конкретного:

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-participant"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-participant?id=1"
```

Создать `sample.gif` командой `python -m scripts.create_sample` (он появится в `data/uploads/`), затем создать задание:

```bash
curl -i -u admin:change-me -X POST "http://127.0.0.1:8000/core/api/stable/add-assignment?participant=1&input=sample.gif&tags=demo"
```

Проверить, что задание и результат появились:

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-assignment/1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-assignment?id=1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-result/1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-result?id=1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-report"
```

Конвертация: `queued` → `running` → `done` (или `error`). В режиме `--test-mode`: `test` и `skipped (test mode)` без реального выполнения. В обычном режиме результат сохраняется как `data/outputs/<assignment_id>_<filename>.jpg`. При отсутствии или ошибке входного файла возвращается `400`, для неизвестного ID — `404`, при неверной Basic Auth — `401`. Защита от обхода путей: API принимает только простое имя файла, не произвольные директории.

### Реляционная алгебра: отчёт по формуле (12)

Возвращаются столбцы **`Assignment.input`, `Participant.platform`, `Result.cache_hit`**. Сначала используется правое внешнее соединение `Participant` с `Assignment` (с учётом внешнего ключа эквивалентно внутреннему), затем левое внешнее соединение с результатами за последние 5 минут (`Result.datetime >= now - 5 min`). Участники без заданий в отчёт не попадают. У записей без подходящего результата будет XML-атрибут `null="true"`. Значение `cache_hit` всегда 0: этот учебный конвертер не выполняет кеширование. В JSON и SQLite реализована одна и та же логика отчёта.

## Этап 3 — SQLite на SQL-запросах

```bash
python run.py --backend sqlite
```

Создаётся `data/database.sqlite3`. Таблицы `participant`, `assignment`, `result` соответствуют ER-диаграмме варианта 12. В `src/storage.py` используются `sqlite3`, `CREATE TABLE`, `INSERT`, `SELECT`, `UPDATE` и `LEFT JOIN`, **ORM нет**. Переключатель `--backend` позволяет повторно запустить то же API и те же тесты с другой системой хранения.

## Model-Based Testing (MBT) и Coverage

```bash
python -m unittest tests.test_mbt -v
python -m coverage erase
python -m coverage run --branch --source=src -m unittest tests.test_mbt
python -m coverage report -m
python -m coverage html
```

Файл `tests/test_mbt.py` содержит машину состояний `RuleBasedStateMachine` из Hypothesis. Её сгенерированные сценарии создают участников и задания, читают и сопоставляют записи и результаты. В **каждом сценарии** начальное действие `@initialize()` вызывает все девять маршрутов через клиент `ApiClient`. Две конфигурации запускают идентичную модель для файлового хранилища и SQLite. `coverage` формирует отчёт о **ветвях** (`--branch`), а HTML отчёт появляется в `htmlcov/index.html`. Это не утверждение о 100% покрытии всех ветвей: фактический процент определяется результатом запуска.

Юнит-тесты из `tests/test_converter.py` проверяют CLI отдельно; покрытие API доказывается только MBT-тестами, сгенерированными Hypothesis.

Клиент `src/client.py`: имена девяти публичных методов полностью соответствуют путям таблицы 12 после замены `/` и `-` на `_`, например `core_api_stable_add_participant`.

## Полное описание функций и настроек

В этом разделе перечислены функции и публичные методы проекта, в том числе
внутренние вспомогательные операции. Начальный символ `_` в имени означает,
что метод предназначен для внутреннего использования.

### Конвертер и запуск

| Файл | Функция | Назначение |
|---|---|---|
| `src/converter.py` | `convert_gif(input_path, output_path)` | Проверяет входной GIF, берёт первый кадр, создаёт белый фон, сохраняет JPEG и возвращает путь. |
| `src/converter.py` | `main(argv)` | Обрабатывает два аргумента CLI, запускает конвертер и сообщает об ошибке. |
| `scripts/create_sample.py` | `main()` | Создаёт анимированный пример `data/uploads/sample.gif`. |
| `scripts/demo_three_gifs.py` | `main()` | Создаёт три тестовых GIF и проверяет полученные JPEG. |
| `run.py` | `load_auth(config_path)` | Читает логин и пароль Basic Auth из INI-файла. |
| `run.py` | `main(argv)` | Разбирает настройки запуска, создаёт хранилище, сервис и Bottle-сервер. |

### HTTP API — `src/api.py`

| Функция | Назначение |
|---|---|
| `xml_document` | Преобразует запись или список записей в XML. |
| `_is_authorized` | Проверяет HTTP Basic Auth, сравнивая учётные данные безопасным способом. |
| `wrap_result` | Формирует XML-ответ и коды 400/404 для ошибок данных. |
| `required_id` | Извлекает положительный числовой идентификатор из query string. |
| `register_participant_routes` | Регистрирует три обработчика для Participant. |
| `add_participant`, `read_participant`, `retrieve_participant` | Создают, ищут и читают участника. |
| `register_assignment_routes` | Регистрирует три обработчика для Assignment. |
| `add_assignment`, `read_assignment`, `retrieve_assignment` | Создают, ищут и читают задание. |
| `register_result_routes` | Регистрирует два обработчика для Result. |
| `read_result`, `retrieve_result` | Ищут и читают результат. |
| `create_app` | Создаёт Bottle-приложение и маршрут отчёта. |
| `authenticate` | Хук, отклоняющий неавторизованные запросы с HTTP 401. |
| `response_type` | Хук, устанавливающий тип XML-ответа. |

Обработчики `add_*`, `read_*`, `retrieve_*`, `authenticate` и
`response_type` объявляются внутри функций регистрации маршрутов или
`create_app`; их нельзя вызывать как самостоятельный импортируемый API.

### Асинхронная обработка — `src/service.py`

| Метод `ConversionService` | Назначение |
|---|---|
| `__init__` | Подготавливает каталоги и пул из двух рабочих потоков. |
| `add_assignment` | Проверяет файл и участника, сохраняет задачу и запускает обработку либо тестовый режим. |
| `_finish` | Согласованно обновляет статусы Assignment и Result. |
| `_convert` | Запускает отдельный процесс CLI через `subprocess.run`, фиксирует итог. |
| `close` | Останавливает пул и дожидается завершения заданий. |

### Модели данных — `src/storage.py`

`FileStore` сохраняет записи в JSON-файле, `SQLiteStore` использует таблицы
SQLite с параметризованными SQL-запросами. Обе реализации предоставляют
одинаковые методы предметной модели:

| Метод | Назначение |
|---|---|
| `__init__` | Создаёт или открывает хранилище и таблицы. |
| `participant_add`, `participant_read`, `participant_retrieve` | Добавляют, фильтруют и находят участника по ID. |
| `assignment_add`, `assignment_read`, `assignment_retrieve` | Добавляют, фильтруют и находят задания. |
| `assignment_stage` | Обновляет этап выполнения задания. |
| `result_add`, `result_read`, `result_retrieve` | Добавляют, фильтруют и находят результаты. |
| `result_update` | Изменяет поля существующего результата. |
| `report_read` | Строит отчёт по формуле (12), по умолчанию за последние 300 секунд. |

Вспомогательные функции и методы: `_now` возвращает Unix-время;
`_where_matches` проверяет условия фильтра; `FileStore._load`,
`_save`, `_add`, `_read`, `_retrieve`, `_update` работают с JSON;
`SQLiteStore._connect` открывает транзакцию с откатом при ошибке,
`_select` составляет фильтрованный SELECT, `_insert` выполняет INSERT,
`_update` выполняет UPDATE. Использование блокировок защищает операции
хранилища от одновременной записи несколькими потоками.

### HTTP-клиент — `src/client.py`

`ApiClient.__init__` сохраняет адрес сервера и создаёт заголовок Basic Auth.
`ApiClient._request` выполняет HTTP-запрос и разбирает XML в список словарей.
Девять публичных методов имеют имена, производные от маршрутов таблицы 12:

| Метод `ApiClient` | Действие |
|---|---|
| `core_api_stable_add_participant` | Создать участника. |
| `core_api_stable_read_participant` | Найти участников. |
| `core_api_stable_retrieve_participant` | Получить одного участника. |
| `core_api_stable_add_assignment` | Создать задачу конвертации. |
| `core_api_stable_read_assignment` | Найти задачи участника. |
| `core_api_stable_retrieve_assignment` | Получить одну задачу. |
| `core_api_stable_read_result` | Найти результаты задачи. |
| `core_api_stable_retrieve_result` | Получить один результат. |
| `core_api_stable_read_report` | Получить сводный отчёт. |

### Тестовые функции

`tests/test_converter.py`: `test_gif_converts_to_jpeg` проверяет формат и
размеры JPEG, `test_rejects_non_gif` — отклонение ложного GIF.

`tests/test_mbt.py`: `QuietHandler.log_message` отключает вывод серверного
журнала. `ApiMachine.__init__` поднимает тестовый HTTP-сервер,
`teardown` его завершает, `initial_workflow` проходит девять маршрутов,
`check_unassigned_participant` проверяет отчёт,
`unauthenticated_is_rejected` — HTTP 401, `new_participant` и
`new_assignment` — создание записей, `inspect_assignment` — чтение,
`read_model_matches` — инварианты данных. `FileApiMachine` и
`SQLiteApiMachine` запускают одну модель на разных хранилищах.

### Параметры и конфигурация

| Настройка | Где задаётся | Значение и назначение |
|---|---|---|
| `username`, `password` | `config.ini`, раздел `[auth]` | Учётные данные HTTP Basic Auth. |
| `--config` | `run.py` | Путь к INI-файлу, по умолчанию `config.ini`. |
| `--backend` | `run.py` | `file` (JSON) или `sqlite` (SQLite); по умолчанию `file`. |
| `--test-mode` | `run.py` | Пропускает реальное преобразование изображений. |
| `--host` | `run.py` | Интерфейс сервера, по умолчанию `127.0.0.1`. |
| `--port` | `run.py` | Порт сервера, по умолчанию `8000`. |
| `input`, `output` | `src.converter` | Позиционные пути к входному GIF и выходному JPEG. |
| `data/uploads/` | проект | Каталог входных файлов для API. |
| `data/outputs/` | проект | Каталог преобразованных JPEG. |
| `MAX_CONVERSION_SECONDS` | `src/service.py` | Тайм-аут процесса конвертации: 60 секунд. |
| `JPEG_QUALITY` | `src/converter.py` | Качество сохранения JPEG: 90. |
| `BACKGROUND_COLOR` | `src/converter.py` | Белый фон для прозрачных кадров. |
| `max_examples`, `stateful_step_count` | `tests/test_mbt.py` | Число примеров Hypothesis (12) и шагов (10). |

Зависимости перечислены в `requirements.txt`: `bottle`, `Pillow`,
`hypothesis`, `coverage`. Установка производится одной командой из раздела
«Установка». Файлы настроек, базы данных и изображения исключены из Git.

## Структура

```text
.
├── .gitignore
├── README.md
├── config.ini.example
├── requirements.txt
├── run.py
├── run.sh
├── run.bat
├── scripts/
│   ├── __init__.py
│   ├── demo_three_gifs.py
│   └── create_sample.py
├── src/
│   ├── __init__.py
│   ├── converter.py
│   ├── api.py
│   ├── client.py
│   ├── service.py
│   └── storage.py
└── tests/
    ├── __init__.py
    ├── test_converter.py
    └── test_mbt.py
```

После этапа 2 и 3 делайте отдельные коммиты:

```bash
git add src run.py run.sh run.bat requirements.txt config.ini.example README.md tests

git commit -m "feat(api): add Bottle endpoints and hypothesis MBT"

git add src/storage.py README.md tests/test_mbt.py

git commit -m "feat(db): add SQLite storage with SQL queries"
```

**Важно:** в окончательном репозитории история должна отражать этапы 1 → 2 → 3. Чтобы избежать бессодержательных или пустых коммитов, фиксируйте файлы именно по мере выполнения работы, а не исполняйте все три команды над уже полностью закоммиченным проектом.

## Обоснования для защиты

- **Почему асинхронно?** HTTP-запрос создания задания не дожидается завершения обработки картинки: функция передаёт выполнение `ThreadPoolExecutor`, а фоновой исполнитель вызывает CLI через `subprocess`. Состояние отслеживается отдельным HTTP-запросом.
- **Почему subprocess?** Так требует методичка, и программа-конвертер может работать независимо от HTTP-сервера.
- **Зачем test mode?** Он позволяет тестам быстро и без GIF-файлов проверить бизнес-переходы и все HTTP-маршруты.
- **Зачем MBT?** Hypothesis генерирует последовательности действий над API и проверяет инварианты данных.
- **Почему SQLite?** Этап 3 требует сменить файловое хранение на реляционную БД без изменения маршрутов или интерфейса слоя хранения.

Сервер рассчитан на локальную учебную демонстрацию. Для размещения в открытой сети необходимы HTTPS, ограничения размеров файлов и отдельная система безопасной загрузки.
