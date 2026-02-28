"""
ErrorLogger - Preserving scraping errors in Google Sheets

Creates a sheet called "Scraping_Errors" and records all errors with timestamp,
scraper name, error message, traceback, and URL if available.

Auto-cleanup of old errors based on retention_days setting
"""

import time
import traceback
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Any, Optional

import gspread

from .logger import get_logger

if TYPE_CHECKING:
    from .google_sheets import GoogleSheetsClient

logger = get_logger("error_logger")


class ErrorLogger:
    """
    Logging scraping errors in Google Sheets with auto-cleanup

    Creates a sheet named "Scraping_Errors" with columns:
    - Timestamp
    - Scraper
    - Error Type
    - Error Message
    - URL (if present)
    - Traceback

    Features:
    - Auto-cleanup of old errors based on retention_days
    - Efficient batch deletion
    - Maintains sheet size
    """

    def __init__(
        self,
        sheets_client: 'GoogleSheetsClient',
        sheet_id: str,
        enabled: bool = True,
        retention_days: int = 30,
        cleanup_on_start: bool = True
    ):
        """
        Args:
            sheets_client: GoogleSheetsClient instance
            sheet_id: ID Google Sheets tables
            enabled: Is error saving enabled?
            retention_days: How many days to keep errors (default: 30)
            cleanup_on_start: Run cleanup on initialization (default: True)
        """
        self.client: 'GoogleSheetsClient' = sheets_client
        self.sheet_id: str = sheet_id
        self.enabled: bool = enabled
        self.retention_days: int = retention_days
        self.logger = logger
        self.error_sheet_name: str = "Scraping_Errors"

        # Statistics
        self.stats: Dict[str, Any] = {
            'errors_logged': 0,
            'errors_cleaned': 0,
            'last_cleanup': None
        }

        # Create a sheet if it does not exist
        if self.enabled:
            self._ensure_error_sheet_exists()

            # Run initial cleanup if requested
            if cleanup_on_start:
                self.cleanup_old_errors()

    def _ensure_error_sheet_exists(self) -> None:
        """Create the Scraping_Errors sheet if it does not exist."""
        try:
            if not self.client.worksheet_exists(self.sheet_id, self.error_sheet_name):
                self.logger.info(f"Creating {self.error_sheet_name} sheet...")

                worksheet: gspread.Worksheet = self.client.create_worksheet(
                    self.sheet_id,
                    self.error_sheet_name,
                    rows=1000,
                    cols=6
                )

                headers = [
                    'Timestamp',
                    'Scraper',
                    'Error Type',
                    'Error Message',
                    'URL',
                    'Traceback'
                ]

                worksheet.update('A1', [headers])
                self.logger.info(f"[OK] Created {self.error_sheet_name} sheet")

        except Exception as e:
            self.logger.error(f"Failed to create {self.error_sheet_name} sheet: {e}")
            self.enabled = False

    def cleanup_old_errors(self) -> int:
        """
        Delete errors older than retention_days.

        Returns:
            Number of deleted rows
        """
        if not self.enabled:
            return 0

        try:
            worksheet: gspread.Worksheet = self.client.open_sheet(
                self.sheet_id, self.error_sheet_name
            )

            all_data: List[List[str]] = worksheet.get_all_values()

            if len(all_data) <= 1:  # Only headers or empty
                self.logger.debug("No errors to clean up")
                return 0

            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            rows_to_delete: List[int] = []

            for idx, row in enumerate(all_data[1:], start=2):  # Skip header (row 1)
                if not row or not row[0]:  # Empty row or no timestamp
                    continue

                try:
                    row_timestamp = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    if row_timestamp < cutoff_date:
                        rows_to_delete.append(idx)
                except (ValueError, IndexError):
                    continue

            if rows_to_delete:
                deleted_count = self._delete_rows_batch(worksheet, rows_to_delete)

                self.logger.info(
                    f"[x]️  Cleaned up {deleted_count} old errors "
                    f"(older than {self.retention_days} days)"
                )

                self.stats['errors_cleaned'] += deleted_count
                self.stats['last_cleanup'] = datetime.now()

                return deleted_count

            self.logger.debug(f"No errors older than {self.retention_days} days")
            return 0

        except Exception as e:
            self.logger.error(f"Failed to cleanup old errors: {e}")
            return 0

    def _delete_rows_batch(
        self,
        worksheet: gspread.Worksheet,
        row_indices: List[int]
    ) -> int:
        """
        Delete multiple rows efficiently (from bottom to top).

        Args:
            worksheet: gspread Worksheet instance
            row_indices: List of row numbers to delete (1-indexed)

        Returns:
            Number of deleted rows
        """
        if not row_indices:
            return 0

        # Sort in reverse order to delete from bottom to top
        # (so that indexes are not shifted during deletion)
        sorted_indices = sorted(row_indices, reverse=True)
        deleted = 0
        batch_size = 100

        try:
            for i in range(0, len(sorted_indices), batch_size):
                batch = sorted_indices[i:i + batch_size]

                for row_idx in batch:
                    worksheet.delete_rows(row_idx)
                    deleted += 1

                # Small delay between batches to avoid rate limits
                if i + batch_size < len(sorted_indices):
                    time.sleep(1)

            return deleted

        except Exception as e:
            self.logger.error(f"Failed to delete rows batch: {e}")
            return deleted

    def log_error(
        self,
        scraper_name: str,
        error: Exception,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        auto_cleanup: bool = False
    ) -> None:
        """
        Record an error in Google Sheets.

        Args:
            scraper_name: Scraper name
            error: Exception object
            url: URL where the error occurred (optional)
            context: Additional context (optional)
            auto_cleanup: Run cleanup after logging (default: False)
        """
        if not self.enabled:
            return

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_type = type(error).__name__
            error_message = str(error)[:500]
            tb = ''.join(traceback.format_tb(error.__traceback__))[:1000]

            if context:
                context_str = str(context)[:200]
                error_message = f"{error_message} | Context: {context_str}"

            row = [
                timestamp,
                scraper_name,
                error_type,
                error_message,
                url or '',
                tb
            ]

            worksheet: gspread.Worksheet = self.client.open_sheet(
                self.sheet_id, self.error_sheet_name
            )
            worksheet.append_row(row, value_input_option='RAW')

            self.stats['errors_logged'] += 1

            self.logger.warning(
                f"Error logged to {self.error_sheet_name}: "
                f"{scraper_name} - {error_type}"
            )

            if auto_cleanup:
                self.cleanup_old_errors()

        except Exception as e:
            self.logger.error(f"Failed to log error to sheet: {e}")
            # Don't raise — this is fallback logging

    def get_stats(self) -> Dict[str, Any]:
        """Get error logging statistics."""
        return {
            **self.stats,
            'retention_days': self.retention_days,
            'enabled': self.enabled
        }

    def get_error_count(self, days: Optional[int] = None) -> int:
        """
        Get count of errors in the last N days.

        Args:
            days: Number of days to look back (None = all errors)

        Returns:
            Count of errors
        """
        if not self.enabled:
            return 0

        try:
            worksheet: gspread.Worksheet = self.client.open_sheet(
                self.sheet_id, self.error_sheet_name
            )
            all_data: List[List[str]] = worksheet.get_all_values()

            if len(all_data) <= 1:
                return 0

            if days is None:
                return len(all_data) - 1  # Exclude header

            cutoff_date = datetime.now() - timedelta(days=days)
            count = 0

            for row in all_data[1:]:  # Skip header
                if not row or not row[0]:
                    continue
                try:
                    row_timestamp = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    if row_timestamp >= cutoff_date:
                        count += 1
                except (ValueError, IndexError):
                    continue

            return count

        except Exception as e:
            self.logger.error(f"Failed to get error count: {e}")
            return 0


class ScraperErrorMixin:
    """
    Mixin for scrapers to add error logging.

    Usage:
        class MyScraper(ScraperErrorMixin):
            def __init__(self, error_logger: Optional[ErrorLogger]):
                self.error_logger: Optional[ErrorLogger] = error_logger
                self.scraper_name = "MyScraper"

            def scrape(self):
                try:
                    # ... scraping ...
                except Exception as e:
                    self.log_scraping_error(e, url="http://...")
    """

    error_logger: Optional[ErrorLogger] = None
    scraper_name: str = ""

    def log_scraping_error(
        self,
        error: Exception,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log scraping error.

        Args:
            error: Exception
            url: URL where the error occurred
            context: Additional context
        """
        if self.error_logger is not None:
            name = self.scraper_name or self.__class__.__name__
            self.error_logger.log_error(name, error, url, context)
        else:
            logger.error(f"Scraping error in {self.__class__.__name__}: {error}")
