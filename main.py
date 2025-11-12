"""Main entry point for Trakt to Letterboxd Sync"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config_manager import ConfigManager
from app.sync_manager import SyncManager
from app.scheduler import SyncScheduler
from app.web.app import create_app


def setup_logging(config_manager):
    """Configure logging"""
    log_config = config_manager.config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', '/app/logs/sync.log')
    max_bytes = log_config.get('max_bytes', 10485760)
    backup_count = log_config.get('backup_count', 5)

    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

    logging.info("Logging configured")


def main():
    """Main application entry point"""
    try:
        print("=" * 60)
        print("Trakt to Letterboxd Sync")
        print("=" * 60)

        # Load configuration
        config_path = os.getenv('CONFIG_PATH', 'config/config.yaml')
        print(f"Loading configuration from: {config_path}")
        config_manager = ConfigManager(config_path)

        # Setup logging
        setup_logging(config_manager)
        logger = logging.getLogger(__name__)
        logger.info("Starting Trakt to Letterboxd Sync application")

        # Initialize managers
        logger.info("Initializing sync manager...")
        sync_manager = SyncManager(config_manager)

        logger.info("Initializing scheduler...")
        scheduler = SyncScheduler(sync_manager, config_manager)

        # Start scheduler
        try:
            scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.warning(f"Could not start scheduler: {e}")

        # Create and run Flask app
        logger.info("Starting web interface...")
        app = create_app(config_manager, sync_manager, scheduler)

        web_config = config_manager.config.get('web', {})
        host = web_config.get('host', '0.0.0.0')
        port = web_config.get('port', 5000)

        print("\n" + "=" * 60)
        print(f"Web UI available at: http://{host}:{port}")
        print(f"Default password: changeme")
        print("=" * 60 + "\n")

        app.run(
            host=host,
            port=port,
            debug=False,
            threaded=True
        )

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
