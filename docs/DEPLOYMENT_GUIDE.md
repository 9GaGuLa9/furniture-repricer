# 🚀 Furniture Repricer - Deployment Guide

## 📋 Передумови

### Що вам потрібно:
- ✅ VPS сервер (Ubuntu 20.04+ або Debian 11+)
- ✅ Root/sudo доступ до сервера
- ✅ Google Service Account credentials (JSON файл)
- ✅ Telegram Bot Token та Chat ID
- ✅ SSH клієнт для підключення

### Рекомендовані характеристики VPS:
- **RAM:** 4GB мінімум
- **CPU:** 2 cores
- **Disk:** 50GB
- **OS:** Ubuntu 22.04 LTS

---

## 🔧 Крок 1: Підключення до VPS

```bash
# З вашого комп'ютера
ssh root@your-vps-ip

# Або якщо є окремий користувач
ssh username@your-vps-ip
```

---

## 📦 Крок 2: Завантаження проекту

### Варіант A: Через Git (якщо є репозиторій)
```bash
cd /opt
git clone https://your-repo-url/furniture-repricer.git
cd furniture-repricer
```

### Варіант B: Завантаження архіву
```bash
cd /opt

# Завантажити архів на сервер (з вашого комп'ютера)
scp furniture-repricer.tar.gz root@your-vps-ip:/opt/

# Розпакувати
tar -xzf furniture-repricer.tar.gz
cd furniture-repricer
```

---

## ⚙️ Крок 3: Запуск установки

```bash
# Зробити setup скрипт виконуваним
chmod +x setup.sh

# Запустити установку
sudo ./setup.sh
```

**Що робить setup.sh:**
- Оновлює систему
- Встановлює Python 3.10+ та залежності
- Створює віртуальне середовище
- Встановлює Python пакети
- Налаштовує systemd service для адмін-панелі
- Налаштовує cron для автоматичного запуску
- Створює необхідні директорії

**Тривалість:** ~5-10 хвилин

---

## 🔑 Крок 4: Налаштування credentials

### 4.1. Google Service Account

```bash
# Завантажити JSON файл на сервер
scp service_account.json root@your-vps-ip:/opt/furniture-repricer/credentials/

# Або створити файл та вставити вміст
nano credentials/service_account.json
# Вставити JSON, Ctrl+X, Y, Enter

# Встановити права
chmod 600 credentials/service_account.json
```

### 4.2. Environment Variables

```bash
# Редагувати .env файл
nano .env
```

**Заповнити:**
```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Admin Panel
ADMIN_PASSWORD=your_secure_password

# Debug (для production залишити false)
DEBUG=false
```

**Зберегти:** Ctrl+X, Y, Enter

---

## ✅ Крок 5: Тестування

### 5.1. Перевірити конфігурацію
```bash
# Перевірити що всі файли на місці
ls -la credentials/
ls -la .env

# Перевірити Python пакети
source venv/bin/activate
python -c "import gspread, requests; print('OK')"
```

### 5.2. Тестовий запуск (1 товар)
```bash
./run_repricer.sh --test
```

**Якщо все ОК, ви побачите:**
```
==================================
Starting Furniture Repricer
==================================
[INFO] Furniture Repricer Started
[INFO] Mode: TEST
[INFO] Initializing Google Sheets client...
[INFO] ✓ Connected to Google Sheets API
[INFO] Initializing Telegram notifier...
...
✓ Repricer completed successfully
```

### 5.3. Перевірити Telegram
```bash
# Має прийти повідомлення в Telegram
# "🧪 Furniture Repricer Started TEST MODE"
```

---

## 💬 Крок 6: Запуск Telegram Bot

```bash
# Запустити сервіс
sudo systemctl start repricer-telegram

# Перевірити статус
sudo systemctl status repricer-telegram

# Має показати: "active (running)"
```

### Підключитись до бота:
```
1. Відкрити Telegram
2. Знайти вашого бота (по імені з @BotFather)
3. Надіслати /start
4. Надіслати /help щоб подивитись команди
```

### Тест команд:
```
/status - Перевірити статус
/run - Запустити вручну (тест)
```

---

## ⏰ Крок 7: Перевірка cron

```bash
# Подивитись налаштовані завдання
crontab -l

# Має показати:
# 0 11 * * * cd /opt/furniture-repricer && ./run_repricer.sh ...
# 0 21 * * * cd /opt/furniture-repricer && ./run_repricer.sh ...
# 0 2 * * * cd /opt/furniture-repricer && ./run_repricer.sh ...
```

**Розклад (EST):**
- 06:00 EST = 11:00 UTC
- 16:00 EST = 21:00 UTC
- 21:00 EST = 02:00 UTC (наступний день)

---

## 📊 Крок 8: Моніторинг

### Переглянути логи:
```bash
# Останні логи
tail -f logs/repricer_$(date +%Y-%m-%d).log

# Логи cron
tail -f logs/cron.log

# Логи admin панелі
sudo journalctl -u repricer-admin -f
```

### Корисні команди:
```bash
# Ручний запуск
./run_repricer.sh

# Або через Telegram
/run (в боті)

# Зупинити Telegram бота
sudo systemctl stop repricer-telegram

# Перезапустити
sudo systemctl restart repricer-telegram

# Перевірити статус
sudo systemctl status repricer-telegram

# Переглянути логи бота
sudo journalctl -u repricer-telegram -f
```

---

## 🔒 Крок 9: Безпека (опціонально)

### 9.1. Налаштувати firewall
```bash
# Дозволити тільки SSH та admin панель
ufw allow 22/tcp
ufw allow 5000/tcp
ufw enable
```

### 9.2. SSL для admin панелі (рекомендовано)
```bash
# Встановити certbot
apt-get install certbot

# Отримати сертифікат (потрібен домен)
certbot certonly --standalone -d your-domain.com

# Оновити config.yaml:
admin_panel:
  ssl:
    enabled: true
    cert_file: "/etc/letsencrypt/live/your-domain.com/fullchain.pem"
    key_file: "/etc/letsencrypt/live/your-domain.com/privkey.pem"
```

### 9.3. Змінити порт admin панелі
```bash
nano config.yaml

# Змінити:
admin_panel:
  port: 8443  # Замість 5000
```

---

## 🐛 Troubleshooting

### Проблема: "Credentials file not found"
```bash
# Перевірити файл
ls -la credentials/service_account.json

# Якщо немає - завантажити знову
scp service_account.json root@your-vps-ip:/opt/furniture-repricer/credentials/
```

### Проблема: "403 Forbidden" для Google Sheets
```bash
# Перевірити що Service Account має доступ до таблиць
# 1. Відкрити таблицю в браузері
# 2. Share → Має бути email з service_account.json
# 3. Права: Editor
```

### Проблема: "Telegram error"
```bash
# Перевірити токен та chat ID
cat .env | grep TELEGRAM

# Тест Telegram
python3 << EOF
from app.modules.telegram_bot import TelegramNotifier
import os
notifier = TelegramNotifier(os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID'))
notifier.send_test_message()
EOF
```

### Проблема: Cron не запускається
```bash
# Перевірити cron службу
sudo systemctl status cron

# Перевірити логи
grep CRON /var/log/syslog

# Перевірити права
chmod +x run_repricer.sh
```

---

## 📞 Підтримка

### Логи для діагностики:
```bash
# Зібрати всі логи
tar -czf repricer-logs.tar.gz logs/

# Завантажити на свій комп'ютер
scp root@your-vps-ip:/opt/furniture-repricer/repricer-logs.tar.gz ./
```

### Перевірка стану системи:
```bash
# Дисковий простір
df -h

# Пам'ять
free -h

# Завантаження CPU
top

# Перевірка Python процесів
ps aux | grep python
```

---

## 🔄 Оновлення проекту

```bash
cd /opt/furniture-repricer

# Backup поточної конфігурації
cp .env .env.backup
cp config.yaml config.yaml.backup

# Оновити код (якщо Git)
git pull

# Або завантажити нову версію
# scp new-version.tar.gz ...

# Оновити залежності
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Перезапустити сервіси
sudo systemctl restart repricer-admin
```

---

## ✅ Чеклист після deployment

- [ ] VPS підключений та доступний
- [ ] Проект завантажений та розпакований
- [ ] Setup.sh виконано успішно
- [ ] Google credentials додано
- [ ] .env файл налаштовано
- [ ] Тестовий запуск пройшов успішно
- [ ] Telegram сповіщення працюють
- [ ] Admin панель доступна
- [ ] Cron налаштовано та працює
- [ ] Логи пишуться коректно
- [ ] Firewall налаштовано (опціонально)
- [ ] SSL встановлено (опціонально)

---

## 🎉 Готово!

Репрайсер тепер працює автоматично 3 рази на день.

**Корисні посилання:**
- Адмін панель: http://your-vps-ip:5000/admin
- Google Sheets: https://docs.google.com/spreadsheets/d/...
- Telegram бот: @your_bot_name

**Підтримка:**
- Логи: `/opt/furniture-repricer/logs/`
- Конфігурація: `/opt/furniture-repricer/config.yaml`
- Документація: `/opt/furniture-repricer/docs/`
