"""
Telegram Bot module for Furniture Repricer notifications.

Sends messages via Telegram Bot API using direct HTTP requests
(no heavy async dependencies — only `requests` which is already installed).

Usage in main.py:
    from .modules.telegram_bot import TelegramBot

    bot = TelegramBot.from_config(config)
    bot.send_message("Hello!")
"""

import time
from datetime import datetime
from typing import Optional

import requests

from .logger import get_logger

logger = get_logger("telegram_bot")

# Telegram Bot API base URL
_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# Maximum length of a single Telegram message (API limit: 4096)
_MAX_MESSAGE_LENGTH = 4000


class TelegramBot:
    """
    Synchronous Telegram notifications client.

    Sends messages to a single chat via the Telegram Bot API.
    All methods are safe to call even when the bot is disabled —
    they simply return False without raising exceptions.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        errors_only: bool = False,
        enabled: bool = True,
        timeout: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Args:
            token: Telegram bot token (from @BotFather).
            chat_id: Target chat / channel ID (numeric string).
            errors_only: If True — only error notifications are sent.
            enabled: Master switch; when False all methods are no-ops.
            timeout: HTTP request timeout in seconds.
            retry_attempts: How many times to retry on network errors.
            retry_delay: Seconds between retries.
        """
        self.token = token.strip()
        self.chat_id = str(chat_id).strip()
        self.errors_only = errors_only
        self.enabled = enabled
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        if self.enabled:
            logger.info(
                f"TelegramBot initialized | "
                f"chat_id={self.chat_id} | "
                f"errors_only={self.errors_only}"
            )
        else:
            logger.info("TelegramBot disabled (enabled=False)")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict) -> "TelegramBot":
        """
        Create a TelegramBot from the merged runtime config dict.

        Expected keys (all optional — safe defaults are used):
            telegram_enabled       bool   (default: False)
            telegram_bot_token     str    (default: "")
            telegram_chat_id       str    (default: "")
            telegram_on_errors_only bool  (default: False)

        Returns:
            A configured TelegramBot instance.
            If telegram_enabled is False or credentials are missing,
            the instance will be disabled (all methods are no-ops).
        """
        enabled = config.get("telegram_enabled", False)
        token = config.get("telegram_bot_token", "").strip()
        chat_id = str(config.get("telegram_chat_id", "")).strip()
        errors_only = config.get("telegram_on_errors_only", False)

        if not token or not chat_id:
            if enabled:
                logger.warning(
                    "telegram_enabled=True but token/chat_id are empty. "
                    "Bot will be disabled. Fill in config.yaml or Google Sheets."
                )
            return cls(
                token=token or "disabled",
                chat_id=chat_id or "0",
                errors_only=errors_only,
                enabled=False,
            )

        return cls(
            token=token,
            chat_id=chat_id,
            errors_only=errors_only,
            enabled=enabled,
        )

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def send_message(self, text: str, force: bool = False) -> bool:
        """
        Send a plain-text message.

        Args:
            text: Message text (Markdown supported).
            force: If True — send even when errors_only=True.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if not self.enabled:
            return False

        if self.errors_only and not force:
            logger.debug("errors_only=True — skipping non-error notification")
            return False

        return self._send_api_request(text)

    def send_error(self, title: str, details: str = "") -> bool:
        """
        Send an error notification (always sent, regardless of errors_only).

        Args:
            title: Short error title.
            details: Optional detailed description.

        Returns:
            True if sent successfully.
        """
        lines = [f"🔴 *{title}*"]
        if details:
            lines.append(details)
        lines.append(f"🕐 {_now()}")
        return self._send_api_request("\n\n".join(lines), force=True)

    # ------------------------------------------------------------------
    # High-level lifecycle notifications
    # ------------------------------------------------------------------

    def send_run_start(self, products_count: int = 0) -> bool:
        """Notify that a repricer run has started."""
        text = (
            f"🚀 *Repricer started*\n\n"
            f"📦 Products loaded: {products_count}\n"
            f"🕐 {_now()}"
        )
        return self.send_message(text)

    def send_run_complete(self, stats: dict) -> bool:
        """
        Notify that a repricer run finished successfully.

        Args:
            stats: Dict with keys: duration_min, total_products,
                   updated_products, emma_mason, competitors (list of names).
        """
        duration = stats.get("duration_min", 0)
        total = stats.get("total_products", 0)
        updated = stats.get("updated_products", 0)
        emma = stats.get("emma_mason", 0)

        competitors_lines = []
        for name, count in stats.get("competitors", {}).items():
            competitors_lines.append(f"  • {name}: {count}")
        competitors_block = "\n".join(competitors_lines) if competitors_lines else "  —"

        text = (
            f"✅ *Repricer completed*\n\n"
            f"⏱ Duration: {duration:.1f} min\n"
            f"📦 Products: {total} total | {updated} updated\n"
            f"🛒 Emma Mason: {emma}\n"
            f"🔍 Competitors:\n{competitors_block}\n"
            f"🕐 {_now()}"
        )
        return self.send_message(text)

    def send_run_failed(self, error: Exception) -> bool:
        """Notify that a repricer run crashed."""
        return self.send_error(
            title="Repricer FAILED",
            details=f"`{type(error).__name__}: {str(error)[:300]}`",
        )

    def send_scraper_warning(self, scraper_name: str, message: str) -> bool:
        """Send a non-critical scraper warning (e.g. fallback used)."""
        text = (
            f"⚠️ *{scraper_name}*\n\n"
            f"{message}\n"
            f"🕐 {_now()}"
        )
        return self.send_message(text)

    def send_algolia_key_refreshed(self, success: bool) -> bool:
        """Notify about Algolia API key auto-refresh result."""
        if success:
            text = (
                f"🔑 *Algolia key refreshed*\n\n"
                f"Auto-refresh via Playwright succeeded.\n"
                f"🕐 {_now()}"
            )
        else:
            text = (
                f"🔑 *Algolia key refresh FAILED*\n\n"
                f"Fell back to HTML scraper.\n"
                f"🕐 {_now()}"
            )
            return self._send_api_request(text, force=True)
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _send_api_request(self, text: str, force: bool = False) -> bool:
        """
        Make the actual HTTP POST to Telegram Bot API.

        Retries up to self.retry_attempts times on network errors.
        Long messages are automatically truncated to _MAX_MESSAGE_LENGTH.

        Args:
            text: Message text.
            force: Internal flag — bypasses errors_only check.

        Returns:
            True if the API accepted the message.
        """
        if not self.enabled:
            return False

        # Truncate if needed
        if len(text) > _MAX_MESSAGE_LENGTH:
            text = text[:_MAX_MESSAGE_LENGTH] + "\n...[truncated]"

        url = _API_BASE.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)

                if response.status_code == 200:
                    logger.debug(f"Telegram message sent (attempt {attempt})")
                    return True

                # 400 = bad request (wrong chat_id, parse error, etc.) — don't retry
                if response.status_code == 400:
                    logger.error(
                        f"Telegram API 400 Bad Request: {response.text[:200]}"
                    )
                    return False

                # 429 = rate limit — wait and retry
                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get(
                        "retry_after", self.retry_delay
                    )
                    logger.warning(
                        f"Telegram rate limit. Retrying after {retry_after}s..."
                    )
                    time.sleep(retry_after)
                    continue

                logger.warning(
                    f"Telegram API HTTP {response.status_code} "
                    f"(attempt {attempt}/{self.retry_attempts}): {response.text[:100]}"
                )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Telegram request timed out "
                    f"(attempt {attempt}/{self.retry_attempts})"
                )

            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    f"Telegram connection error "
                    f"(attempt {attempt}/{self.retry_attempts}): {exc}"
                )

            except Exception as exc:
                logger.error(f"Unexpected error sending Telegram message: {exc}")
                return False

            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay)

        logger.error(
            f"Failed to send Telegram message after {self.retry_attempts} attempts"
        )
        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Send a test message to verify the bot is configured correctly.

        Returns:
            True if the test message was delivered.
        """
        logger.info("Testing Telegram connection...")
        result = self._send_api_request(
            f"🤖 *Furniture Repricer*\nTelegram notifications connected.\n🕐 {_now()}",
            force=True,
        )
        if result:
            logger.info("[OK] Telegram test message sent")
        else:
            logger.error("[X] Telegram test failed — check token and chat_id")
        return result

    def __repr__(self) -> str:
        return (
            f"TelegramBot("
            f"enabled={self.enabled}, "
            f"chat_id={self.chat_id}, "
            f"errors_only={self.errors_only})"
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _now() -> str:
    """Return current datetime as a readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
