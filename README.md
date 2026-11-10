# Асинхронное преобразование GIF в JPEG — вариант №12

## 1. Общее описание

Проект выполнен по дисциплине «Прикладная разработка серверных частей веб-приложений на языке Питон».

**Тема курсовой работы:** «Веб-приложение с HTTP API для асинхронного преобразования файлов из формата GIF в формат JPEG».

Приложение написано на Python и состоит из трёх частей, соответствующих этапам практического задания №2:

1. **Консольный конвертер:** принимает путь к GIF-файлу и путь для сохранения JPEG. Использует библиотеку Pillow. Для анимированного GIF преобразует первый кадр, прозрачность заменяет белым фоном. Работа демонстрируется на трёх входных файлах.
2. **HTTP API:** реализовано на Bottle. Предоставляет девять маршрутов для создания и получения участников (`Participant`), заданий (`Assignment`), результатов (`Result`) и формирования отчёта. Все ответы возвращаются в XML. Доступ защищён HTTP Basic Authentication (RFC 7617). Данные хранятся в JSON-файле.
3. **SQLite:** вместо файлового JSON-хранилища используется реляционная СУБД SQLite. Доступ к таблицам реализован обычными SQL-запросами без ORM. Маршруты HTTP API не изменяются.

При создании задания сервер записывает его в хранилище и передаёт обработку в `ThreadPoolExecutor`. Рабочий поток запускает консольный конвертер через `subprocess.run()`. Клиент может отдельно запросить статус задания и результат. В тестовом режиме (`--test-mode`) реальное преобразование изображений не запускается.

Для тестирования HTTP API используется Hypothesis `RuleBasedStateMachine` и класс API-клиента. Покрытие ветвей измеряется библиотекой Coverage.

**Структура проекта:** `src/` — исходный код, `tests/` — тесты, `scripts/` — вспомогательные команды, `run.py` — запуск HTTP-сервера, `run.sh` и `run.bat` — скрипты запуска, `requirements.txt` — зависимости, `config.ini.example` — образец настроек авторизации. Рабочие данные создаются внутри `data/` и не включаются в Git.

## 2. Описание всех функций и настроек

### 2.1. Конвертер и запуск приложения

| Файл | Функция | Назначение |
|---|---|---|
| `src/converter.py` | `convert_gif(input_path, output_path)` | Проверяет, что входные данные содержат GIF, преобразует первый кадр в RGB на белом фоне и сохраняет JPEG. |
| `src/converter.py` | `main(argv)` | Читает аргументы командной строки, запускает конвертацию и сообщает об ошибках. |
| `run.py` | `load_auth(config_path)` | Читает имя пользователя и пароль из конфигурационного INI-файла. |
| `run.py` | `main(argv)` | Обрабатывает параметры сервера, выбирает хранилище, создаёт сервис и запускает Bottle. |
| `scripts/create_sample.py` | `main()` | Создаёт пример анимированного GIF для проверки API. |
| `scripts/demo_three_gifs.py` | `main()` | Проверяет конвертацию на трёх GIF разных размеров. |

### 2.2. HTTP API (`src/api.py`)

| Функция | Назначение |
|---|---|
| `xml_document` | Преобразует одну запись или список записей в XML. |
| `_is_authorized` | Проверяет заголовок HTTP Basic Authentication. |
| `wrap_result` | Формирует XML-ответ и возвращает HTTP 400 или 404 при ошибке запроса или отсутствии записи. |
| `required_id` | Получает и проверяет положительный идентификатор из строки запроса. |
| `register_participant_routes` | Регистрирует три маршрута для `Participant`. |
| `register_assignment_routes` | Регистрирует три маршрута для `Assignment`. |
| `register_result_routes` | Регистрирует два маршрута для `Result`. |
| `create_app` | Создаёт приложение Bottle, хуки авторизации и маршруты, включая отчёт. |

Внутренние обработчики `add_participant`, `read_participant`, `retrieve_participant`, `add_assignment`, `read_assignment`, `retrieve_assignment`, `read_result` и `retrieve_result` выполняют соответствующие операции с данными. Обработчик `authenticate` проверяет авторизацию перед запросом; `response_type` устанавливает тип ответа XML.

### 2.3. Асинхронное выполнение (`src/service.py`)

| Метод класса `ConversionService` | Назначение |
|---|---|
| `__init__` | Создаёт каталоги входных и выходных файлов, инициализирует пул рабочих потоков. |
| `add_assignment` | Проверяет входные данные, создаёт задание и результат, отправляет задачу на выполнение. |
| `_convert` | Запускает CLI-конвертер с помощью `subprocess.run()` и обрабатывает результат запуска. |
| `_finish` | Сохраняет окончательные статусы задания и результата. |
| `close` | Останавливает пул потоков после завершения задач. |

Возможные состояния задания: `queued`, `running`, `done`, `error`, а в тестовом режиме — `test`.

### 2.4. Хранение данных (`src/storage.py`)

Функции `_now()` и `_where_matches()` возвращают текущее время и проверяют соответствие записи условиям фильтрации.

Классы `FileStore` и `SQLiteStore` предоставляют одинаковые операции:

| Метод | Назначение |
|---|---|
| `__init__` | Открывает или создаёт хранилище. |
| `participant_add`, `participant_read`, `participant_retrieve` | Создание участника, поиск участников, получение участника по ID. |
| `assignment_add`, `assignment_read`, `assignment_retrieve` | Создание задания, поиск заданий, получение задания по ID. |
| `assignment_stage` | Изменение статуса задания. |
| `result_add`, `result_read`, `result_retrieve` | Создание результата, поиск результатов, получение результата по ID. |
| `result_update` | Изменение записи результата. |
| `report_read` | Формирование отчёта по формуле (12) задания. |

Внутренние методы `FileStore`: `_load` (чтение JSON), `_save` (сохранение JSON), `_add` (добавление), `_read` (поиск), `_retrieve` (чтение по ID), `_update` (изменение записи).

Внутренние методы `SQLiteStore`: `_connect` (соединение и транзакция SQLite), `_select` (SELECT), `_insert` (INSERT), `_update` (UPDATE). Запросы используют параметры вместо подстановки значений непосредственно в SQL.

Отчёт `report_read` возвращает поля `input`, `platform`, `cache_hit`. Он связывает `Participant` и `Assignment`, затем присоединяет `Result`, созданные за последние **5 минут**. Если подходящего результата нет, `cache_hit` имеет значение `null`.

### 2.5. HTTP-клиент (`src/client.py`)

Класс `ApiClient` содержит `__init__` (сохранение адреса сервера и данных Basic Auth) и `_request` (отправка HTTP-запроса и разбор XML). Публичные методы именуются по маршрутам варианта №12 с заменой `/` и `-` на `_`:

| Метод | Действие |
|---|---|
| `core_api_stable_add_participant` | Создать участника. |
| `core_api_stable_read_participant` | Найти участников. |
| `core_api_stable_retrieve_participant` | Получить участника по ID. |
| `core_api_stable_add_assignment` | Создать задание. |
| `core_api_stable_read_assignment` | Найти задания участника. |
| `core_api_stable_retrieve_assignment` | Получить задание по ID. |
| `core_api_stable_read_result` | Найти результаты задания. |
| `core_api_stable_retrieve_result` | Получить результат по ID. |
| `core_api_stable_read_report` | Получить отчёт. |

### 2.6. Тестовые функции

- `tests/test_converter.py`: `test_gif_converts_to_jpeg` проверяет успешную конвертацию; `test_rejects_non_gif` проверяет отклонение файла другого формата.
- `tests/test_mbt.py`: `QuietHandler.log_message` отключает лишние записи журнала; `ApiMachine.__init__` запускает тестовое приложение; `teardown` освобождает ресурсы; `initial_workflow` вызывает все девять маршрутов; `check_unassigned_participant` проверяет отчёт для участника без заданий; `unauthenticated_is_rejected` проверяет HTTP 401; `new_participant` и `new_assignment` генерируют операции создания; `inspect_assignment` проверяет чтение задания; `read_model_matches` проверяет соответствие состояния API ожидаемой модели.
- `FileApiMachine` и `SQLiteApiMachine` запускают одну машину состояний для файловой модели и SQLite.

### 2.7. Настройки

| Настройка | Место | Значение |
|---|---|---|
| `username`, `password` | `[auth]` в `config.ini` | Учётные данные для HTTP Basic Auth. |
| `--backend` | `run.py` | `file` (по умолчанию) или `sqlite`. |
| `--config` | `run.py` | Путь к `config.ini`. |
| `--test-mode` | `run.py` | Пропускает реальную конвертацию в тестах. |
| `--host` | `run.py` | Адрес сервера, по умолчанию `127.0.0.1`. |
| `--port` | `run.py` | Порт сервера, по умолчанию `8000`. |
| `input`, `output` | `src.converter` | Пути к исходному GIF и выходному JPEG. |
| `JPEG_QUALITY` | `src/converter.py` | Качество JPEG — 90. |
| `BACKGROUND_COLOR` | `src/converter.py` | Белый фон при обработке прозрачных изображений. |
| `MAX_CONVERSION_SECONDS` | `src/service.py` | Предельное время выполнения процесса — 60 секунд. |
| `max_examples`, `stateful_step_count` | `tests/test_mbt.py` | Настройки Hypothesis — 12 примеров и 10 шагов. |

Входные изображения размещаются в `data/uploads/`, готовые JPEG — в `data/outputs/`. Файловое хранилище использует `data/records.json`, SQLite — `data/database.sqlite3`. Эти пути исключены из Git с помощью `.gitignore`.

## 3. Команды для сборки проекта и запуска тестов

Требуется Python 3.10 или новее. Все команды выполняются из корня репозитория. Для проекта на Python отдельная компиляция не требуется: подготовка состоит из установки зависимостей.

**Установка зависимостей:**

```bash
python -m pip install -r requirements.txt
```

**Настройка авторизации (Linux / GitHub Codespaces):**

```bash
cp config.ini.example config.ini
```

В Windows можно использовать `copy config.ini.example config.ini`. При необходимости измените значения в `config.ini`. Этот файл не публикуется в репозитории.

**Запуск консольной утилиты и демонстрация на трёх GIF:**

```bash
python -m scripts.create_sample
python -m src.converter data/uploads/sample.gif data/outputs/sample.jpg
python -m scripts.demo_three_gifs
```

**Запуск API с файловым хранилищем:**

```bash
python run.py --backend file
```

**Запуск API с SQLite:**

```bash
python run.py --backend sqlite
```

**Запуск в тестовом режиме без конвертации:**

```bash
python run.py --backend sqlite --test-mode
```

По умолчанию сервер доступен по адресу `http://127.0.0.1:8000`. Остановка — `Ctrl+C`.

**Запуск всех автоматических тестов:**

```bash
python -m unittest discover -s tests -v
```

**Проверка MBT для обеих моделей и формирование отчёта покрытия ветвей:**

```bash
python -m coverage erase
python -m coverage run --branch --source=src -m unittest tests.test_mbt
python -m coverage report -m
python -m coverage html
```

HTML-отчёт создаётся в `htmlcov/index.html`. Покрытие HTTP API измеряется при запуске тестов Hypothesis отдельно от модульных тестов конвертера.

## 4. Примеры использования

Перед отправкой запросов создайте пример GIF и запустите сервер в отдельном терминале:

```bash
python -m scripts.create_sample
python run.py --backend sqlite
```

В другом терминале выполните запросы с учётными данными из вашего `config.ini` (ниже показаны демонстрационные значения из `config.ini.example`). Все ответы API содержат XML.

**4.1. Создание участника:**

```bash
curl -i -u admin:change-me -X POST "http://127.0.0.1:8000/core/api/stable/add-participant?locale=ru&platform=windows"
```

**4.2. Поиск и чтение участника:**

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-participant?platform=windows"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-participant?id=1"
```

**4.3. Создание задания на конвертацию:**

```bash
curl -i -u admin:change-me -X POST "http://127.0.0.1:8000/core/api/stable/add-assignment?participant=1&input=sample.gif&tags=demo"
```

Сервер возвращает XML с идентификатором и текущим состоянием задания, не ожидая завершения фоновой операции.

**4.4. Поиск и чтение задания:**

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-assignment/1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-assignment?id=1"
```

После завершения обработки `stage` принимает значение `done`. Выходной файл для задания №1: `data/outputs/1_sample.jpg`.

**4.5. Поиск и чтение результата:**

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-result/1"
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-result?id=1"
```

В результате указываются название JPEG (`response`), статус (`stage`) и информация об ошибке (`exception`).

**4.6. Построение отчёта по формуле (12):**

```bash
curl -u admin:change-me "http://127.0.0.1:8000/core/api/stable/read-report"
```

Пример XML для задания с доступным результатом:

```xml
<response>
  <items>
    <item>
      <input>sample.gif</input>
      <platform>windows</platform>
      <cache_hit>0</cache_hit>
    </item>
  </items>
</response>
```

Если результат старше пяти минут, поле `cache_hit` может возвращаться как `<cache_hit null="true" />`.

**4.7. Пример обработки ошибок:**

```bash
curl -i -u admin:change-me "http://127.0.0.1:8000/core/api/stable/retrieve-assignment?id=999999"
curl -i -u admin:change-me -X POST "http://127.0.0.1:8000/core/api/stable/add-assignment?participant=1&input=missing.gif&tags=invalid"
```

Для отсутствующей записи сервер возвращает HTTP `404 Not Found`, для отсутствующего входного GIF — HTTP `400 Bad Request`, для запроса без корректной авторизации — HTTP `401 Unauthorized`.
