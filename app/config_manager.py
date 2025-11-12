"""Configuration management"""
import os
import yaml
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ISO format strings for robust datetime parsing
ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",  # date only without time
)

def parse_dt(value):
    """Parse str|datetime|None and return datetime|None (UTC-aware)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        # Convert 'Z' to %z-compliant format
        s_z = s.replace("Z", "+00:00") if s.endswith("Z") else s
        # Try fromisoformat first
        try:
            dt = datetime.fromisoformat(s_z)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        # Fallback: try known formats
        for fmt in ISO_FORMATS:
            try:
                if fmt.endswith("%z"):
                    dt = datetime.strptime(s_z, fmt)
                else:
                    dt = datetime.strptime(s, fmt)
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    # Unknown format
    return None

def save_dt(path, dt):
    """Save datetime to file in consistent ISO 8601 format with Z."""
    dtu = parse_dt(dt) or datetime.now(timezone.utc)
    # Consistent ISO 8601 with Z
    with open(path, "w", encoding="utf-8") as f:
        f.write(dtu.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"))


class ConfigManager:
    """Manages application configuration"""

    def __init__(self, config_path="config/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._ensure_directories()

    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
                return config
        except FileNotFoundError:
            logger.warning(f"Config file not found at {self.config_path}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()

    def _get_default_config(self):
        """Return default configuration"""
        return {
            'trakt': {
                'client_id': os.getenv('TRAKT_CLIENT_ID', ''),
                'client_secret': os.getenv('TRAKT_CLIENT_SECRET', ''),
                'access_token': '',
                'refresh_token': ''
            },
            'letterboxd': {
                'auto_upload': False,
                'username': os.getenv('LETTERBOXD_USERNAME', ''),
                'password': os.getenv('LETTERBOXD_PASSWORD', '')
            },
            'sync': {
                'schedule': '0 2 * * *',
                'start_date': '',
                'export_path': '/app/data/exports',
                'last_sync_file': '/app/data/last_sync.txt'
            },
            'web': {
                'host': '0.0.0.0',
                'port': 5000,
                'admin_password': 'changeme'
            },
            'logging': {
                'level': 'INFO',
                'file': '/app/logs/sync.log',
                'max_bytes': 10485760,
                'backup_count': 5
            }
        }

    def _ensure_directories(self):
        """Ensure required directories exist"""
        directories = [
            self.config['sync']['export_path'],
            os.path.dirname(self.config['logging']['file']),
            os.path.dirname(self.config['sync']['last_sync_file'])
        ]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def save_config(self):
        """Save configuration to YAML file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False)
                logger.info(f"Configuration saved to {self.config_path}")
                return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def get(self, *keys, default=None):
        """Get nested configuration value"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, *keys, value):
        """Set nested configuration value"""
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()

    def get_last_sync_time(self):
        """Get the last sync timestamp"""
        last_sync_file = self.config['sync']['last_sync_file']
        try:
            if os.path.exists(last_sync_file):
                with open(last_sync_file, 'r', encoding='utf-8') as f:
                    timestamp_str = f.read()
                    dt = parse_dt(timestamp_str)
                    if dt:
                        logger.debug(f"Loaded last sync time: {dt}")
                        return dt
        except Exception as e:
            logger.error(f"Error reading last sync time: {e}")
        return None

    def set_last_sync_time(self, timestamp=None):
        """Set the last sync timestamp"""
        last_sync_file = self.config['sync']['last_sync_file']
        try:
            save_dt(last_sync_file, timestamp or datetime.now(timezone.utc))
            logger.info(f"Last sync time updated: {timestamp or 'now'}")
            return True
        except Exception as e:
            logger.error(f"Error writing last sync time: {e}")
            return False
