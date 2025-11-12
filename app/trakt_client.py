"""Trakt.tv API client"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
import trakt
from trakt import Trakt

logger = logging.getLogger(__name__)


class TraktClient:
    """Client for interacting with Trakt.tv API"""

    def __init__(self, client_id, client_secret, access_token=None, refresh_token=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._configure_trakt()

    def _configure_trakt(self):
        """Configure Trakt API client"""
        # Configure client credentials
        Trakt.configuration.defaults.client(
            id=self.client_id,
            secret=self.client_secret
        )

        # Configure HTTP settings
        Trakt.configuration.defaults.http(
            retry=True,
            timeout=30
        )

        # Set OAuth tokens if available
        if self.access_token:
            # Properly configure OAuth with all required fields
            Trakt.configuration.defaults.oauth(
                token=self.access_token,
                refresh_token=self.refresh_token
            )
            logger.info("OAuth tokens configured for Trakt API")
        else:
            logger.warning("No access token available - authentication required")

    def authenticate(self, redirect_uri='urn:ietf:wg:oauth:2.0:oob'):
        """
        Initiate OAuth authentication flow
        Returns: (auth_url, pin_url) tuple for user to complete authentication
        """
        try:
            # Get authentication URL
            auth_url = Trakt['oauth'].authorize_url(redirect_uri)
            logger.info("Generated authentication URL")
            return auth_url
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            raise

    def exchange_code(self, code, redirect_uri='urn:ietf:wg:oauth:2.0:oob'):
        """
        Exchange authorization code for access token
        Returns: (access_token, refresh_token) tuple
        """
        try:
            token = Trakt['oauth'].token_exchange(code, redirect_uri)
            self.access_token = token.get('access_token')
            self.refresh_token = token.get('refresh_token')

            # Update configuration with new tokens
            Trakt.configuration.defaults.oauth(
                token=self.access_token,
                refresh_token=self.refresh_token
            )

            logger.info("Successfully exchanged code for access token")
            return self.access_token, self.refresh_token
        except Exception as e:
            logger.error(f"Error exchanging code: {e}")
            raise

    def get_watched_movies(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Get list of watched movies

        Args:
            since: Only get movies watched after this datetime

        Returns:
            List of movie dictionaries with watch history
        """
        try:
            logger.info("Fetching watched movies from Trakt")

            # Convert since to ISO format for Trakt API if provided
            start_at = None
            if since:
                # Ensure since is a datetime object (defensive check)
                if isinstance(since, str):
                    # Parse string to datetime if needed
                    from app.config_manager import parse_dt
                    since = parse_dt(since)
                    if not since:
                        logger.warning("Could not parse since parameter as datetime, ignoring")
                        since = None

                if since:
                    # Ensure UTC timezone
                    if since.tzinfo:
                        since_utc = since.astimezone(timezone.utc)
                    else:
                        since_utc = since.replace(tzinfo=timezone.utc)

                    # Pass datetime object directly (trakt.py v4.4.0 expects datetime, not string)
                    start_at = since_utc
                    logger.info(f"Syncing movies since: {since_utc.isoformat(timespec='seconds').replace('+00:00', 'Z')}")

            # Get watched movies with history
            # Use extended='full' to get all IDs (tmdb, imdb, etc.)
            watched = Trakt['sync/history'].movies(
                start_at=start_at,
                extended='full'
            )

            movies_list = []
            for item in watched:
                movie_data = self._extract_movie_data(item)
                if movie_data:
                    movies_list.append(movie_data)

            logger.info(f"Retrieved {len(movies_list)} watched movies")
            return movies_list

        except Exception as e:
            logger.error(f"Error fetching watched movies: {e}")
            raise

    def get_movie_ratings(self) -> Dict[str, float]:
        """
        Get user's movie ratings

        Returns:
            Dictionary mapping movie IDs to ratings
        """
        try:
            logger.info("Fetching movie ratings from Trakt")
            ratings = Trakt['sync/ratings'].movies()

            ratings_dict = {}
            for item in ratings:
                if hasattr(item, 'movie') and item.movie:
                    trakt_id = item.movie.ids.get('trakt')
                    rating = item.rating
                    if trakt_id and rating:
                        ratings_dict[str(trakt_id)] = rating

            logger.info(f"Retrieved {len(ratings_dict)} movie ratings")
            return ratings_dict

        except Exception as e:
            logger.error(f"Error fetching ratings: {e}")
            return {}

    def _extract_movie_data(self, history_item) -> Optional[Dict]:
        """Extract movie data from history item"""
        try:
            movie = history_item.movie if hasattr(history_item, 'movie') else history_item
            watched_at = history_item.watched_at if hasattr(history_item, 'watched_at') else None

            if not movie:
                return None

            # Extract IDs (ids is an object with attributes, not a dict)
            ids = movie.ids if hasattr(movie, 'ids') else None

            # Debug: Log what we got from Trakt
            movie_title = movie.title if hasattr(movie, 'title') else 'Unknown'
            logger.debug(f"Processing movie: {movie_title}")
            logger.debug(f"  - ids object type: {type(ids)}")
            logger.debug(f"  - ids object: {ids}")
            logger.debug(f"  - ids dir: {dir(ids) if ids else 'None'}")

            # Get IDs - try dict access first, then attribute access
            trakt_id = None
            imdb_id = None
            tmdb_id = None

            if ids:
                # Try dictionary access first
                if isinstance(ids, dict):
                    trakt_id = ids.get('trakt')
                    imdb_id = ids.get('imdb')
                    tmdb_id = ids.get('tmdb')
                else:
                    # Try attribute/bracket access (trakt.py uses special dict-like objects)
                    try:
                        trakt_id = ids['trakt'] if 'trakt' in ids else getattr(ids, 'trakt', None)
                        imdb_id = ids['imdb'] if 'imdb' in ids else getattr(ids, 'imdb', None)
                        tmdb_id = ids['tmdb'] if 'tmdb' in ids else getattr(ids, 'tmdb', None)
                    except (KeyError, TypeError):
                        # Fallback to attribute access only
                        trakt_id = getattr(ids, 'trakt', None)
                        imdb_id = getattr(ids, 'imdb', None)
                        tmdb_id = getattr(ids, 'tmdb', None)

            logger.debug(f"  - Extracted IDs: trakt={trakt_id}, imdb={imdb_id}, tmdb={tmdb_id}")

            return {
                'title': movie_title,
                'year': movie.year if hasattr(movie, 'year') else None,
                'trakt_id': trakt_id,
                'imdb_id': imdb_id,
                'tmdb_id': tmdb_id,
                'watched_at': watched_at,
                'rating': None  # Will be populated separately
            }
        except Exception as e:
            logger.error(f"Error extracting movie data: {e}", exc_info=True)
            return None

    def test_connection(self) -> bool:
        """Test if the Trakt API connection is working"""
        try:
            # Try to fetch watched history (just check if API responds)
            # Get the generator/iterator but don't fully consume it
            history = Trakt['sync/history'].movies()
            # Try to get first item to verify connection works
            try:
                next(iter(history))
            except StopIteration:
                # Empty history is fine, connection works
                pass
            logger.info("Trakt API connection test successful")
            return True
        except Exception as e:
            logger.error(f"Trakt API connection test failed: {e}")
            return False
