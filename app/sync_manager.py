"""Main sync orchestration"""
import logging
from datetime import datetime
from typing import Optional, Dict, List
from app.trakt_client import TraktClient
from app.letterboxd_csv import LetterboxdCSV
from app.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SyncManager:
    """Orchestrates syncing between Trakt and Letterboxd"""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.trakt_client = None
        self.letterboxd_csv = LetterboxdCSV(
            export_path=config_manager.get('sync', 'export_path')
        )
        self._initialize_trakt_client()

    def _initialize_trakt_client(self):
        """Initialize Trakt client with credentials"""
        try:
            client_id = self.config.get('trakt', 'client_id')
            client_secret = self.config.get('trakt', 'client_secret')
            access_token = self.config.get('trakt', 'access_token')
            refresh_token = self.config.get('trakt', 'refresh_token')

            if not client_id or not client_secret:
                logger.warning("Trakt credentials not configured")
                return

            # Debug logging
            logger.info(f"Initializing Trakt client with credentials:")
            logger.info(f"  - client_id: {'SET' if client_id else 'MISSING'}")
            logger.info(f"  - client_secret: {'SET' if client_secret else 'MISSING'}")
            logger.info(f"  - access_token: {'SET' if access_token else 'MISSING'}")
            logger.info(f"  - refresh_token: {'SET' if refresh_token else 'MISSING'}")

            self.trakt_client = TraktClient(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                refresh_token=refresh_token
            )

            logger.info("Trakt client initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing Trakt client: {e}")

    def sync(self, full_sync: bool = False) -> Dict:
        """
        Perform sync from Trakt to Letterboxd

        Args:
            full_sync: If True, sync all history. If False, only sync since last sync.

        Returns:
            Dictionary with sync results
        """
        result = {
            'success': False,
            'movies_synced': 0,
            'csv_path': None,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            if not self.trakt_client:
                raise Exception("Trakt client not initialized. Please configure API credentials.")

            # Determine sync start date
            since = None
            if not full_sync:
                since = self._get_sync_start_date()

            logger.info(f"Starting sync (full_sync={full_sync}, since={since})")

            # Fetch watched movies from Trakt
            watched_movies = self.trakt_client.get_watched_movies(since=since)

            if not watched_movies:
                logger.info("No movies to sync")
                result['success'] = True
                result['movies_synced'] = 0
                return result

            # Fetch ratings
            ratings = self.trakt_client.get_movie_ratings()

            # Merge ratings with watched movies
            for movie in watched_movies:
                trakt_id = str(movie.get('trakt_id', ''))
                if trakt_id in ratings:
                    movie['rating'] = ratings[trakt_id]

            # Generate Letterboxd CSV
            csv_path = self.letterboxd_csv.generate_csv(watched_movies)

            # Update last sync time
            self.config.set_last_sync_time()

            result['success'] = True
            result['movies_synced'] = len(watched_movies)
            result['csv_path'] = csv_path

            logger.info(f"Sync completed successfully: {len(watched_movies)} movies")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result['error'] = str(e)

        return result

    def _get_sync_start_date(self) -> Optional[datetime]:
        """Get the date to start syncing from"""
        # Check for last sync time
        last_sync = self.config.get_last_sync_time()
        if last_sync:
            logger.info(f"Last sync was at {last_sync}")
            return last_sync

        # Check for configured start date
        start_date_str = self.config.get('sync', 'start_date')
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
                logger.info(f"Using configured start date: {start_date}")
                return start_date
            except Exception as e:
                logger.warning(f"Invalid start_date in config: {e}")

        # No start date - will sync all history
        logger.info("No start date found - will sync all history")
        return None

    def test_connection(self) -> Dict:
        """Test connection to Trakt API"""
        result = {
            'trakt': False,
            'error': None
        }

        try:
            if not self.trakt_client:
                result['error'] = "Trakt client not initialized"
                return result

            result['trakt'] = self.trakt_client.test_connection()

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Connection test failed: {e}")

        return result

    def get_sync_stats(self) -> Dict:
        """Get statistics about sync history"""
        try:
            last_sync = self.config.get_last_sync_time()
            recent_exports = self.letterboxd_csv.get_recent_exports(limit=5)

            return {
                'last_sync': last_sync.isoformat() if last_sync else None,
                'recent_exports': recent_exports,
                'export_count': len(recent_exports)
            }

        except Exception as e:
            logger.error(f"Error getting sync stats: {e}")
            return {
                'last_sync': None,
                'recent_exports': [],
                'export_count': 0,
                'error': str(e)
            }

    def authenticate_trakt(self) -> str:
        """
        Initiate Trakt authentication

        Returns:
            Authentication URL for user
        """
        if not self.trakt_client:
            self._initialize_trakt_client()

        if not self.trakt_client:
            raise Exception("Cannot initialize Trakt client - check credentials")

        return self.trakt_client.authenticate()

    def complete_trakt_auth(self, code: str) -> bool:
        """
        Complete Trakt authentication with authorization code

        Args:
            code: Authorization code from user

        Returns:
            True if successful
        """
        try:
            if not self.trakt_client:
                raise Exception("Trakt client not initialized")

            access_token, refresh_token = self.trakt_client.exchange_code(code)

            # Save tokens to config
            self.config.set('trakt', 'access_token', value=access_token)
            self.config.set('trakt', 'refresh_token', value=refresh_token)

            # Reinitialize Trakt client with new tokens
            self._initialize_trakt_client()

            logger.info("Trakt authentication completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error completing Trakt auth: {e}")
            raise
