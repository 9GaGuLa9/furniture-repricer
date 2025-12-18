#!/bin/bash
# Furniture Repricer - Run Script
# Запуск головного репрайсера

set -e

# Перейти до директорії скрипта
cd "$(dirname "$0")"

# Кольори
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Перевірити наявність venv
if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found!${NC}"
    echo "Run: ./setup.sh"
    exit 1
fi

# Активувати venv
source venv/bin/activate

# Перевірити наявність credentials
if [ ! -f "credentials/service_account.json" ]; then
    echo -e "${RED}Google credentials not found!${NC}"
    echo "Add file: credentials/service_account.json"
    exit 1
fi

# Перевірити .env
if [ ! -f ".env" ]; then
    echo -e "${RED}.env file not found!${NC}"
    echo "Copy: cp .env.example .env"
    exit 1
fi

# Перевірити параметри
TEST_MODE=false
if [ "$1" == "--test" ] || [ "$1" == "-t" ]; then
    TEST_MODE=true
    echo -e "${GREEN}Running in TEST MODE (limited products)${NC}"
fi

# Створити директорію для логів якщо не існує
mkdir -p logs

# Лог файл з датою
LOG_FILE="logs/repricer_$(date +%Y-%m-%d).log"

# Запустити репрайсер
echo "=================================="
echo "Starting Furniture Repricer"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Log: $LOG_FILE"
echo "=================================="

if [ "$TEST_MODE" = true ]; then
    python3 app/main.py --test 2>&1 | tee -a "$LOG_FILE"
else
    python3 app/main.py 2>&1 | tee -a "$LOG_FILE"
fi

# Перевірити результат
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Repricer completed successfully${NC}"
    exit 0
else
    echo -e "${RED}✗ Repricer failed${NC}"
    exit 1
fi
