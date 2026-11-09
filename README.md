# GIF → JPEG — вариант №12, этапы 1 и 2

Выполнен CLI-конвертер и веб-сервер Bottle с XML и HTTP Basic Auth.

```bash
python -m pip install -r requirements.txt
cp config.ini.example config.ini
python run.py --backend file --test-mode
```

Для реального выполнения создайте `sample.gif` через
`python -m scripts.create_sample` и запустите сервер без `--test-mode`.

API-пути: `/core/api/stable/add-participant`, `read-participant`,
`retrieve-participant`, `add-assignment`, `read-assignment/:participant`,
`retrieve-assignment`, `read-result/:assignment`, `retrieve-result`,
`read-report`. Все ответы в XML. Девять маршрутов проверяются через
Hypothesis RuleBasedStateMachine и API-клиент.

```bash
python -m coverage run --branch --source=src -m unittest tests.test_mbt
python -m coverage report -m
```
