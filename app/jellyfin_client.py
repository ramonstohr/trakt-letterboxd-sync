"""Jellyfin API client for fetching watched movies"""
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Client for interacting with Jellyfin API"""

    def __init__(self, url: str, api_key: str, user_id: str):
        """
        Initialize Jellyfin client

        Args:
            url: Jellyfin server URL (e.g., http://localhost:8096)
            api_key: Jellyfin API key
            user_id: Jellyfin user ID
        """
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.user_id = user_id
        self.session = requests.Session()

        # Set authentication header
        self.session.headers.update({
            'X-Emby-Token': api_key,
            'Accept': 'application/json'
        })

    def test_connection(self) -> bool:
        """Test if the Jellyfin API connection is working"""
        try:
            response = self.session.get(f"{self.url}/System/Info")
            if response.status_code == 200:
                info = response.json()
                logger.info(f"Connected to Jellyfin {info.get('Version', 'unknown')}")
                return True
            else:
                logger.error(f"Jellyfin connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Jellyfin API connection test failed: {e}")
            return False

    def get_watched_movies(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Get list of watched movies from Jellyfin

        Args:
            since: Only get movies watched after this datetime

        Returns:
            List of movie dictionaries with watch history
        """
        try:
            logger.info("Fetching watched movies from Jellyfin")

            # Build query parameters
            params = {
                'Filters': 'IsPlayed',
                'IncludeItemTypes': 'Movie',
                'Recursive': 'true',
                'Fields': 'ProviderIds,UserData,ProductionYear,PremiereDate',
                'SortBy': 'DatePlayed',
                'SortOrder': 'Descending',
                'EnableUserData': 'true'
            }

            # Make request
            endpoint = f"{self.url}/Users/{self.user_id}/Items"
            response = self.session.get(endpoint, params=params)

            if response.status_code != 200:
                logger.error(f"Failed to fetch movies from Jellyfin: {response.status_code}")
                logger.debug(f"Response: {response.text[:500]}")
                return []

            data = response.json()
            items = data.get('Items', [])

            logger.info(f"Retrieved {len(items)} watched movies from Jellyfin")

            # Convert to our format
            movies_list = []
            for item in items:
                movie_data = self._extract_movie_data(item)
                if movie_data:
                    # Filter by date if specified
                    if since and movie_data.get('watched_at'):
                        watched_at = movie_data['watched_at']
                        if isinstance(watched_at, datetime) and watched_at < since:
                            continue

                    movies_list.append(movie_data)

            logger.info(f"Processed {len(movies_list)} movies" +
                       (f" (since {since})" if since else ""))
            return movies_list

        except Exception as e:
            logger.error(f"Error fetching watched movies from Jellyfin: {e}", exc_info=True)
            raise

    def _extract_movie_data(self, item: Dict) -> Optional[Dict]:
        """Extract movie data from Jellyfin item"""
        try:
            title = item.get('Name', 'Unknown')
            year = item.get('ProductionYear')

            # Get provider IDs (TMDB, IMDB)
            provider_ids = item.get('ProviderIds', {})
            tmdb_id = provider_ids.get('Tmdb')
            imdb_id = provider_ids.get('Imdb')

            # Get user data (watched status, date, etc.)
            user_data = item.get('UserData', {})
            played = user_data.get('Played', False)

            if not played:
                logger.debug(f"Skipping '{title}' - not marked as played")
                return None

            # Get last played date
            last_played_date = user_data.get('LastPlayedDate')
            watched_at = None

            if last_played_date:
                try:
                    # Parse ISO datetime from Jellyfin
                    watched_at = datetime.fromisoformat(last_played_date.replace('Z', '+00:00'))
                    # Ensure UTC
                    if watched_at.tzinfo:
                        watched_at = watched_at.astimezone(timezone.utc)
                    else:
                        watched_at = watched_at.replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.warning(f"Could not parse date '{last_played_date}': {e}")

            logger.debug(f"Extracted movie '{title}' ({year}): tmdb={tmdb_id}, imdb={imdb_id}, watched={watched_at}")

            return {
                'title': title,
                'year': year,
                'tmdb_id': tmdb_id,
                'imdb_id': imdb_id,
                'trakt_id': None,  # Not available from Jellyfin
                'watched_at': watched_at,
                'rating': None  # Jellyfin ratings could be added later
            }

        except Exception as e:
            logger.error(f"Error extracting movie data: {e}", exc_info=True)
            return None
