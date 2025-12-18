# 🔧 ВИПРАВЛЕННЯ ImportError - Інструкція

## ❌ Проблема яку ви мали:
```
ImportError: attempted relative import with no known parent package
```

## ✅ Що виправлено:

### 1. Створено структуру пакетів:
```
app/
├── __init__.py          ← Робить app пакетом
├── scrapers/
│   ├── __init__.py      ← Робить scrapers пакетом
│   └── emmamason.py     ← ВИПРАВЛЕНИЙ scraper
└── modules/
    └── __init__.py      ← Робить modules пакетом
```

### 2. Виправлено emmamason.py:
- Додано sys.path для запуску напряму
- Гнучкі імпорти (try/except)
- Працює ВСІ способи запуску

### 3. Створено допоміжні скрипти:
- `test_scraper.py` - тестування scraper
- `check_structure.py` - перевірка структури
- `run_repricer.py` - запуск системи

---

## 🚀 Як використовувати:

### Крок 1: Розпакувати архів
```bash
# Розпакуйте furniture-repricer-fixed.zip
# В вашу директорію: D:\...\furniture-repricer\
```

### Крок 2: Встановити залежності (якщо ще не)
```bash
pip install beautifulsoup4 requests lxml
pip install curl-cffi  # опціонально
```

### Крок 3: Перевірити структуру
```bash
cd D:\...\furniture-repricer
python check_structure.py
```

Має показати всі ✅

### Крок 4: Запустити тест
```bash
python test_scraper.py
```

---

## 📁 Способи запуску:

### ✅ Спосіб 1: Тестовий скрипт (найпростіший)
```bash
python test_scraper.py
```

### ✅ Спосіб 2: Як модуль
```bash
python -m app.scrapers.emmamason
```

### ✅ Спосіб 3: Напряму (тепер працює!)
```bash
python app\scrapers\emmamason.py
```

### ✅ Спосіб 4: Через runner
```bash
python run_repricer.py --test
```

---

## 🔍 Що в архіві:

```
furniture-repricer-fixed/
├── app/
│   ├── __init__.py
│   ├── scrapers/
│   │   ├── __init__.py
│   │   └── emmamason.py      ← ВИПРАВЛЕНИЙ
│   └── modules/
│       └── __init__.py
│
├── test_scraper.py            ← Тестування
├── check_structure.py         ← Перевірка
├── run_repricer.py            ← Запуск
└── README_FIX.md              ← Ця інструкція
```

---

## 💡 Ключові зміни в emmamason.py:

### Було:
```python
from ..modules.logger import get_logger  # НЕ працює напряму
```

### Стало:
```python
# Додано:
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Гнучкий імпорт:
try:
    from ..modules.logger import get_logger
except (ImportError, ValueError):
    from app.modules.logger import get_logger  # Fallback
```

---

## ✅ Перевірка що все працює:

```bash
# 1. Структура
python check_structure.py
# Має показати: ✅ ВСЕ ПРАЦЮЄ!

# 2. Тест scraper
python test_scraper.py
# Має запуститись без ImportError

# 3. Напряму
python app\scrapers\emmamason.py
# Теж має працювати!
```

---

## 🐛 Якщо все ще помилки:

### `No module named 'beautifulsoup4'`
```bash
pip install beautifulsoup4 lxml requests
```

### `No module named 'app'`
```bash
# Перевірте що запускаєте з кореневої директорії:
cd D:\...\furniture-repricer
pwd  # має показати правильний шлях
```

---

## 🎉 Готово!

Тепер можете:
1. Запускати scraper різними способами
2. Інтегрувати в main.py
3. Додавати інші scrapers

---

**Успіхів! 🚀**
