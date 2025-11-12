"""Letterboxd.com API client for uploading watch history"""
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class LetterboxdClient:
    """Client for interacting with Letterboxd.com"""

    BASE_URL = "https://letterboxd.com"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        self.csrf_token = None
        self.logged_in = False

    def login(self) -> bool:
        """
        Login to Letterboxd using username and password

        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info(f"Logging in to Letterboxd as {self.username}")

            # Step 1: Get login page to extract CSRF token
            # Letterboxd uses /sign-in/ for the login page
            login_page_url = f"{self.BASE_URL}/sign-in/"
            response = self.session.get(login_page_url)

            if response.status_code != 200:
                logger.error(f"Failed to load login page: {response.status_code}")
                return False

            # Parse CSRF token from the login form
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_input = soup.find('input', {'name': '__csrf'})

            if not csrf_input:
                logger.error("Could not find CSRF token on login page")
                # Try alternative: look for meta tag
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    self.csrf_token = csrf_meta.get('content')
                    logger.debug(f"Got CSRF token from meta tag: {self.csrf_token[:20]}...")
                else:
                    logger.error("Could not find CSRF token in any form")
                    return False
            else:
                self.csrf_token = csrf_input.get('value')
                logger.debug(f"Got CSRF token from input: {self.csrf_token[:20]}...")

            # Step 2: Submit login form
            login_data = {
                '__csrf': self.csrf_token,
                'username': self.username,
                'password': self.password,
                'authenticationCode': '',  # For 2FA, currently not supported
            }

            response = self.session.post(login_page_url, data=login_data, allow_redirects=True)

            # Check if login was successful
            if response.status_code == 200:
                # Verify we're logged in by checking for username in response
                if self.username.lower() in response.text.lower():
                    logger.info("Successfully logged in to Letterboxd")
                    self.logged_in = True

                    # Update CSRF token from response if present
                    soup = BeautifulSoup(response.text, 'html.parser')
                    csrf_input = soup.find('input', {'name': '__csrf'})
                    if csrf_input:
                        self.csrf_token = csrf_input.get('value')

                    return True
                else:
                    logger.error("Login failed - invalid credentials")
                    return False
            else:
                logger.error(f"Login request failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error during login: {e}")
            return False

    def get_film_id_from_tmdb(self, tmdb_id: str) -> Optional[str]:
        """
        Get Letterboxd film ID from TMDB ID

        Args:
            tmdb_id: TMDB ID of the film

        Returns:
            Letterboxd film ID or None if not found
        """
        try:
            # Letterboxd has a /tmdb/ redirect endpoint
            tmdb_url = f"{self.BASE_URL}/tmdb/{tmdb_id}"
            response = self.session.get(tmdb_url, allow_redirects=True)

            if response.status_code == 200:
                # Extract film slug from final URL
                # Example: https://letterboxd.com/film/inception-2010/ -> inception-2010
                final_url = response.url
                match = re.search(r'/film/([^/]+)/', final_url)

                if match:
                    film_slug = match.group(1)

                    # Now we need to get the actual film ID from the page
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for data-film-id attribute
                    film_container = soup.find('div', {'data-film-id': True})
                    if film_container:
                        film_id = film_container.get('data-film-id')
                        logger.debug(f"Found Letterboxd film ID {film_id} for TMDB {tmdb_id}")
                        return film_id

                    # Alternative: look in script tags for filmId
                    for script in soup.find_all('script'):
                        if script.string and 'filmId' in script.string:
                            match = re.search(r'"filmId"\s*:\s*"?(\d+)"?', script.string)
                            if match:
                                film_id = match.group(1)
                                logger.debug(f"Found Letterboxd film ID {film_id} for TMDB {tmdb_id}")
                                return film_id

                    logger.warning(f"Could not extract film ID for TMDB {tmdb_id}")
                    return None
                else:
                    logger.warning(f"Could not parse film URL for TMDB {tmdb_id}")
                    return None
            else:
                logger.warning(f"TMDB redirect failed for {tmdb_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting film ID for TMDB {tmdb_id}: {e}")
            return None

    def mark_as_watched(
        self,
        film_id: str,
        watched_date: datetime,
        rating: Optional[float] = None,
        liked: bool = False,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Mark a film as watched on Letterboxd

        Args:
            film_id: Letterboxd film ID
            watched_date: Date when the film was watched
            rating: Rating (0.5 to 5.0 in 0.5 increments), None for no rating
            liked: Whether the film is liked
            tags: Optional list of tags

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.logged_in:
                logger.error("Not logged in to Letterboxd")
                return False

            logger.info(f"Marking film {film_id} as watched on {watched_date.strftime('%Y-%m-%d')}")

            # Format the viewing date
            viewing_date_str = watched_date.strftime('%Y-%m-%d')

            # Prepare rating (convert to Letterboxd format: 0, 1-10 as half-stars)
            # Rating 0.5 -> 1, 1.0 -> 2, 1.5 -> 3, ..., 5.0 -> 10
            rating_value = "0"
            if rating:
                rating_value = str(int(rating * 2))

            # Prepare data
            diary_data = {
                '__csrf': self.csrf_token,
                'filmId': film_id,
                'viewingDateStr': viewing_date_str,
                'rating': rating_value,
                'liked': 'true' if liked else 'false',
                'review': '',  # Empty review
                'tags': ','.join(tags) if tags else '',
            }

            # Submit to Letterboxd
            save_url = f"{self.BASE_URL}/s/save-diary-entry"
            response = self.session.post(save_url, data=diary_data)

            if response.status_code == 200:
                logger.info(f"Successfully marked film {film_id} as watched")
                return True
            else:
                logger.error(f"Failed to mark film as watched: {response.status_code}")
                logger.debug(f"Response: {response.text[:500]}")
                return False

        except Exception as e:
            logger.error(f"Error marking film as watched: {e}")
            return False

    def is_film_in_diary(self, film_id: str, watched_date: datetime) -> bool:
        """
        Check if a film is already in the diary for a specific date

        Args:
            film_id: Letterboxd film ID
            watched_date: Date to check

        Returns:
            True if film is already logged on this date
        """
        try:
            # This would require fetching the user's diary and checking
            # For now, we'll return False to always attempt upload
            # A more sophisticated version would parse the diary page
            return False

        except Exception as e:
            logger.error(f"Error checking diary: {e}")
            return False

    def upload_movies(self, movies: List[Dict]) -> Dict:
        """
        Upload multiple movies to Letterboxd

        Args:
            movies: List of movie dictionaries with:
                - tmdb_id: TMDB ID
                - watched_at: datetime object
                - rating: Optional rating (Letterboxd scale 0.5-5.0)
                - title: Movie title (for logging)

        Returns:
            Dictionary with upload results
        """
        result = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        if not self.logged_in:
            if not self.login():
                result['errors'].append("Failed to login to Letterboxd")
                return result

        logger.info(f"Uploading {len(movies)} movies to Letterboxd")

        for movie in movies:
            try:
                tmdb_id = movie.get('tmdb_id')
                if not tmdb_id:
                    logger.warning(f"Skipping movie without TMDB ID: {movie.get('title', 'Unknown')}")
                    result['skipped'] += 1
                    continue

                # Get Letterboxd film ID
                film_id = self.get_film_id_from_tmdb(tmdb_id)
                if not film_id:
                    logger.warning(f"Could not find Letterboxd ID for {movie.get('title', 'Unknown')} (TMDB: {tmdb_id})")
                    result['failed'] += 1
                    result['errors'].append(f"No Letterboxd match for {movie.get('title', 'Unknown')}")
                    continue

                # Mark as watched
                watched_date = movie.get('watched_at')
                if isinstance(watched_date, str):
                    watched_date = datetime.fromisoformat(watched_date.replace('Z', '+00:00'))

                rating = movie.get('rating')

                success = self.mark_as_watched(
                    film_id=film_id,
                    watched_date=watched_date,
                    rating=rating,
                    liked=False,  # Could be configurable
                    tags=None  # Could add "trakt-sync" tag
                )

                if success:
                    result['success'] += 1
                    logger.info(f"✓ Uploaded: {movie.get('title', 'Unknown')}")
                else:
                    result['failed'] += 1
                    result['errors'].append(f"Failed to upload {movie.get('title', 'Unknown')}")

            except Exception as e:
                logger.error(f"Error processing movie {movie.get('title', 'Unknown')}: {e}")
                result['failed'] += 1
                result['errors'].append(str(e))

        logger.info(f"Upload complete: {result['success']} successful, {result['failed']} failed, {result['skipped']} skipped")
        return result
