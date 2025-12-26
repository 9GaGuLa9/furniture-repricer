# 🐧 SCHEDULER ДЛЯ VPS - DELIVERY PACKAGE

## 📦 ЩО ВКЛЮЧЕНО:

Повна система автоматичного запуску для Linux VPS з підтримкою:
- ⏰ Multiple execution times (06:00, 16:00, 21:00 EST)
- 🌍 Timezone support
- 🔄 Systemd service (автозапуск при reboot)
- 📊 Google Sheets control
- 🐛 Error handling & logging
- 📈 Statistics tracking

---

## 📋 СТВОРЕНІ ФАЙЛИ (6 файлів):

### 🔴 CORE FILES:

| # | Файл | Розмір | Опис |
|---|------|--------|------|
| 1 | **scheduler.py** | ~600 рядків | Scheduler module з timezone support |
| 2 | **run_scheduler.py** | ~150 рядків | Daemon entry point для VPS |
| 3 | **repricer-scheduler.service** | ~50 рядків | Systemd service file |
| 4 | **requirements.txt** | Updated | + schedule + pytz |

### 📘 DOCUMENTATION:

| # | Файл | Опис |
|---|------|------|
| 5 | **VPS_SCHEDULER_SETUP.md** | Повна інструкція setup для VPS ⭐ |
| 6 | **CONFIG_SHEET_SCHEDULER.md** | Scheduler параметри для Google Sheets |

---

## 🚀 ШВИДКИЙ СТАРТ (15 хвилин):

### 1. Підключення до VPS:

```bash
ssh user@your-vps-ip
cd ~/furniture-repricer
source venv/bin/activate
```

### 2. Install dependencies:

```bash
pip install schedule==1.2.0 pytz==2024.1
```

### 3. Copy files:

```bash
# Scheduler module
cp scheduler.py app/modules/scheduler.py

# Daemon script
cp run_scheduler.py ./run_scheduler.py
chmod +x run_scheduler.py
```

### 4. Google Sheets Config:

Додати в Config sheet:
```
schedule_enabled    | TRUE
schedule_times      | 06:00,16:00,21:00
schedule_timezone   | America/New_York
```

### 5. Test:

```bash
python run_scheduler.py
# Ctrl+C після перевірки що працює
```

### 6. Setup systemd:

```bash
# Edit service file (replace YOUR_USERNAME)
nano repricer-scheduler.service

# Install service
sudo cp repricer-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable repricer-scheduler
sudo systemctl start repricer-scheduler

# Check status
sudo systemctl status repricer-scheduler
```

### 7. Monitor:

```bash
# Real-time logs
sudo journalctl -u repricer-scheduler -f
```

**Детальні інструкції:** `VPS_SCHEDULER_SETUP.md`

---

## ⚙️ КОНФІГУРАЦІЯ:

### Google Sheets параметри (3 нові):

| Parameter | Type | Default | Опис |
|-----------|------|---------|------|
| `schedule_enabled` | Boolean | FALSE | Увімкнути scheduler |
| `schedule_times` | String | 06:00,16:00,21:00 | Час запуску (HH:MM,HH:MM) |
| `schedule_timezone` | String | America/New_York | Часовий пояс |

### Приклади:

**Production (3x daily):**
```
schedule_enabled   | TRUE
schedule_times     | 06:00,16:00,21:00
schedule_timezone  | America/New_York
```

**High frequency (6x daily):**
```
schedule_enabled   | TRUE
schedule_times     | 00:00,04:00,08:00,12:00,16:00,20:00
schedule_timezone  | America/New_York
```

**Conservative (1x daily):**
```
schedule_enabled   | TRUE
schedule_times     | 06:00
schedule_timezone  | America/New_York
```

---

## 🔧 УПРАВЛІННЯ:

### Основні команди:

```bash
# Старт
sudo systemctl start repricer-scheduler

# Стоп
sudo systemctl stop repricer-scheduler

# Рестарт (після зміни config)
sudo systemctl restart repricer-scheduler

# Статус
sudo systemctl status repricer-scheduler

# Логи
sudo journalctl -u repricer-scheduler -f
```

### Зміна налаштувань:

**1. Змінити час запуску:**
- В Google Sheets Config: `schedule_times | 08:00,14:00,20:00`
- Restart: `sudo systemctl restart repricer-scheduler`

**2. Вимкнути scheduler:**
- В Google Sheets Config: `schedule_enabled | FALSE`
- Restart: `sudo systemctl restart repricer-scheduler`

**3. Змінити timezone:**
- В Google Sheets Config: `schedule_timezone | Europe/Kyiv`
- Restart: `sudo systemctl restart repricer-scheduler`

---

## 📊 МОНІТОРИНГ:

### Логи:

```bash
# Real-time systemd logs
sudo journalctl -u repricer-scheduler -f

# Останні 50 рядків
sudo journalctl -u repricer-scheduler -n 50

# Сьогоднішні логи
sudo journalctl -u repricer-scheduler --since today

# Тільки помилки
sudo journalctl -u repricer-scheduler -p err

# Файлові логи
tail -f logs/scheduler_*.log
tail -f logs/repricer_*.log
```

### Статус:

```bash
# Service status
sudo systemctl status repricer-scheduler

# Має бути:
# Active: active (running)
# Loaded: loaded (...; enabled)
```

---

## 📈 СТАТИСТИКА:

Scheduler збирає статистику:

```python
{
    'total_runs': 156,
    'successful_runs': 154,  # 98.7%
    'failed_runs': 2,
    'last_run': '2025-12-26T21:00:00-05:00',
    'last_success': '2025-12-26T21:00:00-05:00',
    'last_error': {
        'time': '2025-12-25T16:00:00-05:00',
        'error': 'Connection timeout'
    }
}
```

**Переглянути:** `logs/scheduler_*.log`

---

## 🐛 TROUBLESHOOTING:

### Service не запускається:

```bash
# 1. Перевірити логи
sudo journalctl -u repricer-scheduler -n 50 --no-pager

# 2. Тест manually
cd ~/furniture-repricer
source venv/bin/activate
python run_scheduler.py

# 3. Перевірити шляхи
cat /etc/systemd/system/repricer-scheduler.service | grep ExecStart
ls -la $(cat /etc/systemd/system/repricer-scheduler.service | grep ExecStart | cut -d' ' -f1 | cut -d'=' -f2)
```

### Scheduled runs fail:

```bash
# 1. Перевірити що репрайсер працює
python run_repricer.py

# 2. Перевірити config
python -c "from app.modules.config_manager import ConfigManager; print('OK')"

# 3. Перевірити логи
tail -f logs/scheduler_*.log
tail -f logs/repricer_*.log
```

### Wrong timezone:

```bash
# 1. Перевірити system timezone
timedatectl

# 2. Тест timezone
python -c "
from app.modules.scheduler import RepricerScheduler
s = RepricerScheduler(['12:00'], 'America/New_York')
print(s._get_current_time())
"

# 3. Змінити в Config sheet
# schedule_timezone | America/New_York
```

---

## ✅ INTEGRATION CHECKLIST:

### Підготовка (5 хв):
- [ ] VPS доступний по SSH
- [ ] Проект в `/home/ubuntu/furniture-repricer`
- [ ] venv активний
- [ ] Install: `pip install schedule pytz`

### Файли (5 хв):
- [ ] Copy `scheduler.py` → `app/modules/scheduler.py`
- [ ] Copy `run_scheduler.py` → `./run_scheduler.py`
- [ ] Edit `repricer-scheduler.service` (replace username)

### Config (2 хв):
- [ ] Add scheduler params to Google Sheets Config
- [ ] `schedule_enabled = TRUE`
- [ ] `schedule_times = 06:00,16:00,21:00`
- [ ] `schedule_timezone = America/New_York`

### Testing (3 хв):
- [ ] Test: `python run_scheduler.py` (Ctrl+C після)
- [ ] Verify: "Next run: ..." показується

### Systemd (5 хв):
- [ ] `sudo cp repricer-scheduler.service /etc/systemd/system/`
- [ ] `sudo systemctl daemon-reload`
- [ ] `sudo systemctl enable repricer-scheduler`
- [ ] `sudo systemctl start repricer-scheduler`
- [ ] `sudo systemctl status repricer-scheduler` → `active (running)`

### Verification (10 хв):
- [ ] Логи показують scheduler running
- [ ] Next runs відображаються
- [ ] Дочекатись scheduled run
- [ ] Google Sheets оновились
- [ ] Логи чисті (без critical errors)

**Загальний час:** ~30 хвилин

---

## 🌟 BEST PRACTICES:

### 1. Log Rotation:

```bash
sudo nano /etc/logrotate.d/repricer-scheduler

# Add:
/home/ubuntu/furniture-repricer/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
}
```

### 2. Monitoring:

```bash
# Monitor script
nano ~/monitor_scheduler.sh

# Add:
#!/bin/bash
STATUS=$(systemctl is-active repricer-scheduler)
if [ "$STATUS" != "active" ]; then
    systemctl restart repricer-scheduler
fi

# Cron (every 15 min)
crontab -e
# Add: */15 * * * * /home/ubuntu/monitor_scheduler.sh
```

### 3. Backup Config:

```bash
# Daily backup
crontab -e
# Add: 0 2 * * * cp ~/furniture-repricer/config.yaml ~/backups/config_$(date +\%Y\%m\%d).yaml
```

---

## 📞 ПІДТРИМКА:

### Документація:
- **VPS_SCHEDULER_SETUP.md** - Повна інструкція setup (must-read!)
- **CONFIG_SHEET_SCHEDULER.md** - Scheduler параметри для Google Sheets

### Файли:
- `scheduler.py` - Scheduler module
- `run_scheduler.py` - Daemon script
- `repricer-scheduler.service` - Systemd service

### Корисні команди:

```bash
# Діагностика
sudo systemctl status repricer-scheduler
sudo journalctl -u repricer-scheduler -n 50

# Управління
sudo systemctl restart repricer-scheduler
sudo systemctl stop repricer-scheduler

# Логи
tail -f logs/scheduler_*.log
tail -f logs/repricer_*.log
```

---

## 🎉 SUCCESS CRITERIA:

Scheduler працює правильно якщо:

- ✅ `systemctl status repricer-scheduler` → `active (running)`
- ✅ Логи показують "SCHEDULER STARTED"
- ✅ Логи показують "Next run: ..." з правильним часом
- ✅ Scheduled run виконався успішно
- ✅ Google Sheets оновились після run
- ✅ Stats показують `successful_runs > 0`
- ✅ Service автоматично restart при помилках
- ✅ Service запускається після reboot VPS

---

## 🚀 ГОТОВО!

**Система тепер повністю автономна:**

### Що працює автоматично:

- ⏰ **Запуски тричі на день:** 06:00, 16:00, 21:00 EST
- 🔄 **Автоматичний restart** при помилках
- 🚀 **Автозапуск після reboot** VPS
- 📊 **Оновлення Google Sheets** після кожного run
- 🐛 **Детальне логування** всіх операцій
- 📈 **Статистика** успішності

### Клієнт контролює:

- 🎛️ **Enable/disable** через Google Sheets
- ⏰ **Зміна schedule** on the fly
- 🌍 **Timezone** management
- 📊 **Всі параметри** БЕЗ змін коду

### Результат:

- ✅ **0 ручної роботи** - все автоматично
- ✅ **Завжди актуальні ціни** - 3x daily updates
- ✅ **Конкурентоспроможність 24/7**
- ✅ **Повний контроль** через Google Sheets

---

**Час setup:** 30 хвилин  
**Складність:** Низька (покрокові інструкції)  
**Результат:** Повна автоматизація!

**Насолоджуйтесь автономною системою!** 🎊🚀
