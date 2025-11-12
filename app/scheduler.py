"""Scheduling for automated syncing"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Manages scheduled sync operations"""

    def __init__(self, sync_manager, config_manager):
        self.sync_manager = sync_manager
        self.config = config_manager
        self.scheduler = BackgroundScheduler()
        self.job_id = 'trakt_letterboxd_sync'
        self.is_running = False

    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        try:
            # Get schedule from config
            schedule = self.config.get('sync', 'schedule', default='0 2 * * *')

            # Add sync job
            self.scheduler.add_job(
                func=self._scheduled_sync,
                trigger=CronTrigger.from_crontab(schedule),
                id=self.job_id,
                name='Trakt to Letterboxd Sync',
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True

            logger.info(f"Scheduler started with cron expression: {schedule}")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Scheduler stopped")

        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            raise

    def _scheduled_sync(self):
        """Perform scheduled sync (called by scheduler)"""
        try:
            logger.info("Starting scheduled sync")
            result = self.sync_manager.sync(full_sync=False)

            if result['success']:
                logger.info(f"Scheduled sync completed: {result['movies_synced']} movies synced")
            else:
                logger.error(f"Scheduled sync failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error in scheduled sync: {e}")

    def trigger_manual_sync(self, full_sync=False):
        """
        Trigger a manual sync immediately

        Args:
            full_sync: Whether to do a full sync or incremental

        Returns:
            Sync result dictionary
        """
        try:
            logger.info(f"Manual sync triggered (full_sync={full_sync})")
            result = self.sync_manager.sync(full_sync=full_sync)
            return result

        except Exception as e:
            logger.error(f"Error in manual sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def update_schedule(self, cron_expression):
        """
        Update the sync schedule

        Args:
            cron_expression: New cron expression for schedule
        """
        try:
            # Update config
            self.config.set('sync', 'schedule', value=cron_expression)

            # Restart scheduler if it's running
            if self.is_running:
                self.stop()
                self.start()
            else:
                self.start()

            logger.info(f"Schedule updated to: {cron_expression}")
            return True

        except Exception as e:
            logger.error(f"Error updating schedule: {e}")
            raise

    def get_next_run_time(self):
        """Get the next scheduled run time"""
        if not self.is_running:
            return None

        try:
            job = self.scheduler.get_job(self.job_id)
            if job and job.next_run_time:
                return job.next_run_time
            return None

        except Exception as e:
            logger.error(f"Error getting next run time: {e}")
            return None

    def get_status(self):
        """Get scheduler status"""
        next_run = self.get_next_run_time()

        return {
            'running': self.is_running,
            'schedule': self.config.get('sync', 'schedule'),
            'next_run': next_run.isoformat() if next_run else None
        }
