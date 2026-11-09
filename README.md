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
