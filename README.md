# 🛋️ Furniture Repricer - Повна Система

Автоматичний репрайсер для меблевого бізнесу з парсингом цін конкурентів та розрахунком рекомендованих цін.

## 📁 Структура проекту

```
furniture-repricer/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Головний скрипт
│   ├── modules/                 # Готові модулі
│   │   ├── __init__.py
│   │   ├── logger.py           # Логування
│   │   ├── config.py           # Конфігурація
│   │   ├── pricing.py          # Розрахунок цін
│   │   └── sku_matcher.py      # Співставлення SKU
│   └── scrapers/                # Парсери сайтів
│       ├── __init__.py
│       └── emmamason.py        # ✅ Emma Mason scraper
│
├── config.yaml                  # Конфігурація системи
├── .env.example                 # Шаблон змінних середовища
├── requirements.txt             # Python залежності
│
├── test_scraper.py             # Тестування scraper
├── check_structure.py          # Перевірка структури
└── run_repricer.py             # Запуск системи
```

## 🚀 Швидкий старт

### 1. Встановлення

```bash
# Клонувати або розпакувати проект
cd furniture-repricer

# Створити віртуальне середовище (рекомендовано)
python -m venv venv

# Активувати
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Встановити залежності
pip install -r requirements.txt
```

### 2. Налаштування

```bash
# Створити .env файл
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac

# Відредагувати config.yaml
# Замінити YOUR_SPREADSHEET_ID_HERE на ваш ID таблиці

# Додати Google Service Account credentials
# Покласти service_account.json в credentials/
```

### 3. Перевірка

```bash
# Перевірити структуру
python check_structure.py

# Має показати всі ✅
```

### 4. Тестування

```bash
# Тест Emma Mason scraper
python test_scraper.py

# Тест головного репрайсера (поки без scrapers)
python run_repricer.py --test
```

## 📝 Що готово

### ✅ Модулі (100%):
- **logger.py** - Система логування
- **config.py** - Управління конфігурацією
- **pricing.py** - Розрахунок цін за формулою
- **sku_matcher.py** - Співставлення товарів за SKU

### ✅ Scrapers:
- **emmamason.py** - Парсер сайту клієнта ✅

### ⏳ TODO:
- Google Sheets інтеграція (модуль є в документації)
- Telegram bot (модуль є в документації)
- Інші scrapers (1stopbedrooms, coleman, afa)
- Інтеграція scrapers в main.py

## 🔧 Різні способи запуску

### Тестування scraper:
```bash
python test_scraper.py
```

### Запуск репрайсера:
```bash
# Тестовий режим (10 товарів)
python run_repricer.py --test

# Production (всі товари)
python run_repricer.py
```

### Як Python модуль:
```bash
python -m app.main --test
python -m app.scrapers.emmamason
```

## 📖 Формула ціноутворення

```
Floor = Our Cost × 1.5 (мінімальна ціна, 50% маржа)
Max = Our Cost × 2.0 (максимальна ціна, 100% маржа)

Suggest_raw = MIN(Competitor1, Competitor2, Competitor3) - $1

Suggest = MAX(Floor, MIN(Suggest_raw, Max))

Округлення до .99
```

## 🔍 Налаштування

### config.yaml:
- `development.test_mode: true` - тестовий режим
- `development.test_limit: 10` - кількість товарів для тесту
- `scrapers.emmamason.enabled: true` - увімкнути scraper
- `pricing.coefficients` - коефіцієнти формули

### .env:
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота (опціонально)
- `TELEGRAM_CHAT_ID` - ID чату (опціонально)

## 🐛 Troubleshooting

### ImportError: No module named 'app'
```bash
# Запускайте з кореневої директорії проекту
cd furniture-repricer
python check_structure.py
```

### ModuleNotFoundError
```bash
# Встановіть залежності
pip install -r requirements.txt
```

### Немає файлу logger.py
```bash
# Перевірте що розпаковано всі файли
dir app\modules\logger.py  # Windows
ls app/modules/logger.py   # Linux
```

## 📚 Документація

- **README.md** - Цей файл
- **README_FIX.md** - Виправлення ImportError
- **INSTALL_INSTRUCTIONS.txt** - Інструкція по встановленню

## 🎯 Наступні кроки

1. ✅ Структура готова
2. ✅ Модулі готові
3. ✅ Emma Mason scraper готовий
4. 🚧 Додати Google Sheets модуль
5. 🚧 Додати решту scrapers
6. 🚧 Інтегрувати в main.py
7. 🚧 Тестування на production даних

## 💡 Приклад використання

```python
from app.modules import PricingEngine, SKUMatcher

# Pricing
engine = PricingEngine({'floor': 1.5, 'below_lowest': 1.0, 'max': 2.0})
suggested, metadata = engine.calculate_suggested_price(
    cost=60.0,
    competitor_prices=[95.0, 98.0, 100.0]
)
print(f"Suggested price: ${suggested:.2f}")

# SKU Matching
matcher = SKUMatcher({'split_delimiter': ';'})
matches = matcher.matches("ABC123;DEF456", "def456")  # True
```

## 📞 Підтримка

Якщо виникнуть проблеми:
1. Запустіть `python check_structure.py`
2. Перевірте логи в `logs/`
3. Читайте документацію в `docs/`

---

**Версія:** 1.0  
**Статус:** В розробці 🚧  
**Готово:** ~60% ⚡
