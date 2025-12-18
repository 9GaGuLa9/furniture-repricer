@echo off
echo ========================================
echo   Furniture Repricer - Installation
echo ========================================
echo.

echo [1/3] Installing minimal dependencies...
pip install PyYAML python-dotenv beautifulsoup4 requests lxml
echo.

echo [2/3] Checking structure...
python check_structure.py
echo.

echo [3/3] Testing scraper...
python test_scraper.py
echo.

echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit config.yaml - add your spreadsheet ID
echo 2. Copy .env.example to .env
echo 3. Read README.md for details
echo.
pause
