"""
Telegram Bot Commands для Furniture Repricer
Управління репрайсером через Telegram
"""

import asyncio
import subprocess
import os
from datetime import datetime
from pathlib import Path
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import get_config
from app.modules.logger import get_logger

logger = get_logger("telegram_commands")
config = get_config()


class RepricerTelegramBot:
    """Telegram бот з командами управління"""
    
    def __init__(self, token: str, allowed_chat_ids: list):
        """
        Ініціалізація бота
        
        Args:
            token: Bot token
            allowed_chat_ids: Список дозволених chat IDs
        """
        self.token = token
        self.allowed_chat_ids = allowed_chat_ids
        self.app = Application.builder().token(token).build()
        self.base_dir = Path(__file__).parent.parent
        
        # Додати обробники команд
        self._register_handlers()
    
    def _register_handlers(self):
        """Зареєструвати обробники команд"""
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("run", self.cmd_run))
        self.app.add_handler(CommandHandler("last", self.cmd_last))
        self.app.add_handler(CommandHandler("logs", self.cmd_logs))
        self.app.add_handler(CommandHandler("schedule", self.cmd_schedule))
        self.app.add_handler(CommandHandler("config", self.cmd_config))
    
    def _is_authorized(self, update: Update) -> bool:
        """Перевірити чи користувач авторизований"""
        chat_id = update.effective_chat.id
        return chat_id in self.allowed_chat_ids
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return
        
        message = """
🛋️ *Furniture Repricer Bot*

Доступні команди:
/status - Поточний статус
/run - Запустити репрайсер
/last - Останні результати
/logs - Останні логи
/schedule - Розклад запусків
/config - Конфігурація
/help - Допомога

_Керуйте репрайсером прямо з Telegram!_
        """
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        if not self._is_authorized(update):
            return
        
        message = """
📖 *Довідка по командах:*

*Моніторинг:*
/status - Показує чи запущений репрайсер зараз
/last - Результати останнього запуску
/logs - Останні 20 рядків з логів

*Управління:*
/run - Запустити репрайсер вручну (займає ~45-60 хв)
/schedule - Переглянути розклад автоматичних запусків

*Налаштування:*
/config - Поточна конфігурація
Змінити параметри можна в Google Sheets (аркуш Config)

*Приклади:*
• `/run` - запустити зараз
• `/logs` - подивитись що відбувається
• `/status` - перевірити чи все працює
        """
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - поточний статус"""
        if not self._is_authorized(update):
            return
        
        # Перевірити чи запущений процес
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'app/main.py'],
                capture_output=True,
                text=True
            )
            
            is_running = bool(result.stdout.strip())
            
            if is_running:
                status_emoji = "🔄"
                status_text = "Running"
                status_msg = "_Репрайсер зараз працює. Це може зайняти 30-60 хвилин._"
            else:
                status_emoji = "✅"
                status_text = "Idle"
                status_msg = "_Репрайсер не запущений. Очікує наступного розкладу._"
            
            # Час наступного запуску (з cron)
            cron_result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True
            )
            
            # Знайти наступний час
            next_run = "Перевірте crontab"
            if cron_result.stdout:
                # Парсити cron для наступного часу
                lines = [l for l in cron_result.stdout.split('\n') if 'run_repricer' in l]
                if lines:
                    next_run = "Дивіться /schedule"
            
            # Останній лог
            log_file = self._get_latest_log()
            last_update = "N/A"
            if log_file and log_file.exists():
                last_update = datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            message = f"""
{status_emoji} *Status: {status_text}*

{status_msg}

📅 Останнє оновлення: `{last_update}`
⏰ Наступний запуск: {next_run}

_Використай /last для деталей останнього запуску_
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Status command error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
    
    async def cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /run - запустити репрайсер вручну"""
        if not self._is_authorized(update):
            return
        
        # Перевірити чи не запущений вже
        result = subprocess.run(
            ['pgrep', '-f', 'app/main.py'],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            await update.message.reply_text(
                "⚠️ Репрайсер вже запущений!\nПочекайте завершення або дивіться /status"
            )
            return
        
        # Запустити
        try:
            script_path = self.base_dir / "run_repricer.sh"
            
            # Запустити в фоні
            subprocess.Popen(
                [str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(self.base_dir)
            )
            
            message = """
🚀 *Репрайсер запущено!*

⏱ Очікуваний час: 30-60 хвилин
📊 Оброблюється ~8821 товарів

_Ви отримаєте сповіщення після завершення._
_Використайте /status для перевірки прогресу._
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            logger.info(f"Manual run triggered by Telegram user {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Run command error: {e}")
            await update.message.reply_text(f"❌ Помилка запуску: {e}")
    
    async def cmd_last(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /last - результати останнього запуску"""
        if not self._is_authorized(update):
            return
        
        try:
            log_file = self._get_latest_log()
            
            if not log_file or not log_file.exists():
                await update.message.reply_text("📭 Логи не знайдені")
                return
            
            # Прочитати останні рядки логу
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Шукати статистику (приблизно)
            stats = {
                'time': log_file.stem.replace('repricer_', ''),
                'products': 'N/A',
                'updated': 'N/A',
                'errors': 'N/A'
            }
            
            for line in lines[-100:]:  # Останні 100 рядків
                if 'Total products:' in line:
                    stats['products'] = line.split(':')[-1].strip()
                elif 'Updated:' in line:
                    stats['updated'] = line.split(':')[-1].strip()
                elif 'Errors:' in line:
                    stats['errors'] = line.split(':')[-1].strip()
            
            message = f"""
📊 *Останній запуск*

📅 Дата: `{stats['time']}`
📦 Товарів: `{stats['products']}`
✏️ Оновлено: `{stats['updated']}`
❌ Помилок: `{stats['errors']}`

_Дивіться /logs для детальних логів_
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Last command error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
    
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /logs - останні логи"""
        if not self._is_authorized(update):
            return
        
        try:
            log_file = self._get_latest_log()
            
            if not log_file or not log_file.exists():
                await update.message.reply_text("📭 Логи не знайдені")
                return
            
            # Прочитати останні 20 рядків
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            last_lines = lines[-20:]
            log_text = ''.join(last_lines)
            
            # Обрізати якщо дуже довго
            if len(log_text) > 3000:
                log_text = log_text[-3000:]
                log_text = "...\n" + log_text
            
            message = f"📝 *Останні логи:*\n\n```\n{log_text}\n```"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Logs command error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
    
    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /schedule - розклад запусків"""
        if not self._is_authorized(update):
            return
        
        try:
            # Прочитати crontab
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True
            )
            
            if not result.stdout:
                await update.message.reply_text("📭 Cron не налаштований")
                return
            
            # Знайти рядки з репрайсером
            cron_lines = [
                line for line in result.stdout.split('\n')
                if 'run_repricer' in line and not line.startswith('#')
            ]
            
            if not cron_lines:
                await update.message.reply_text("⚠️ Репрайсер не знайдено в cron")
                return
            
            message = "⏰ *Розклад автоматичних запусків:*\n\n"
            
            for i, line in enumerate(cron_lines, 1):
                # Парсити cron (приблизно)
                parts = line.split()
                if len(parts) >= 5:
                    minute = parts[0]
                    hour = parts[1]
                    
                    # Конвертувати UTC в EST (UTC-5)
                    hour_utc = int(hour)
                    hour_est = (hour_utc - 5) % 24
                    
                    message += f"✅ Запуск #{i}: `{hour_est:02d}:{minute} EST`\n"
            
            message += "\n_Змінити розклад можна через crontab або config.yaml_"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Schedule command error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
    
    async def cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /config - поточна конфігурація"""
        if not self._is_authorized(update):
            return
        
        try:
            message = f"""
⚙️ *Поточна конфігурація:*

*Scrapers:*
• Emma Mason: `{config.is_scraper_enabled('emmamason')}`
• 1StopBedrooms: `{config.is_scraper_enabled('onestopbedrooms')}`
• Coleman: `{config.is_scraper_enabled('coleman')}`
• AFA: `{config.is_scraper_enabled('afa')}`

*Settings:*
• Test mode: `{config.test_mode}`
• Telegram: `{config.telegram_enabled}`
• Log level: `{config.log_level}`

*Pricing:*
• Floor: `{config.get_pricing_coefficients()['floor']}`
• Below: `${config.get_pricing_coefficients()['below_lowest']}`
• Max: `{config.get_pricing_coefficients()['max']}`

_Змінити можна в config.yaml або Google Sheets_
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Config command error: {e}")
            await update.message.reply_text(f"❌ Помилка: {e}")
    
    def _get_latest_log(self) -> Path:
        """Знайти останній лог файл"""
        logs_dir = self.base_dir / "logs"
        if not logs_dir.exists():
            return None
        
        log_files = list(logs_dir.glob("repricer_*.log"))
        if not log_files:
            return None
        
        # Повернути найновіший
        return max(log_files, key=lambda p: p.stat().st_mtime)
    
    def run(self):
        """Запустити бота"""
        logger.info("Starting Telegram bot...")
        self.app.run_polling()


def main():
    """Main entry point для запуску бота окремо"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return
    
    # Дозволені chat IDs (можна додати більше)
    allowed_chats = [int(chat_id)]
    
    bot = RepricerTelegramBot(token, allowed_chats)
    bot.run()


if __name__ == "__main__":
    main()
