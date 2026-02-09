"""
Scheduler Module for Furniture Repricer
Automatic launch at a specified time with time zone support
"""

import time
import schedule
from datetime import datetime, timedelta
from typing import List, Optional, Callable
import pytz
import logging
from pathlib import Path
import subprocess
import sys

logger = logging.getLogger("scheduler")


class RepricerScheduler:
    """
    Scheduler for automatic repricer launch
    """
    
    def __init__(
        self,
        schedule_times: List[str],
        timezone: str = "America/New_York",
        enabled: bool = True,
        config_path: str = "config.yaml",
        timeout_hours: float = 4.0
    ):
        """
        Initialization of the scheduler
        
        Args:
            schedule_times: List of start times [“06:00”, “16:00”, “21:00”]
            timezone: Time zone (pytz timezone name)
            enabled: Whether the scheduler is enabled
            config_path: Path to config.yaml
            timeout_hours: Maximum execution time in hours (default: 4.0)
        """
        self.schedule_times = schedule_times
        self.timezone_name = timezone
        self.enabled = enabled
        self.config_path = config_path
        self.running = False
        self.timeout_seconds = int(timeout_hours * 3600)
        
        # Validate timezone
        try:
            self.timezone = pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.error(f"Unknown timezone: {timezone}, using UTC")
            self.timezone = pytz.UTC
            self.timezone_name = "UTC"
        
        # Stats
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run': None,
            'last_success': None,
            'last_error': None,
        }
        
        logger.info(f"Scheduler initialized: {len(schedule_times)} times, timezone: {timezone}")
        logger.info(f"Timeout: {timeout_hours} hours ({self.timeout_seconds} seconds)")
    
    def _get_current_time(self) -> datetime:
        """Get the current time in the configured timezone"""
        return datetime.now(self.timezone)
    
    def _run_repricer(self):
        """
        Launch the replayer
        
        Uses subprocess to run run_repricer.py
        """
        current_time = self._get_current_time()
        
        logger.info("="*60)
        logger.info(f"SCHEDULED RUN STARTED: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("="*60)
        
        self.stats['total_runs'] += 1
        self.stats['last_run'] = current_time.isoformat()
        
        try:
            # Identify Python executable and run script
            python_exe = sys.executable
            run_script = Path(__file__).parent.parent.parent / "run_repricer.py"
            
            if not run_script.exists():
                raise FileNotFoundError(f"run_repricer.py not found: {run_script}")
            
            # Run as a subprocess
            logger.info(f"Executing: {python_exe} {run_script}")
            logger.info(f"Timeout: {self.timeout_seconds/3600:.1f} hours")
            
            result = subprocess.run(
                [python_exe, str(run_script)],
                cwd=str(run_script.parent),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,  # Configurable timeout
                encoding='utf-8',
                errors='replace'  # Handle encoding errors gracefully
            )
            
            # Log output
            if result.stdout:
                logger.info("STDOUT:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            
            if result.stderr:
                logger.warning("STDERR:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        logger.warning(f"  {line}")
            
            # Check the result code
            if result.returncode == 0:
                logger.info("[OK] Repricer completed successfully")
                self.stats['successful_runs'] += 1
                self.stats['last_success'] = current_time.isoformat()
            else:
                logger.error(f"[FAIL] Repricer failed with code {result.returncode}")
                self.stats['failed_runs'] += 1
                self.stats['last_error'] = {
                    'time': current_time.isoformat(),
                    'code': result.returncode,
                    'stderr': result.stderr[-500:] if result.stderr else None
                }
        
        except subprocess.TimeoutExpired:
            timeout_hours = self.timeout_seconds / 3600
            logger.error(f"[TIMEOUT] Repricer execution timeout ({timeout_hours:.1f} hours)")
            self.stats['failed_runs'] += 1
            self.stats['last_error'] = {
                'time': current_time.isoformat(),
                'error': f'Timeout ({timeout_hours:.1f} hours)'
            }
        
        except Exception as e:
            logger.error(f"[ERROR] Repricer execution failed: {e}", exc_info=True)
            self.stats['failed_runs'] += 1
            self.stats['last_error'] = {
                'time': current_time.isoformat(),
                'error': str(e)
            }
        
        finally:
            logger.info("="*60)
            logger.info("SCHEDULED RUN COMPLETED")
            logger.info("="*60)
    
    def setup_schedule(self):
        """Set up a schedule for execution"""
        if not self.enabled:
            logger.warning("Scheduler is DISABLED")
            return
        
        # Clear existing schedule
        schedule.clear()
        
        # Add every time
        for time_str in self.schedule_times:
            try:
                # Validate time format
                datetime.strptime(time_str, "%H:%M")
                
                # Schedule job
                schedule.every().day.at(time_str).do(self._run_repricer)
                
                logger.info(f"[OK] Scheduled: {time_str} {self.timezone_name}")
            
            except ValueError:
                logger.error(f"Invalid time format: {time_str} (expected HH:MM)")
        
        # Show next runs
        self._log_next_runs()
    
    def _log_next_runs(self):
        """Log the following scheduled launches"""
        jobs = schedule.get_jobs()
        
        if not jobs:
            logger.warning("No jobs scheduled!")
            return
        
        logger.info(f"\nScheduled jobs ({len(jobs)}):")
        
        for job in jobs:
            next_run = job.next_run
            if next_run:
                # schedule library works in local system time (not UTC)
                # Just add timezone info without conversion
                next_run_local = self.timezone.localize(next_run)
                logger.info(f"  Next run: {next_run_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    def run_forever(self):
        """
        Run the scheduler in an infinite loop
        
        Executed until Ctrl+C or external stop
        """
        if not self.enabled:
            logger.error("Cannot run scheduler - it's disabled!")
            return
        
        self.running = True
        self.setup_schedule()
        
        logger.info("\n" + "="*60)
        logger.info("SCHEDULER STARTED")
        logger.info(f"Timezone: {self.timezone_name}")
        logger.info(f"Schedule times: {', '.join(self.schedule_times)}")
        logger.info(f"Timeout: {self.timeout_seconds/3600:.1f} hours per run")
        logger.info("Press Ctrl+C to stop")
        logger.info("="*60 + "\n")
        
        try:
            while self.running:
                # Check pending jobs
                schedule.run_pending()
                
                # Sleep 1 minute
                time.sleep(60)
                
                # Every hour, log next runs
                current_time = self._get_current_time()
                if current_time.minute == 0:
                    self._log_status()
        
        except KeyboardInterrupt:
            logger.info("\n[OK] Scheduler stopped by user (Ctrl+C)")
        
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
        
        finally:
            self.running = False
            logger.info("Scheduler shutdown complete")
    
    def _log_status(self):
        """Log current status"""
        current_time = self._get_current_time()
        
        logger.info("\n" + "-"*60)
        logger.info(f"STATUS UPDATE: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("-"*60)
        logger.info(f"Total runs: {self.stats['total_runs']}")
        logger.info(f"Successful: {self.stats['successful_runs']}")
        logger.info(f"Failed: {self.stats['failed_runs']}")
        
        if self.stats['last_run']:
            logger.info(f"Last run: {self.stats['last_run']}")
        
        if self.stats['last_success']:
            logger.info(f"Last success: {self.stats['last_success']}")
        
        if self.stats['last_error']:
            error_info = self.stats['last_error']
            logger.info(f"Last error: {error_info.get('time')} - {error_info.get('error')}")
        
        # Next runs
        self._log_next_runs()
        logger.info("-"*60 + "\n")
    
    def stop(self):
        """Stop the scheduler gracefully"""
        logger.info("Stopping scheduler...")
        self.running = False
    
    def run_once_now(self):
        """
        Start the replayer NOW (outside of schedule)
        """
        logger.info("Manual run triggered (outside schedule)")
        self._run_repricer()
    
    def get_stats(self) -> dict:
        """Get statistics"""
        return self.stats.copy()


def create_scheduler_from_config(config: dict) -> Optional[RepricerScheduler]:
    """
    Create a scheduler from the configuration
    
    Args:
        config: Config dictionary (з ConfigManager або YAML)
    
    Returns:
        RepricerScheduler instance або None якщо disabled
    """
    # Check if enabled
    enabled = config.get('schedule_enabled', False)
    
    if not enabled:
        logger.info("Scheduler disabled in config (schedule_enabled = FALSE)")
        return None
    
    # Get parameters
    times_str = config.get('schedule_times', '06:00,16:00,21:00')
    timezone = config.get('schedule_timezone', 'America/New_York')
    timeout_minutes = config.get('scraping_timeout_minutes', 240)  # Default: 4 hours
    
    # Parse times
    schedule_times = [t.strip() for t in times_str.split(',')]
    
    # Convert timeout to hours
    timeout_hours = timeout_minutes / 60.0
    
    # Create scheduler
    scheduler = RepricerScheduler(
        schedule_times=schedule_times,
        timezone=timezone,
        enabled=enabled,
        timeout_hours=timeout_hours
    )
    
    return scheduler

# ============================================================
# EXAMPLE OF USE

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-12s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print("\n" + "="*60)
    print("SCHEDULER MODULE TEST")
    print("="*60 + "\n")
    
    # Example 1: Manual scheduler
    print("Example 1: Create scheduler with custom times")
    scheduler = RepricerScheduler(
        schedule_times=["09:00", "15:00", "21:00"],
        timezone="America/New_York",
        enabled=True,
        timeout_hours=4.0
    )
    scheduler.setup_schedule()
    
    print("\nExample 2: Run once now (for testing)")
    # scheduler.run_once_now()  # Uncomment to test
    
    print("\nExample 3: From config")
    test_config = {
        'schedule_enabled': True,
        'schedule_times': '06:00,16:00,21:00',
        'schedule_timezone': 'America/New_York',
        'scraping_timeout_minutes': 240
    }
    scheduler2 = create_scheduler_from_config(test_config)
    
    if scheduler2:
        print("Scheduler created from config!")
        scheduler2.setup_schedule()
    
    print("\n[OK] Scheduler module test complete!")
    print("\nTo run forever: scheduler.run_forever()")
    print("To stop: Press Ctrl+C")
