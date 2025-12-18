"""
Telegram Bot для сповіщень Furniture Repricer
Надсилає повідомлення про статус, помилки та зміни цін
"""

import asyncio
from telegram import Bot
from telegram.error import TelegramError
from typing import Optional, Dict, List
from datetime import datetime

from .logger import get_logger

logger = get_logger("telegram")


class TelegramNotifier:
    """Клас для надсилання Telegram сповіщень"""
    
    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        """
        Ініціалізація Telegram бота
        
        Args:
            bot_token: Токен бота від @BotFather
            chat_id: ID чату куди надсилати повідомлення
            enabled: Чи увімкнені сповіщення
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.bot = None
        
        if self.enabled and self.bot_token and self.chat_id:
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram notifier initialized")
        else:
            logger.warning("Telegram notifier disabled or not configured")
    
    async def _send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """
        Надіслати повідомлення (async)
        
        Args:
            text: Текст повідомлення
            parse_mode: Формат (Markdown або HTML)
        
        Returns:
            True якщо успішно
        """
        if not self.enabled or not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            logger.debug("Telegram message sent successfully")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """
        Надіслати повідомлення (sync wrapper)
        
        Args:
            text: Текст повідомлення
            parse_mode: Формат (Markdown або HTML)
        
        Returns:
            True якщо успішно
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._send_message(text, parse_mode))
    
    def send_start_notification(self, test_mode: bool = False) -> bool:
        """
        Надіслати повідомлення про початок роботи
        
        Args:
            test_mode: Чи тестовий режим
        
        Returns:
            True якщо успішно
        """
        mode = "🧪 TEST MODE" if test_mode else "🚀 PRODUCTION"
        
        text = f"""
*Furniture Repricer Started* {mode}

⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')}`
📊 Status: Collecting prices...

_This may take 30-60 minutes_
        """.strip()
        
        return self.send_message(text)
    
    def send_completion_notification(self, stats: Dict) -> bool:
        """
        Надіслати повідомлення про завершення
        
        Args:
            stats: Статистика {
                'total_products': 8821,
                'updated': 234,
                'errors': 12,
                'duration_minutes': 45,
                'competitors': {...}
            }
        
        Returns:
            True якщо успішно
        """
        duration = stats.get('duration_minutes', 0)
        total = stats.get('total_products', 0)
        updated = stats.get('updated', 0)
        errors = stats.get('errors', 0)
        
        # Emoji статусу
        if errors == 0:
            status_emoji = "✅"
        elif errors < 10:
            status_emoji = "⚠️"
        else:
            status_emoji = "❌"
        
        text = f"""
*Furniture Repricer Completed* {status_emoji}

⏱ Duration: `{duration:.1f} minutes`
📦 Total products: `{total}`
✏️ Updated: `{updated}`
❌ Errors: `{errors}`

*Competitors:*
"""
        
        # Додати статистику по конкурентам
        competitors = stats.get('competitors', {})
        for name, comp_stats in competitors.items():
            status = "✅" if comp_stats.get('success', False) else "❌"
            text += f"{status} {name}: `{comp_stats.get('products', 0)}` products\n"
        
        text += f"\n_Next run scheduled in 5-10 hours_"
        
        return self.send_message(text)
    
    def send_error_notification(self, error: str, context: str = "") -> bool:
        """
        Надіслати повідомлення про помилку
        
        Args:
            error: Текст помилки
            context: Контекст (де сталась помилка)
        
        Returns:
            True якщо успішно
        """
        text = f"""
*⚠️ Repricer Error*

❌ Error: `{error}`
📍 Context: `{context}`
⏰ Time: `{datetime.now().strftime('%H:%M:%S')}`

_Check logs for details_
        """.strip()
        
        return self.send_message(text)
    
    def send_price_changes_summary(self, changes: List[Dict]) -> bool:
        """
        Надіслати підсумок змін цін
        
        Args:
            changes: Список змін [{
                'sku': 'ABC123',
                'old_price': 100.0,
                'new_price': 94.0,
                'change_percent': -6.0
            }]
        
        Returns:
            True якщо успішно
        """
        if not changes:
            return False
        
        # Топ-10 найбільших змін
        top_changes = sorted(
            changes,
            key=lambda x: abs(x.get('change_percent', 0)),
            reverse=True
        )[:10]
        
        text = f"*📊 Price Changes Summary*\n\n"
        text += f"Total changes: `{len(changes)}`\n"
        text += f"Top 10 biggest changes:\n\n"
        
        for i, change in enumerate(top_changes, 1):
            sku = change.get('sku', 'N/A')
            old = change.get('old_price', 0)
            new = change.get('new_price', 0)
            percent = change.get('change_percent', 0)
            
            # Emoji для зростання/падіння
            emoji = "📈" if percent > 0 else "📉"
            
            text += f"{i}. `{sku}`: ${old:.2f} → ${new:.2f} {emoji} `{percent:+.1f}%`\n"
        
        return self.send_message(text)
    
    def send_custom_message(self, title: str, message: str, emoji: str = "ℹ️") -> bool:
        """
        Надіслати кастомне повідомлення
        
        Args:
            title: Заголовок
            message: Текст
            emoji: Емодзі
        
        Returns:
            True якщо успішно
        """
        text = f"*{emoji} {title}*\n\n{message}"
        return self.send_message(text)
    
    def send_test_message(self) -> bool:
        """
        Надіслати тестове повідомлення
        
        Returns:
            True якщо успішно
        """
        text = """
*🧪 Telegram Test Message*

✅ Connection successful!
📱 Bot: Online
💬 Chat: Connected

_This is a test message from Furniture Repricer_
        """.strip()
        
        return self.send_message(text)
    
    def send_daily_summary(self, stats: Dict) -> bool:
        """
        Надіслати щоденний підсумок
        
        Args:
            stats: Статистика за день
        
        Returns:
            True якщо успішно
        """
        text = f"""
*📊 Daily Summary - {datetime.now().strftime('%Y-%m-%d')}*

🔄 Runs completed: `{stats.get('runs', 0)}`
📦 Products processed: `{stats.get('total_products', 0)}`
✏️ Total updates: `{stats.get('total_updates', 0)}`
❌ Total errors: `{stats.get('total_errors', 0)}`

*Average prices:*
💰 Our: `${stats.get('avg_our_price', 0):.2f}`
🏆 Competitors: `${stats.get('avg_competitor_price', 0):.2f}`
📊 Suggested: `${stats.get('avg_suggested_price', 0):.2f}`

*Top competitors:*
"""
        
        for comp, count in stats.get('competitor_matches', {}).items():
            text += f"• {comp}: `{count}` matches\n"
        
        return self.send_message(text)


class TelegramNotifierManager:
    """Менеджер для групових сповіщень"""
    
    def __init__(self, notifier: TelegramNotifier, config: dict):
        """
        Ініціалізація менеджера
        
        Args:
            notifier: TelegramNotifier instance
            config: Конфігурація notifications
        """
        self.notifier = notifier
        self.config = config
    
    def should_send(self, notification_type: str) -> bool:
        """
        Перевірити чи треба надсилати певний тип сповіщення
        
        Args:
            notification_type: Тип ('on_start', 'on_complete', 'on_error', etc.)
        
        Returns:
            True якщо треба надсилати
        """
        return self.config.get('notifications', {}).get(notification_type, False)
    
    def notify_start(self, test_mode: bool = False):
        """Сповістити про старт"""
        if self.should_send('on_start'):
            self.notifier.send_start_notification(test_mode)
    
    def notify_complete(self, stats: Dict):
        """Сповістити про завершення"""
        if self.should_send('on_complete'):
            self.notifier.send_completion_notification(stats)
    
    def notify_error(self, error: str, context: str = ""):
        """Сповістити про помилку"""
        if self.should_send('on_error'):
            self.notifier.send_error_notification(error, context)
    
    def notify_price_changes(self, changes: List[Dict]):
        """Сповістити про зміни цін"""
        if self.should_send('on_price_changes') and changes:
            self.notifier.send_price_changes_summary(changes)
    
    def notify_summary(self, stats: Dict):
        """Надіслати підсумок"""
        if self.should_send('summary'):
            self.notifier.send_completion_notification(stats)


if __name__ == "__main__":
    # Тестування (потрібні токен та chat_id)
    import os
    
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    
    if token and chat_id:
        notifier = TelegramNotifier(token, chat_id)
        
        # Тест
        print("Sending test message...")
        success = notifier.send_test_message()
        print(f"Success: {success}")
    else:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to test")
