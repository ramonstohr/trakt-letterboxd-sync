"""Letterboxd.com API client for uploading watch history"""
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple
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
        # Realistic browser headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        self.csrf_token = None
        self.logged_in = False

    def _find_csrf_token(self, soup: BeautifulSoup, response: requests.Response) -> Optional[str]:
        """
        Find CSRF token from multiple possible sources

        Args:
            soup: BeautifulSoup parsed HTML
            response: Original response object

        Returns:
            CSRF token string or None
        """
        # 1. Check hidden input fields (common names)
        csrf_names = ['csrfmiddlewaretoken', '_csrf', '__csrf', '_token',
                      'authenticity_token', '__RequestVerificationToken', 'csrf_token']

        for name in csrf_names:
            csrf_input = soup.find('input', {'name': name})
            if csrf_input and csrf_input.get('value'):
                token = csrf_input.get('value')
                logger.debug(f"Found CSRF token in input[name='{name}']: {token[:20]}...")
                return token

        # 2. Check meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta and csrf_meta.get('content'):
            token = csrf_meta.get('content')
            logger.debug(f"Found CSRF token in meta tag: {token[:20]}...")
            return token

        # 3. Check cookies
        if 'csrftoken' in response.cookies:
            token = response.cookies['csrftoken']
            logger.debug(f"Found CSRF token in cookie: {token[:20]}...")
            return token

        if 'csrf_token' in response.cookies:
            token = response.cookies['csrf_token']
            logger.debug(f"Found CSRF token in cookie: {token[:20]}...")
            return token

        logger.warning("Could not find CSRF token in any location")
        return None

    def _parse_login_form(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Parse login form to extract action URL and hidden fields

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Tuple of (form_action_url, hidden_fields_dict)
        """
        # Find the login form
        form = soup.find('form', {'class': lambda x: x and 'login' in x.lower() if x else False})
        if not form:
            # Try generic form with username/password fields
            form = soup.find('form')

        if not form:
            logger.error("Could not find login form on page")
            return None, None

        # Get form action
        action = form.get('action', '/user/login.do')
        if not action.startswith('http'):
            action = self.BASE_URL + action

        logger.debug(f"Form action: {action}")

        # Extract all hidden fields
        hidden_fields = {}
        for hidden in form.find_all('input', type='hidden'):
            name = hidden.get('name')
            value = hidden.get('value', '')
            if name:
                hidden_fields[name] = value
                logger.debug(f"Hidden field: {name} = {value[:50] if value else '(empty)'}...")

        return action, hidden_fields

    def login(self) -> bool:
        """
        Login to Letterboxd using username and password

        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info(f"Logging in to Letterboxd as {self.username}")

            # Step 1: GET login page with proper headers
            sign_in_url = f"{self.BASE_URL}/sign-in/"
            self.session.headers.update({
                'Referer': self.BASE_URL,
            })

            response = self.session.get(sign_in_url, allow_redirects=True)

            if response.status_code != 200:
                logger.error(f"Failed to load login page: {response.status_code}")
                logger.debug(f"Response URL: {response.url}")
                return False

            logger.info(f"Loaded login page successfully (final URL: {response.url})")

            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Check for bot challenge / Turnstile
            if 'turnstile' in response.text.lower() or 'challenge' in response.text.lower():
                logger.error("Bot challenge detected (Cloudflare Turnstile or similar)")
                logger.debug("Page contains anti-bot protection")
                return False

            # Step 2: Find CSRF token
            self.csrf_token = self._find_csrf_token(soup, response)

            if not self.csrf_token:
                logger.error("Could not find CSRF token - dumping page info")
                logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
                logger.debug(f"Forms found: {len(soup.find_all('form'))}")
                # Dump first 500 chars of HTML for debugging
                logger.debug(f"HTML sample: {response.text[:500]}")
                return False

            # Step 3: Parse login form
            form_action, hidden_fields = self._parse_login_form(soup)

            if not form_action:
                logger.error("Could not parse login form")
                return False

            # Step 4: Build login data (merge hidden fields + credentials)
            login_data = hidden_fields.copy()
            login_data.update({
                'username': self.username,
                'password': self.password,
                'authenticationCode': '',  # For 2FA
            })

            # Ensure CSRF token is in the data (might be in hidden fields already)
            if self.csrf_token and '__csrf' not in login_data:
                login_data['__csrf'] = self.csrf_token

            logger.debug(f"Login data keys: {list(login_data.keys())}")

            # Step 5: Submit login with proper headers
            self.session.headers.update({
                'Referer': sign_in_url,
                'Origin': self.BASE_URL,
                'Content-Type': 'application/x-www-form-urlencoded',
            })

            # Add CSRF token to headers if found in meta tag
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta:
                self.session.headers['X-CSRF-Token'] = csrf_meta.get('content')

            response = self.session.post(form_action, data=login_data, allow_redirects=True)

            logger.info(f"Login POST completed: {response.status_code} (final URL: {response.url})")

            # Step 6: Verify login success
            # Check if we're redirected to homepage or profile
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for signed-in indicators
                signed_in_indicators = [
                    soup.find('a', {'class': lambda x: x and 'avatar' in x.lower() if x else False}),
                    soup.find('nav', {'class': lambda x: x and 'signed-in' in x.lower() if x else False}),
                    self.username.lower() in response.text.lower(),
                    'sign out' in response.text.lower(),
                ]

                if any(signed_in_indicators):
                    logger.info("✓ Successfully logged in to Letterboxd")
                    self.logged_in = True

                    # Update CSRF token from new page
                    new_csrf = self._find_csrf_token(soup, response)
                    if new_csrf:
                        self.csrf_token = new_csrf

                    return True
                else:
                    logger.error("Login appeared to succeed but cannot verify signed-in state")
                    logger.debug(f"Checking for error messages...")

                    # Look for error messages
                    error_div = soup.find('div', {'class': lambda x: x and 'error' in x.lower() if x else False})
                    if error_div:
                        logger.error(f"Error message: {error_div.get_text(strip=True)}")

                    return False
            else:
                logger.error(f"Login failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error during login: {e}", exc_info=True)
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
