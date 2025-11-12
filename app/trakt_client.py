"""Trakt.tv API client"""
import logging
from datetime import datetime
from typing import List, Dict, Optional
import trakt
from trakt import Trakt
from trakt.movies import Movie

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
        Trakt.configuration.defaults.client(
            id=self.client_id,
            secret=self.client_secret
        )

        # Set tokens if available
        if self.access_token:
            Trakt.configuration.defaults.oauth(
                token=self.access_token,
                refresh_token=self.refresh_token
            )

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

            # Get watched movies with history
            watched = Trakt['sync/history'].movies(
                start_at=since.isoformat() if since else None
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

            # Extract IDs
            ids = movie.ids if hasattr(movie, 'ids') else {}

            return {
                'title': movie.title if hasattr(movie, 'title') else 'Unknown',
                'year': movie.year if hasattr(movie, 'year') else None,
                'trakt_id': ids.get('trakt'),
                'imdb_id': ids.get('imdb'),
                'tmdb_id': ids.get('tmdb'),
                'watched_at': watched_at,
                'rating': None  # Will be populated separately
            }
        except Exception as e:
            logger.error(f"Error extracting movie data: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if the Trakt API connection is working"""
        try:
            # Try to fetch a small amount of data
            Trakt['sync/history'].movies(limit=1)
            logger.info("Trakt API connection test successful")
            return True
        except Exception as e:
            logger.error(f"Trakt API connection test failed: {e}")
            return False
