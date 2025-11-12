"""Letterboxd CSV generation and upload"""
import csv
import logging
import os
from datetime import datetime
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class LetterboxdCSV:
    """Generate and manage Letterboxd import CSV files"""

    # Letterboxd CSV columns
    COLUMNS = ['Title', 'Year', 'imdbID', 'tmdbID', 'WatchedDate', 'Rating']

    def __init__(self, export_path='/app/data/exports'):
        self.export_path = export_path
        Path(export_path).mkdir(parents=True, exist_ok=True)

    def generate_csv(self, movies: List[Dict], filename: str = None) -> str:
        """
        Generate Letterboxd CSV from movie data

        Args:
            movies: List of movie dictionaries from Trakt
            filename: Optional custom filename (default: letterboxd_import_YYYYMMDD_HHMMSS.csv)

        Returns:
            Path to generated CSV file
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'letterboxd_import_{timestamp}.csv'

        filepath = os.path.join(self.export_path, filename)

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.COLUMNS)
                writer.writeheader()

                for movie in movies:
                    row = self._format_movie_row(movie)
                    if row:
                        writer.writerow(row)

            logger.info(f"Generated CSV with {len(movies)} movies at {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error generating CSV: {e}")
            raise

    def _format_movie_row(self, movie: Dict) -> Dict:
        """Format a movie dictionary into Letterboxd CSV row"""
        try:
            row = {
                'Title': movie.get('title', ''),
                'Year': movie.get('year', ''),
                'imdbID': movie.get('imdb_id', ''),
                'tmdbID': movie.get('tmdb_id', ''),
                'WatchedDate': self._format_date(movie.get('watched_at')),
                'Rating': self._convert_rating(movie.get('rating'))
            }

            # Letterboxd requires at least one identifier
            if not any([row['imdbID'], row['tmdbID'], row['Title']]):
                logger.warning(f"Skipping movie without identifier: {movie}")
                return None

            return row

        except Exception as e:
            logger.error(f"Error formatting movie row: {e}")
            return None

    def _format_date(self, date_value) -> str:
        """Format date to Letterboxd format (YYYY-MM-DD)"""
        if not date_value:
            return ''

        try:
            if isinstance(date_value, datetime):
                return date_value.strftime('%Y-%m-%d')
            elif isinstance(date_value, str):
                # Try to parse ISO format
                dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            else:
                return str(date_value)
        except Exception as e:
            logger.warning(f"Error formatting date {date_value}: {e}")
            return ''

    def _convert_rating(self, rating) -> str:
        """
        Convert Trakt rating (1-10) to Letterboxd rating (0.5-5.0)

        Args:
            rating: Trakt rating (1-10 scale)

        Returns:
            Letterboxd rating string (0.5-5.0 with 0.5 increments)
        """
        if not rating:
            return ''

        try:
            # Trakt uses 1-10, Letterboxd uses 0.5-5.0
            trakt_rating = float(rating)

            # Convert to 0.5-5.0 scale
            letterboxd_rating = (trakt_rating / 10.0) * 5.0

            # Round to nearest 0.5
            letterboxd_rating = round(letterboxd_rating * 2) / 2

            # Ensure it's within valid range
            letterboxd_rating = max(0.5, min(5.0, letterboxd_rating))

            # Format with one decimal place
            return f"{letterboxd_rating:.1f}"

        except Exception as e:
            logger.warning(f"Error converting rating {rating}: {e}")
            return ''

    def get_recent_exports(self, limit=10) -> List[Dict]:
        """
        Get list of recent CSV exports

        Args:
            limit: Maximum number of exports to return

        Returns:
            List of export info dictionaries
        """
        try:
            exports = []
            for file in Path(self.export_path).glob('letterboxd_import_*.csv'):
                stat = file.stat()
                exports.append({
                    'filename': file.name,
                    'path': str(file),
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })

            # Sort by modified time, most recent first
            exports.sort(key=lambda x: x['modified'], reverse=True)

            return exports[:limit]

        except Exception as e:
            logger.error(f"Error getting recent exports: {e}")
            return []

    def validate_csv(self, filepath: str) -> Dict:
        """
        Validate a Letterboxd CSV file

        Returns:
            Dictionary with validation results
        """
        result = {
            'valid': False,
            'row_count': 0,
            'errors': [],
            'warnings': []
        }

        try:
            with open(filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                # Check for required columns
                if not any(col in reader.fieldnames for col in ['Title', 'imdbID', 'tmdbID']):
                    result['errors'].append("Missing required identifier columns")
                    return result

                # Count rows and check for issues
                for i, row in enumerate(reader, start=2):
                    result['row_count'] += 1

                    # Check if row has at least one identifier
                    if not any([row.get('Title'), row.get('imdbID'), row.get('tmdbID')]):
                        result['warnings'].append(f"Row {i}: No identifier found")

                result['valid'] = len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(f"Error reading CSV: {e}")

        return result
