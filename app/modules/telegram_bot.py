"""
Telegram Bot module for Furniture Repricer notifications.

Sends messages via Telegram Bot API using direct HTTP requests
(no heavy async dependencies — only `requests` which is already installed).

Supports multiple recipients with individual notification levels:

    SILENT   (0) — no messages at all
    CRITICAL (1) — only critical failures (run crashed, fatal scraper error)
    ERRORS   (2) — CRITICAL + non-fatal errors, Algolia key refresh failed
    WARNINGS (3) — ERRORS + fallbacks activated, run completed with errors
    INFO     (4) — WARNINGS + run start / complete (normal flow)
    ALL      (5) — INFO + per-scraper granular status (developer only)

Config formats (config.yaml):

    # NEW — multi-recipient:
    telegram_enabled: true
    telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
    telegram_recipients:
      - name: "Developer"
        chat_id: "123456789"
        level: "ALL"
      - name: "Client"
        chat_id: "987654321"
        level: "INFO"

    # LEGACY — single recipient (fully supported, no migration needed):
    telegram_enabled: true
    telegram_bot_token: "${TELEGRAM_BOT_TOKEN}"
    telegram_chat_id: "123456789"
    telegram_on_errors_only: false   # false → INFO;  true → ERRORS

Usage:
    from .modules.telegram_bot import TelegramBot

    bot = TelegramBot.from_config(config)
    bot.send_run_start(products_count=8432)
    bot.send_error("Scraper failed", details="Timeout after 30 s")
"""

import time
from datetime import datetime
from enum import IntEnum

import requests

from .logger import get_logger

logger = get_logger("telegram_bot")

# Telegram Bot API base URL template
_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# Hard cap on a single Telegram message (API limit: 4096)
_MAX_MESSAGE_LENGTH = 4000


# ---------------------------------------------------------------------------
# Notification level
# ---------------------------------------------------------------------------

class NotifyLevel(IntEnum):
    """
    Notification levels in ascending verbosity order.

    A recipient receives a message when:
        message_level <= recipient_level
    """
    SILENT   = 0
    CRITICAL = 1
    ERRORS   = 2
    WARNINGS = 3
    INFO     = 4
    ALL      = 5

    @classmethod
    def from_str(
        cls,
        value: str,
        default: "NotifyLevel" = None,
    ) -> "NotifyLevel":
        """
        Parse a level from a string (case-insensitive).

        Args:
            value:   String representation, e.g. "ERRORS", "info", "3".
            default: Fallback level when value is invalid.

        Returns:
            NotifyLevel instance.
        """
        if default is None:
            default = cls.INFO
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                return default
        cleaned = str(value).strip().upper()
        if cleaned.isdigit():
            try:
                return cls(int(cleaned))
            except ValueError:
                pass
        try:
            return cls[cleaned]
        except KeyError:
            logger.warning(
                f"Unknown notification level '{value}', "
                f"using default '{default.name}'"
            )
            return default


# ---------------------------------------------------------------------------
# Internal single-recipient descriptor
# ---------------------------------------------------------------------------

class _Recipient:
    """Internal holder for one chat_id and its notification level."""

    __slots__ = ("name", "chat_id", "level")

    def __init__(self, name: str, chat_id: str, level: NotifyLevel):
        self.name = name
        self.chat_id = chat_id
        self.level = level

    def __repr__(self) -> str:
        return (
            f"_Recipient(name={self.name!r}, "
            f"chat_id={self.chat_id!r}, "
            f"level={self.level.name})"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TelegramBot:
    """
    Synchronous Telegram notifications client with multi-recipient support.

    Each public method documents which NotifyLevel it uses, so you can
    predict which recipients will receive the message.

    All public methods are safe to call when the bot is disabled —
    they return False immediately without raising exceptions.
    """

    def __init__(
        self,
        token: str,
        recipients: list = None,
        enabled: bool = True,
        timeout: int = 10,
        retry_attempts: int = 3,
        retry_delay: float = 2.0,
        # Legacy kwargs — accepted for backward compatibility
        chat_id: str = None,
        errors_only: bool = False,
    ):
        """
        Args:
            token:          Telegram bot token (from @BotFather).
            recipients:     List of _Recipient objects.
            enabled:        Master switch; when False all methods are no-ops.
            timeout:        HTTP request timeout in seconds.
            retry_attempts: How many times to retry on network errors.
            retry_delay:    Seconds between retries.
            chat_id:        Legacy parameter — used when recipients is None.
            errors_only:    Legacy parameter — maps to ERRORS level.
        """
        self.token = token.strip()
        self.enabled = enabled
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # Support legacy direct construction:
        #   TelegramBot(token="...", chat_id="...", enabled=False)
        if recipients is None:
            if chat_id and str(chat_id).strip() not in ("", "0"):
                level = NotifyLevel.ERRORS if errors_only else NotifyLevel.INFO
                self.recipients = [
                    _Recipient("default", str(chat_id).strip(), level)
                ]
            else:
                self.recipients = []
        else:
            self.recipients = list(recipients)

        if self.enabled and self.recipients:
            summary = ", ".join(
                f"{r.name}({r.level.name})" for r in self.recipients
            )
            logger.info(
                f"TelegramBot initialized | recipients=[{summary}]"
            )
        elif not self.enabled:
            logger.info("TelegramBot disabled (enabled=False)")
        else:
            logger.info("TelegramBot initialized (no recipients configured)")

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict) -> "TelegramBot":
        """
        Create a TelegramBot from the merged runtime config dict.

        Supports three formats (applied in order, higher overrides lower):

        1. YAML multi-recipient list (base):
            telegram_recipients:
              - name: "Developer"
                chat_id: "123456789"
                level: "ALL"
              - name: "Client"
                chat_id: "987654321"
                level: "INFO"

        2. Google Sheets flat-key overrides (override YAML per recipient by name):
            telegram_client_chat_id    →  overrides chat_id for recipient "Client"
            telegram_client_level      →  overrides level for recipient "Client"
            telegram_developer_level   →  overrides level for recipient "Developer"

            Key format: telegram_{name_lowercase}_{chat_id | level}
            These keys come from the Config sheet and take highest priority.

        3. Legacy single chat_id (used when no telegram_recipients in YAML):
            telegram_chat_id: "123456789"
            telegram_on_errors_only: false   # false → INFO;  true → ERRORS

        Returns:
            Configured TelegramBot instance (disabled if credentials missing).
        """
        enabled = config.get("telegram_enabled", False)
        token = config.get("telegram_bot_token", "").strip()

        recipients: list[_Recipient] = []

        # --- Step 1: Build base recipients from YAML multi-recipient list ---
        raw_recipients = config.get("telegram_recipients")
        if raw_recipients and isinstance(raw_recipients, list):
            for idx, entry in enumerate(raw_recipients):
                chat_id = str(entry.get("chat_id", "")).strip()
                name = str(
                    entry.get("name", f"recipient_{idx + 1}")
                ).strip()
                level = NotifyLevel.from_str(
                    entry.get("level", "INFO"),
                    default=NotifyLevel.INFO,
                )
                if chat_id:
                    recipients.append(_Recipient(name, chat_id, level))
                else:
                    logger.warning(
                        f"telegram_recipients[{idx}] missing chat_id — skipped"
                    )

        # --- Step 2: Legacy single chat_id fallback ---
        if not recipients:
            chat_id = str(config.get("telegram_chat_id", "")).strip()
            if chat_id:
                errors_only = config.get("telegram_on_errors_only", False)
                level = NotifyLevel.ERRORS if errors_only else NotifyLevel.INFO
                recipients.append(_Recipient("default", chat_id, level))

        # --- Step 3: Apply Google Sheets flat-key overrides ---
        # Format: telegram_{name_lowercase}_{chat_id | level}
        # Example: telegram_client_chat_id, telegram_client_level
        # These keys are written by the client in the Config sheet and have
        # the highest priority — they override the YAML values.
        if recipients:
            recipients = cls._apply_sheets_overrides(config, recipients)

        if not token or not recipients:
            if enabled:
                logger.warning(
                    "telegram_enabled=True but token or recipients are missing. "
                    "Bot will be disabled. Check config.yaml."
                )
            return cls(
                token=token or "disabled",
                recipients=[],
                enabled=False,
            )

        return cls(
            token=token,
            recipients=recipients,
            enabled=enabled,
        )

    @staticmethod
    def _apply_sheets_overrides(
        config: dict,
        recipients: list,
    ) -> list:
        """
        Apply Google Sheets flat-key overrides to the recipients list.

        Scans config for keys matching the pattern:
            telegram_{name_lowercase}_chat_id
            telegram_{name_lowercase}_level

        Only existing recipients (matched by name, case-insensitive) are
        updated — new recipients cannot be created via Google Sheets.

        Args:
            config:     Full merged config dict.
            recipients: List of _Recipient objects built from YAML.

        Returns:
            Updated list of _Recipient objects.
        """
        # Build a lookup: lowercase_name → recipient index
        name_index: dict[str, int] = {
            r.name.lower(): i for i, r in enumerate(recipients)
        }

        overrides_applied = []

        # Known override suffixes and their lengths
        _SUFFIXES = ("_chat_id", "_level")

        for key, value in config.items():
            # Only process telegram_ keys that aren't the base config keys
            if not key.startswith("telegram_"):
                continue
            # Skip known top-level keys
            if key in (
                "telegram_enabled",
                "telegram_bot_token",
                "telegram_chat_id",
                "telegram_on_errors_only",
                "telegram_recipients",
            ):
                continue

            # Parse: telegram_{name}_{field}
            # Match against known suffixes to avoid ambiguity with underscores
            # e.g. "telegram_client_chat_id" → name="client", field="chat_id"
            remainder = key[len("telegram_"):]   # e.g. "client_chat_id"
            field = None
            recipient_name_lower = None
            for suffix in _SUFFIXES:
                if remainder.endswith(suffix):
                    recipient_name_lower = remainder[: -len(suffix)]
                    field = suffix.lstrip("_")     # "chat_id" or "level"
                    break

            if not recipient_name_lower or not field:
                continue

            if recipient_name_lower not in name_index:
                logger.debug(
                    f"Google Sheets override '{key}' — "
                    f"no recipient named '{recipient_name_lower}' found, skipped"
                )
                continue

            idx = name_index[recipient_name_lower]
            recipient = recipients[idx]

            if field == "chat_id":
                new_chat_id = str(value).strip()
                if new_chat_id and new_chat_id != recipient.chat_id:
                    old = recipient.chat_id
                    recipients[idx] = _Recipient(
                        recipient.name, new_chat_id, recipient.level
                    )
                    overrides_applied.append(
                        f"  {recipient.name}.chat_id: {old} → {new_chat_id}"
                    )

            elif field == "level":
                new_level = NotifyLevel.from_str(
                    str(value), default=recipient.level
                )
                if new_level != recipient.level:
                    old = recipient.level.name
                    recipients[idx] = _Recipient(
                        recipient.name, recipient.chat_id, new_level
                    )
                    overrides_applied.append(
                        f"  {recipient.name}.level: {old} → {new_level.name}"
                    )

        if overrides_applied:
            logger.info(
                "Google Sheets Telegram overrides applied:\n"
                + "\n".join(overrides_applied)
            )

        return recipients

    # ------------------------------------------------------------------
    # Core public send
    # ------------------------------------------------------------------

    def send_message(
        self,
        text: str,
        level: NotifyLevel = NotifyLevel.INFO,
    ) -> bool:
        """
        Send a plain-text message to all recipients whose level >= `level`.

        Args:
            text:  Message text (Markdown supported).
            level: Minimum notification level required to receive this message.

        Returns:
            True if at least one recipient received the message.
        """
        return self._dispatch(level, text)

    def send_critical(self, title: str, details: str = "") -> bool:
        """
        Send a critical failure notification.  Level: CRITICAL.

        Reaches all recipients except those set to SILENT.

        Args:
            title:   Short title.
            details: Optional details.
        """
        lines = [f"🚨 *CRITICAL: {title}*"]
        if details:
            lines.append(details)
        lines.append(f"🕐 {_now()}")
        return self._dispatch(NotifyLevel.CRITICAL, "\n\n".join(lines))

    def send_error(self, title: str, details: str = "") -> bool:
        """
        Send an error notification.  Level: ERRORS.

        Args:
            title:   Short error title.
            details: Optional detailed description.
        """
        lines = [f"🔴 *{title}*"]
        if details:
            lines.append(details)
        lines.append(f"🕐 {_now()}")
        return self._dispatch(NotifyLevel.ERRORS, "\n\n".join(lines))

    def send_warning(self, title: str, details: str = "") -> bool:
        """
        Send a warning notification.  Level: WARNINGS.

        Args:
            title:   Short title.
            details: Optional details.
        """
        lines = [f"⚠️ *{title}*"]
        if details:
            lines.append(details)
        lines.append(f"🕐 {_now()}")
        return self._dispatch(NotifyLevel.WARNINGS, "\n\n".join(lines))

    # ------------------------------------------------------------------
    # High-level lifecycle notifications
    # ------------------------------------------------------------------

    def send_run_start(self, products_count: int = 0) -> bool:
        """
        Notify that a repricer run has started.  Level: INFO.

        Args:
            products_count: Total products to process (0 = unknown).
        """
        lines = ["🚀 *Repricer started*"]
        if products_count:
            lines.append(f"📦 Products loaded: {products_count}")
        lines.append(f"🕐 {_now()}")
        return self._dispatch(NotifyLevel.INFO, "\n\n".join(lines))

    def send_run_complete(self, stats: dict) -> bool:
        """
        Notify that a repricer run finished.

        Level: INFO when no errors, WARNINGS when errors > 0.

        Args:
            stats: Dict with keys:
                duration_min      float  — total run time in minutes
                total_products    int    — products loaded
                updated_products  int    — prices updated
                emma_mason        int    — Emma Mason products scraped
                competitors       dict   — {name: count} per competitor
                errors_count      int    — number of errors (optional, default 0)
        """
        duration = stats.get("duration_min", 0)
        total = stats.get("total_products", 0)
        updated = stats.get("updated_products", 0)
        emma = stats.get("emma_mason", 0)
        errors_count = stats.get("errors_count", 0)

        competitors_lines = []
        for name, count in stats.get("competitors", {}).items():
            competitors_lines.append(f"  • {name}: {count}")
        competitors_block = (
            "\n".join(competitors_lines) if competitors_lines else "  —"
        )

        status_icon = "✅" if errors_count == 0 else "⚠️"
        lines = [
            f"{status_icon} *Repricer completed*",
            f"⏱ Duration: {duration:.1f} min",
            f"📦 Products: {total} total | {updated} updated",
            f"🛒 Emma Mason: {emma}",
            f"🔍 Competitors:\n{competitors_block}",
        ]
        if errors_count:
            lines.append(f"❌ Errors: {errors_count}")
        lines.append(f"🕐 {_now()}")

        level = NotifyLevel.WARNINGS if errors_count else NotifyLevel.INFO
        return self._dispatch(level, "\n\n".join(lines))

    def send_run_failed(self, error: Exception) -> bool:
        """
        Notify that a repricer run crashed.  Level: CRITICAL.

        Args:
            error: The exception that caused the failure.
        """
        return self.send_critical(
            title="Repricer FAILED",
            details=f"`{type(error).__name__}: {str(error)[:300]}`",
        )

    def send_scraper_warning(self, scraper_name: str, message: str) -> bool:
        """
        Send a non-critical scraper warning (e.g. fallback activated).
        Level: WARNINGS.

        Args:
            scraper_name: Human-readable scraper name.
            message:      Warning details.
        """
        return self.send_warning(title=scraper_name, details=message)

    def send_algolia_key_refreshed(self, success: bool) -> bool:
        """
        Notify about Algolia API key auto-refresh result.

        Success → Level: WARNINGS.
        Failure → Level: ERRORS.

        Args:
            success: True if the refresh succeeded.
        """
        if success:
            text = (
                f"🔑 *Algolia key refreshed*\n\n"
                f"Auto-refresh via Playwright succeeded.\n"
                f"🕐 {_now()}"
            )
            return self._dispatch(NotifyLevel.WARNINGS, text)

        text = (
            f"🔑 *Algolia key refresh FAILED*\n\n"
            f"Fell back to HTML scraper.\n"
            f"🕐 {_now()}"
        )
        return self._dispatch(NotifyLevel.ERRORS, text)

    def send_scraper_status(
        self,
        scraper_name: str,
        products_count: int,
        duration_seconds: float,
        method: str = "",
    ) -> bool:
        """
        Send a per-scraper completion summary.  Level: ALL.

        Only recipients set to ALL receive these granular updates.

        Args:
            scraper_name:     Human-readable scraper name.
            products_count:   Number of products scraped.
            duration_seconds: Scraping duration.
            method:           Scraping method used (e.g. "Algolia API").
        """
        minutes, seconds = divmod(int(duration_seconds), 60)
        duration_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        lines = [
            f"📋 *{scraper_name}*",
            f"📦 Products: {products_count}",
            f"⏱ Time: {duration_str}",
        ]
        if method:
            lines.append(f"🔧 Method: {method}")
        lines.append(f"🕐 {_now()}")
        return self._dispatch(NotifyLevel.ALL, "\n".join(lines))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        """
        Send a test message to verify the bot is configured correctly.

        Sent at CRITICAL level so it reaches all non-SILENT recipients.

        Returns:
            True if the test message was delivered to at least one recipient.
        """
        logger.info("Testing Telegram connection...")
        text = (
            f"🤖 *Furniture Repricer*\n"
            f"Telegram notifications connected.\n"
            f"🕐 {_now()}"
        )
        result = self._dispatch(NotifyLevel.CRITICAL, text)
        if result:
            logger.info("[OK] Telegram test message sent")
        else:
            logger.error("[X] Telegram test failed — check token and chat_ids")
        return result

    def get_recipients_summary(self) -> str:
        """Return a human-readable summary of configured recipients."""
        if not self.recipients:
            return "No recipients configured"
        lines = [
            f"  • {r.name} (chat_id={r.chat_id}) → {r.level.name}"
            for r in self.recipients
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"TelegramBot("
            f"enabled={self.enabled}, "
            f"recipients={self.recipients!r})"
        )

    # ------------------------------------------------------------------
    # Internal dispatch + HTTP helpers
    # ------------------------------------------------------------------

    def _dispatch(self, level: NotifyLevel, text: str) -> bool:
        """
        Send `text` to all recipients whose configured level >= `level`.

        Args:
            level: Minimum level for this message.
            text:  Message text (Markdown).

        Returns:
            True if at least one recipient received the message.
        """
        if not self.enabled:
            return False

        targets = [r for r in self.recipients if r.level >= level]
        if not targets:
            logger.debug(
                f"No recipients at level>={level.name} — message skipped"
            )
            return False

        if len(text) > _MAX_MESSAGE_LENGTH:
            text = text[:_MAX_MESSAGE_LENGTH] + "\n...[truncated]"

        url = _API_BASE.format(token=self.token, method="sendMessage")
        any_sent = False

        for recipient in targets:
            if self._post_with_retry(url, recipient, text):
                any_sent = True

        return any_sent

    def _post_with_retry(
        self,
        url: str,
        recipient: _Recipient,
        text: str,
    ) -> bool:
        """
        Make the actual HTTP POST for a single recipient with retry logic.

        Args:
            url:       Telegram sendMessage endpoint URL.
            recipient: Target recipient.
            text:      Message text.

        Returns:
            True if the API accepted the message.
        """
        payload = {
            "chat_id": recipient.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)

                if response.status_code == 200:
                    logger.debug(
                        f"Telegram → {recipient.name} "
                        f"(attempt {attempt}): sent"
                    )
                    return True

                # 400 Bad Request — wrong chat_id, parse error, etc.
                if response.status_code == 400:
                    logger.error(
                        f"Telegram 400 Bad Request "
                        f"(recipient={recipient.name}): "
                        f"{response.text[:200]}"
                    )
                    return False

                # 429 Rate limit — respect Telegram's retry_after
                if response.status_code == 429:
                    retry_after = (
                        response.json()
                        .get("parameters", {})
                        .get("retry_after", self.retry_delay)
                    )
                    logger.warning(
                        f"Telegram rate limit "
                        f"(recipient={recipient.name}). "
                        f"Retrying after {retry_after}s..."
                    )
                    time.sleep(retry_after)
                    continue

                logger.warning(
                    f"Telegram HTTP {response.status_code} "
                    f"(recipient={recipient.name}, "
                    f"attempt {attempt}/{self.retry_attempts}): "
                    f"{response.text[:100]}"
                )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Telegram timeout "
                    f"(recipient={recipient.name}, "
                    f"attempt {attempt}/{self.retry_attempts})"
                )
            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    f"Telegram connection error "
                    f"(recipient={recipient.name}, attempt {attempt}): {exc}"
                )
            except Exception as exc:
                logger.error(
                    f"Unexpected Telegram error "
                    f"(recipient={recipient.name}): {exc}"
                )
                return False

            if attempt < self.retry_attempts:
                time.sleep(self.retry_delay)

        logger.error(
            f"Failed to deliver Telegram message to {recipient.name} "
            f"after {self.retry_attempts} attempts"
        )
        return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """Return current datetime as a readable string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
