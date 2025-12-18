@echo off
chcp 65001 >nul
echo.
echo ════════════════════════════════════════════════════════════
echo   ПЕРЕВІРКА УСТАНОВКИ
echo ════════════════════════════════════════════════════════════
echo.

echo Scrapers:
if exist "%PROJECT_DIR%\app\scrapers\emmamason.py" (
    echo   ✓ emmamason.py
) else (
    echo   ❌ emmamason.py ВІДСУТНІЙ!
)

if exist "%PROJECT_DIR%\app\scrapers\onestopbedrooms.py" (
    echo   ✓ onestopbedrooms.py
) else (
    echo   ❌ onestopbedrooms.py ВІДСУТНІЙ!
)

if exist "%PROJECT_DIR%\app\scrapers\coleman.py" (
    echo   ✓ coleman.py
) else (
    echo   ❌ coleman.py ВІДСУТНІЙ!
)

if exist "%PROJECT_DIR%\app\scrapers\afa.py" (
    echo   ✓ afa.py
) else (
    echo   ❌ afa.py ВІДСУТНІЙ!
)

if exist "%PROJECT_DIR%\app\scrapers\__init__.py" (
    echo   ✓ __init__.py
) else (
    echo   ❌ __init__.py ВІДСУТНІЙ!
)

echo.
echo Main:
if exist "%PROJECT_DIR%\app\main.py" (
    echo   ✓ main.py (ОНОВЛЕНО)
) else (
    echo   ❌ main.py ВІДСУТНІЙ!
)

echo.
echo ════════════════════════════════════════════════════════════
echo   ВСТАНОВЛЕННЯ ЗАЛЕЖНОСТІ
echo ════════════════════════════════════════════════════════════
echo.

echo Встановлення cloudscraper для AFA scraper...
pip install cloudscraper --quiet

if errorlevel 1 (
    echo ⚠️  Помилка установки cloudscraper
    echo    Спробуйте вручну: pip install cloudscraper
) else (
    echo ✓ cloudscraper встановлено
)

echo.
echo ════════════════════════════════════════════════════════════
echo   ✅ УСТАНОВКА ЗАВЕРШЕНА!
echo ════════════════════════════════════════════════════════════
echo.
echo Тепер можна запускати:
echo.
echo   Тестовий режим (10 товарів):
echo   python run_repricer.py --test
echo.
echo   Повний режим:
echo   python run_repricer.py
echo.
echo ════════════════════════════════════════════════════════════
echo.

cd "%PROJECT_DIR%"
pause
