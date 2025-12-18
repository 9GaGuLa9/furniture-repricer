@echo off
chcp 65001 >nul
cls

echo.
echo ═══════════════════════════════════════════════════════════
echo   FURNITURE REPRICER - ПОВНА УСТАНОВКА
echo ═══════════════════════════════════════════════════════════
echo.
echo Цей скрипт встановить ВСЕ що потрібно і запустить тести.
echo.
echo Зачекайте 1-2 хвилини...
echo.

echo ─────────────────────────────────────────────────────────
echo [1/4] Перевірка Python...
echo ─────────────────────────────────────────────────────────
python --version
if errorlevel 1 (
    echo.
    echo ❌ ПОМИЛКА: Python не знайдено!
    echo.
    echo Встановіть Python з https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo ✅ Python знайдено
echo.

echo ─────────────────────────────────────────────────────────
echo [2/4] Встановлення Python бібліотек...
echo ─────────────────────────────────────────────────────────
echo.
echo Встановлюємо: PyYAML, python-dotenv, beautifulsoup4, requests, lxml
echo.

python -m pip install --quiet PyYAML python-dotenv beautifulsoup4 requests lxml

if errorlevel 1 (
    echo.
    echo ⚠️  Спроба з pip...
    pip install --quiet PyYAML python-dotenv beautifulsoup4 requests lxml
)

echo.
echo ✅ Бібліотеки встановлено
echo.

echo ─────────────────────────────────────────────────────────
echo [3/4] Перевірка структури проекту...
echo ─────────────────────────────────────────────────────────
echo.

python check_structure.py

if errorlevel 1 (
    echo.
    echo ❌ Перевірка не пройшла!
    echo.
    echo Дивіться помилки вище.
    echo.
    pause
    exit /b 1
)

echo.
echo ─────────────────────────────────────────────────────────
echo [4/4] Запуск тесту scraper...
echo ─────────────────────────────────────────────────────────
echo.

python test_scraper.py

echo.
echo ═══════════════════════════════════════════════════════════
echo   ✅ УСТАНОВКА ЗАВЕРШЕНА!
echo ═══════════════════════════════════════════════════════════
echo.
echo Тепер можете:
echo   - Налаштувати config.yaml
echo   - Створити .env файл
echo   - Запустити репрайсер: python run_repricer.py --test
echo.
echo Документація: README.md
echo.
pause
