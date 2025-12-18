#!/bin/bash
# Furniture Repricer - Setup Script
# Автоматична установка на Ubuntu/Debian

set -e

echo "=================================="
echo "Furniture Repricer Setup"
echo "=================================="
echo

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функція для виводу повідомлень
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Перевірка що запущено від root або з sudo
if [ "$EUID" -ne 0 ]; then 
    warn "Please run with sudo for system packages installation"
    echo "sudo ./setup.sh"
    exit 1
fi

# 1. Оновити систему
info "Updating system packages..."
apt-get update -qq

# 2. Встановити Python 3.10+
info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 not found. Installing..."
    apt-get install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
info "Python version: $PYTHON_VERSION"

# 3. Встановити системні залежності
info "Installing system dependencies..."
apt-get install -y \
    git \
    curl \
    wget \
    nginx \
    cron \
    supervisor \
    libssl-dev \
    libffi-dev \
    build-essential

# 4. Створити віртуальне середовище
info "Creating virtual environment..."
cd "$(dirname "$0")"
python3 -m venv venv

# 5. Активувати venv та встановити залежності
info "Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Створити необхідні директорії
info "Creating directories..."
mkdir -p logs
mkdir -p data/cache
mkdir -p credentials

# 7. Копіювати .env.example в .env якщо не існує
if [ ! -f .env ]; then
    info "Creating .env file from template..."
    cp .env.example .env
    warn "Please edit .env file with your credentials!"
    echo "  nano .env"
else
    info ".env file already exists"
fi

# 8. Встановити права доступу
info "Setting permissions..."
chmod 755 run_repricer.sh
chmod 600 .env 2>/dev/null || true
chmod 700 credentials 2>/dev/null || true

# 9. Створити systemd service для Telegram бота
info "Creating systemd service for Telegram bot..."
cat > /etc/systemd/system/repricer-telegram.service << EOF
[Unit]
Description=Furniture Repricer Telegram Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python app/telegram_commands.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable repricer-telegram.service

# 10. Налаштувати cron
info "Setting up cron jobs..."
CRON_FILE="/tmp/repricer_cron"
cat > $CRON_FILE << EOF
# Furniture Repricer - Automatic runs (EST timezone)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# 06:00 EST (11:00 UTC - assuming EST is UTC-5)
0 11 * * * cd $(pwd) && ./run_repricer.sh >> logs/cron.log 2>&1

# 16:00 EST (21:00 UTC)
0 21 * * * cd $(pwd) && ./run_repricer.sh >> logs/cron.log 2>&1

# 21:00 EST (02:00 UTC next day)
0 2 * * * cd $(pwd) && ./run_repricer.sh >> logs/cron.log 2>&1
EOF

crontab -u $(whoami) $CRON_FILE
rm $CRON_FILE

info "Cron jobs installed. View with: crontab -l"

# 11. Перевірка конфігурації
info "Checking configuration..."

if [ ! -f credentials/service_account.json ]; then
    warn "Google Service Account credentials not found!"
    echo "  Please add: credentials/service_account.json"
fi

if ! grep -q "TELEGRAM_BOT_TOKEN=123" .env; then
    warn "Telegram bot token not configured in .env"
fi

# 12. Тестовий запуск
echo
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo
info "Next steps:"
echo "  1. Edit .env file: nano .env"
echo "  2. Add Google credentials: credentials/service_account.json"
echo "  3. Test connection: ./run_repricer.sh --test"
echo "  4. Start Telegram bot: sudo systemctl start repricer-telegram"
echo "  5. Open Telegram and send /start to your bot"
echo
info "Useful commands:"
echo "  • View logs: tail -f logs/repricer_*.log"
echo "  • Manual run: ./run_repricer.sh (or /run in Telegram)"
echo "  • Stop bot: sudo systemctl stop repricer-telegram"
echo "  • Check bot status: sudo systemctl status repricer-telegram"
echo
echo "Telegram setup instructions: docs/TELEGRAM_SETUP.md"
echo "Google Sheets setup: docs/GOOGLE_SERVICE_ACCOUNT.md"
echo
