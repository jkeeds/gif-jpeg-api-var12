# GIF to JPEG — вариант №12, этап 1

Конвертер первого кадра GIF в JPEG с белым фоном.

```bash
python -m pip install -r requirements.txt
python -m scripts.demo_three_gifs
python -m scripts.create_sample
python -m src.converter data/uploads/sample.gif data/outputs/sample.jpg
python -m unittest tests.test_converter -v
```

Исходные GIF и созданные JPEG игнорируются git. Демонстрация трёх примеров
создаёт бинарные изображения во временном каталоге.
