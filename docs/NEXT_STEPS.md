# ✅ Наступні кроки для завершення проекту

## 📦 Що вже готово:

✅ **Основна архітектура проекту**
- Структура директорій
- Конфігураційні файли (config.yaml, .env)
- Модульна система

✅ **Модулі ядра** (100% готові):
- `config.py` - Управління конфігурацією
- `logger.py` - Система логування
- `google_sheets.py` - Інтеграція з Google Sheets
- `telegram_bot.py` - Telegram сповіщення
- `pricing.py` - Розрахунок цін за формулою
- `sku_matcher.py` - Співставлення SKU

✅ **Deployment скрипти**:
- `setup.sh` - Автоматична установка на VPS
- `run_repricer.sh` - Запуск репрайсера
- Systemd service для адмін-панелі
- Cron налаштування

✅ **Документація**:
- DEPLOYMENT_GUIDE.md - Повна інструкція по розгортанню
- Інструкція створення Google Service Account
- README з описом проекту

---

## 🚧 Що потрібно завершити:

### 1. **Скрапери** (пріоритет #1)

Потрібно адаптувати ваші існуючі скрапери під нову структуру:

#### **A. Emma Mason Scraper** (`app/scrapers/emmamason.py`)
**Базовий код є в:** `emmamason++1.py`

**Що зробити:**
1. Створити клас `EmmaMasonScraper`
2. Метод `scrape_products(urls: List[str])` - парсити ціни зі списку URL
3. Повертати список `[{'sku': ..., 'price': ..., 'url': ...}]`
4. Інтегрувати curl-cffi для обходу Cloudflare
5. Додати обробку помилок та retry логіку

**Шаблон:**
```python
class EmmaMasonScraper:
    def __init__(self, config):
        self.config = config
        self.logger = get_logger("emmamason")
    
    def scrape_products(self, urls):
        results = []
        for url in urls:
            # Парсити ціну з URL
            price = self._get_price(url)
            results.append({
                'url': url,
                'price': price,
                'scraped_at': datetime.now()
            })
        return results
```

#### **B. 1StopBedrooms Scraper** (`app/scrapers/onestopbedrooms.py`)
**Базовий код є в:** `1stopbedrooms__1.py`

**Що зробити:**
1. Створити клас `OneStopBedroomsScraper`
2. Метод `scrape_all_products()` - парсити всі товари
3. Використати GraphQL API (код вже є)
4. Повертати `[{'sku': ..., 'brand': ..., 'price': ..., 'url': ...}]`

#### **C. Coleman Furniture Scraper** (`app/scrapers/coleman.py`)
**Базовий код є в:** `colemanfurniture__1.py`

**Що зробити:**
1. Створити клас `ColemanScraper`
2. Метод `scrape_all_products()` - парсити всі товари
3. Використати їх API (код вже є)
4. Повертати структуровані дані

#### **D. AFA Stores Scraper** (`app/scrapers/afa.py`)
**Базовий код є в:** `afastore_all_category.py`

**Що зробити:**
1. Створити клас `AFAScraper`
2. Використати cloudscraper
3. Парсити всі категорії та товари

---

### 2. **Інтеграція скраперів в main.py** (пріоритет #2)

В `app/main.py` потрібно реалізувати:

```python
def _scrape_client_prices(self, products):
    """Парсити ціни клієнта"""
    scraper = EmmaMasonScraper(self.config.get_scraper_config('emmamason'))
    
    # Отримати список URL з products
    urls = [p['url'] for p in products if p.get('url')]
    
    # Парсити
    prices = scraper.scrape_products(urls)
    
    # Оновити products
    for product in products:
        url = product.get('url')
        price_data = next((p for p in prices if p['url'] == url), None)
        if price_data:
            product['our_price'] = price_data['price']
```

Аналогічно для конкурентів.

---

### 3. **Telegram Bot команди** (пріоритет #3)

Вже готовий! Файл `app/telegram_commands.py`

**Треба тільки:**
1. Запустити бота: `./run_telegram_bot.sh`
2. Або через systemd: `sudo systemctl start repricer-telegram`
3. Відкрити Telegram → /start

---

### 4. **Тестування** (пріоритет #4)

**Створити unit тести:**
```bash
tests/
├── test_pricing.py
├── test_sku_matcher.py
├── test_scrapers.py
└── test_google_sheets.py
```

**Запуск тестів:**
```bash
python -m pytest tests/
```

---

## 📝 Рекомендований план виконання:

### **Тиждень 1: Скрапери**
- День 1-2: Emma Mason scraper
- День 3: 1StopBedrooms scraper
- День 4: Coleman scraper
- День 5: AFA scraper
- День 6-7: Тестування скраперів

### **Тиждень 2: Інтеграція**
- День 1-2: Інтеграція скраперів у main.py
- День 3-4: SKU matching між товарами
- День 5: Google Sheets оновлення (batch update)
- День 6: Price History збереження
- День 7: Тестування повного циклу

### **Тиждень 3: Telegram Bot та фіналізація**
- День 1-2: Тестування Telegram команд
- День 3-4: Google Sheets Config інтеграція
- День 5: Deployment на VPS
- День 6-7: Тестування на production даних

### **Тиждень 4: Фіналізація**
- День 1-2: Тестування на production даних
- День 3-4: Оптимізація продуктивності
- День 5: Документація
- День 6-7: Monitoring та налагодження

---

## 🛠️ Інструменти для розробки:

### **Локальна розробка:**
```bash
# Створити віртуальне середовище
python3 -m venv venv
source venv/bin/activate

# Встановити залежності
pip install -r requirements.txt

# Тестовий запуск
python app/main.py --test
```

### **Git workflow:**
```bash
# Створити репозиторій
git init
git add .
git commit -m "Initial commit: project structure"

# Створити бранчі для features
git checkout -b feature/emma-scraper
git checkout -b feature/admin-panel
```

---

## 📚 Додаткові ресурси:

**Документація бібліотек:**
- gspread: https://docs.gspread.org/
- python-telegram-bot: https://docs.python-telegram-bot.org/
- Flask: https://flask.palletsprojects.com/
- curl-cffi: https://github.com/yifeikong/curl_cffi

**Корисні статті:**
- Web Scraping Best Practices
- Google Sheets API Batch Operations
- Flask Admin Dashboard Tutorial

---

## ✅ Чеклист готовності до production:

### **Код:**
- [ ] Всі 4 скрапери реалізовані
- [ ] SKU matching працює коректно
- [ ] Pricing formula протестована
- [ ] Google Sheets update працює
- [ ] Telegram сповіщення надсилаються
- [ ] Адмін-панель функціонує
- [ ] Error handling везде присутній
- [ ] Logging детальний та інформативний

### **Тестування:**
- [ ] Unit тести написані
- [ ] Integration тести пройшли
- [ ] Тестовий запуск на 10 товарах
- [ ] Тестовий запуск на 100 товарах
- [ ] Full run на всіх 8821 товарах
- [ ] Час виконання < 60 хвилин

### **Deployment:**
- [ ] VPS налаштований
- [ ] Cron працює
- [ ] Логи пишуться
- [ ] Firewall налаштований
- [ ] Backups налаштовані
- [ ] Monitoring працює

### **Документація:**
- [ ] README актуальний
- [ ] Deployment guide повний
- [ ] API документація
- [ ] Troubleshooting guide
- [ ] Handover document для клієнта

---

## 📧 Контакт

**Якщо виникнуть питання під час розробки:**
1. Перевірити logs/
2. Подивитись docs/TROUBLESHOOTING.md
3. Перевірити конфігурацію config.yaml

**Успіхів у завершенні проекту! 🚀**

---

## 📎 Додатки:

### **A. Приклад структури даних після парсингу:**
```python
product = {
    'sku': 'ABC123',
    'brand': 'Ashley',
    'cost': 100.0,
    'current_price': 150.0,
    'our_url': 'https://emmamason.com/...',
    'site1_price': 145.0,
    'site1_url': 'https://1stopbedrooms.com/...',
    'site2_price': 148.0,
    'site2_url': 'https://coleman.com/...',
    'site3_price': None,  # Немає на сайті
    'site3_url': None,
    'suggested_price': 144.0,  # min(145, 148) - 1
    'pricing_metadata': {...}
}
```

### **B. Формат Google Sheets update:**
```python
updates = [
    {
        'range': 'D2',  # Our Sales Price
        'values': [[150.0]]
    },
    {
        'range': 'E2',  # Suggest Sales Price
        'values': [[144.0]]
    },
    {
        'range': 'G2:H2',  # Site 1
        'values': [[145.0, 'https://...']]
    }
]
```

### **C. Приклад Telegram повідомлення:**
```
✅ Furniture Repricer Completed

⏱ Duration: 45.3 minutes
📦 Total products: 8821
✏️ Updated: 234
❌ Errors: 12

Competitors:
✅ 1stopbedrooms: 1817 products
✅ Coleman: 147000 products
⚠️ AFA: timeout (retry needed)

Next run in 5 hours
```
