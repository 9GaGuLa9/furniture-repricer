"""
ErrorLogger - Preserving scraping errors in Google Sheets

Creates a sheet called "Scraping_Errors" and records all errors with timestamp,
scraper name, error message, traceback, and URL if available.

✨ NEW: Auto-cleanup of old errors based on retention_days setting
"""

import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from .logger import get_logger

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
        sheets_client, 
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
        self.client = sheets_client
        self.sheet_id = sheet_id
        self.enabled = enabled
        self.retention_days = retention_days
        self.logger = logger
        self.error_sheet_name = "Scraping_Errors"
        
        # Statistics
        self.stats = {
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
    
    def _ensure_error_sheet_exists(self):
        """Create the Scraping_Errors sheet if it does not exist"""
        try:
            if not self.client.worksheet_exists(self.sheet_id, self.error_sheet_name):
                self.logger.info(f"Creating {self.error_sheet_name} sheet...")
                
                worksheet = self.client.create_worksheet(
                    self.sheet_id,
                    self.error_sheet_name,
                    rows=1000,
                    cols=6
                )
                
                # Headers
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
        Delete errors older than retention_days
        
        Returns:
            Number of deleted rows
        """
        if not self.enabled:
            return 0
        
        try:
            worksheet = self.client.open_sheet(self.sheet_id, self.error_sheet_name)
            
            # Get all data
            all_data = worksheet.get_all_values()
            
            if len(all_data) <= 1:  # Only headers or empty
                self.logger.debug("No errors to clean up")
                return 0
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Find rows to delete (older than cutoff_date)
            rows_to_delete = []
            
            for idx, row in enumerate(all_data[1:], start=2):  # Skip header (row 1)
                if not row or not row[0]:  # Empty row or no timestamp
                    continue
                
                try:
                    # Parse timestamp (format: YYYY-MM-DD HH:MM:SS)
                    row_timestamp = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                    
                    if row_timestamp < cutoff_date:
                        rows_to_delete.append(idx)
                
                except (ValueError, IndexError):
                    # If we can't parse timestamp - skip
                    continue
            
            # Delete rows if found
            if rows_to_delete:
                deleted_count = self._delete_rows_batch(worksheet, rows_to_delete)
                
                self.logger.info(
                    f"[x]️  Cleaned up {deleted_count} old errors "
                    f"(older than {self.retention_days} days)"
                )
                
                self.stats['errors_cleaned'] += deleted_count
                self.stats['last_cleanup'] = datetime.now()
                
                return deleted_count
            else:
                self.logger.debug(f"No errors older than {self.retention_days} days")
                return 0
        
        except Exception as e:
            self.logger.error(f"Failed to cleanup old errors: {e}")
            return 0
    
    def _delete_rows_batch(self, worksheet, row_indices: list) -> int:
        """
        Delete multiple rows efficiently (from bottom to top)
        
        Args:
            worksheet: Worksheet instance
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
        
        try:
            # Delete rows in batches to avoid rate limits
            batch_size = 100
            
            for i in range(0, len(sorted_indices), batch_size):
                batch = sorted_indices[i:i + batch_size]
                
                for row_idx in batch:
                    worksheet.delete_rows(row_idx)
                    deleted += 1
                
                # Small delay between batches
                if i + batch_size < len(sorted_indices):
                    import time
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
    ):
        """
        Record an error in Google Sheets
        
        Args:
            scraper_name: Title scraper
            error: Exception object
            url: URL where the error occurred (optional)
            context: Additional context (optional)
            auto_cleanup: Run cleanup after logging (default: False)
        """
        if not self.enabled:
            return
        
        try:
            # Prepare data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            error_type = type(error).__name__
            error_message = str(error)
            
            # Traceback
            tb = ''.join(traceback.format_tb(error.__traceback__))
            
            # Limit length for Google Sheets
            error_message = error_message[:500]
            tb = tb[:1000]
            
            # Add context if available
            if context:
                context_str = str(context)[:200]
                error_message = f"{error_message} | Context: {context_str}"
            
            # Prepare the line
            row = [
                timestamp,
                scraper_name,
                error_type,
                error_message,
                url or '',
                tb
            ]
            
            # Save to Google Sheets
            worksheet = self.client.open_sheet(self.sheet_id, self.error_sheet_name)
            worksheet.append_row(row, value_input_option='USER_ENTERED')
            
            self.stats['errors_logged'] += 1
            
            self.logger.warning(
                f"Error logged to {self.error_sheet_name}: {scraper_name} - {error_type}"
            )
            
            # Optional auto-cleanup after logging
            if auto_cleanup:
                self.cleanup_old_errors()
        
        except Exception as e:
            self.logger.error(f"Failed to log error to sheet: {e}")
            # Don't raise an error - this is fallback logging
    
    def get_stats(self) -> dict:
        """Get error logging statistics"""
        return {
            **self.stats,
            'retention_days': self.retention_days,
            'enabled': self.enabled
        }
    
    def get_error_count(self, days: Optional[int] = None) -> int:
        """
        Get count of errors in the last N days
        
        Args:
            days: Number of days to look back (None = all errors)
        
        Returns:
            Count of errors
        """
        if not self.enabled:
            return 0
        
        try:
            worksheet = self.client.open_sheet(self.sheet_id, self.error_sheet_name)
            all_data = worksheet.get_all_values()
            
            if len(all_data) <= 1:
                return 0
            
            if days is None:
                # Count all errors (exclude header)
                return len(all_data) - 1
            
            # Count errors in last N days
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
    Mixin for scrapers to add error logging
    
    Usage:
        class MyScraper(ScraperErrorMixin):
            def __init__(self, error_logger):
                self.error_logger = error_logger
                self.scraper_name = "MyScraper"
            
            def scrape(self):
                try:
                    # ... scraping ...
                except Exception as e:
                    self.log_scraping_error(e, url="http://...")
    """
    
    def log_scraping_error(
        self,
        error: Exception,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log scraping error
        
        Args:
            error: Exception
            url: URL where the error occurred
            context: Additional context
        """
        if hasattr(self, 'error_logger') and self.error_logger:
            scraper_name = getattr(self, 'scraper_name', self.__class__.__name__)
            self.error_logger.log_error(scraper_name, error, url, context)
        else:
            # Fallback to regular logger
            logger.error(f"Scraping error in {self.__class__.__name__}: {error}")
