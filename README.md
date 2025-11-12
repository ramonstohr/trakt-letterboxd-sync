# Trakt to Letterboxd Sync

Automatically sync your watched movies from Trakt.tv to Letterboxd. This application runs as a Docker container, perfect for Unraid servers, and provides a web UI for configuration and manual syncing.

## Features

- **Automated Scheduled Syncing**: Set up cron-based schedules to automatically sync your watch history
- **Incremental Syncing**: Only sync movies watched since the last sync
- **Web UI**: Easy-to-use web interface for configuration and manual triggers
- **Docker Support**: Fully containerized for easy deployment on Unraid and other platforms
- **Rating Sync**: Automatically converts Trakt ratings (1-10) to Letterboxd ratings (0.5-5.0)
- **CSV Export**: Generates Letterboxd-compatible CSV files for import
- **OAuth Authentication**: Secure authentication with Trakt.tv API

## Screenshots

The web UI provides:
- Dashboard with sync status and statistics
- Manual sync triggers (incremental and full)
- Scheduler control and monitoring
- Recent export downloads
- Trakt authentication management

## Prerequisites

1. **Trakt.tv Account**: You need a Trakt.tv account with watch history
2. **Trakt API Credentials**: Create an application at https://trakt.tv/oauth/applications
   - Set the Redirect URI to: `urn:ietf:wg:oauth:2.0:oob`
   - Note down your Client ID and Client Secret
3. **Letterboxd Account**: For importing the generated CSV files
4. **Docker**: For running the application

## Quick Start

### 1. Clone or Download

```bash
cd /path/to/your/apps
git clone <repository-url> trakt-letterboxd-sync
cd trakt-letterboxd-sync
```

### 2. Configure

Copy the example configuration file:

```bash
cp config/config.yaml.example config/config.yaml
```

Edit `config/config.yaml` and add your Trakt API credentials:

```yaml
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"
```

### 3. Run with Docker Compose

```bash
docker-compose up -d
```

### 4. Access Web UI

Open your browser and navigate to:
```
http://localhost:5000
```

Default password: `changeme` (change this in the config!)

### 5. Authenticate with Trakt

1. In the web UI, click "Authenticate with Trakt"
2. You'll be redirected to Trakt.tv to authorize the application
3. Copy the PIN code and paste it back in the application
4. Authentication complete!

### 6. Run Your First Sync

Click "Incremental Sync" or "Full Sync" in the web UI. The application will:
1. Fetch your watched movies from Trakt
2. Fetch your ratings
3. Generate a Letterboxd-compatible CSV file
4. Save it to the `data/exports/` directory

### 7. Import to Letterboxd

1. Download the CSV file from the "Recent Exports" section
2. Go to Letterboxd Settings → Import & Export
3. Upload the CSV file
4. Review and import your watch history

## Configuration

### Configuration File (`config/config.yaml`)

```yaml
# Trakt API Configuration
trakt:
  client_id: "YOUR_TRAKT_CLIENT_ID"
  client_secret: "YOUR_TRAKT_CLIENT_SECRET"

# Letterboxd Configuration
letterboxd:
  auto_upload: false  # Future feature for automated upload
  username: ""
  password: ""

# Sync Settings
sync:
  # Cron schedule (default: daily at 2 AM)
  schedule: "0 2 * * *"

  # Optional: Only sync movies watched after this date
  start_date: ""  # Format: YYYY-MM-DD

  # Export paths
  export_path: "/app/data/exports"
  last_sync_file: "/app/data/last_sync.txt"

# Web UI Settings
web:
  host: "0.0.0.0"
  port: 5000
  admin_password: "changeme"  # CHANGE THIS!

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "/app/logs/sync.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5
```

### Cron Schedule Examples

The `schedule` field uses cron syntax:

- `0 2 * * *` - Daily at 2:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight
- `0 0 1 * *` - Monthly on the 1st at midnight

## Unraid Installation

### Method 1: Docker Compose (Recommended)

1. Install the "Compose Manager" plugin from Community Applications
2. Add a new stack with the contents of `docker-compose.yml`
3. Edit the paths to match your Unraid shares
4. Start the stack

### Method 2: Unraid Template

1. Go to Docker tab in Unraid
2. Add Container
3. Configure:
   - **Repository**: Build from source or use your own image
   - **Port**: 5000 → 5000
   - **Path 1**: `/mnt/user/appdata/trakt-letterboxd/config` → `/app/config`
   - **Path 2**: `/mnt/user/appdata/trakt-letterboxd/data` → `/app/data`
   - **Path 3**: `/mnt/user/appdata/trakt-letterboxd/logs` → `/app/logs`
   - **Environment Variables**:
     - `TZ` = Your timezone (e.g., `America/New_York`)

## Usage

### Web UI

The web interface provides all the functionality you need:

1. **Dashboard**: View sync status, last sync time, and connection status
2. **Sync Control**: Trigger incremental or full syncs manually
3. **Scheduler**: Start/stop the automated scheduler
4. **Recent Exports**: Download previously generated CSV files
5. **Authentication**: Manage Trakt API authentication

### API Endpoints

The application also provides REST API endpoints:

- `POST /api/sync` - Trigger a sync
- `GET /api/status` - Get current status
- `GET /api/exports` - List recent exports
- `GET /api/exports/<filename>` - Download a CSV file
- `POST /api/scheduler/toggle` - Start/stop scheduler
- `POST /api/auth/trakt/start` - Start Trakt authentication
- `POST /api/auth/trakt/complete` - Complete Trakt authentication

## How It Works

1. **Fetch from Trakt**: The application uses the Trakt API to fetch your watched movie history and ratings
2. **Convert Ratings**: Trakt's 1-10 rating scale is converted to Letterboxd's 0.5-5.0 scale
3. **Generate CSV**: A Letterboxd-compatible CSV file is created with:
   - Movie title and year
   - IMDb and TMDB IDs for accurate matching
   - Watch dates
   - Converted ratings
4. **Export**: The CSV is saved to the exports directory
5. **Import**: You manually import the CSV to Letterboxd (or use automated upload if configured)

## Incremental vs Full Sync

### Incremental Sync (Recommended)
- Only syncs movies watched since the last sync
- Faster and more efficient
- Ideal for scheduled/automated syncing
- Uses the `last_sync.txt` file to track progress

### Full Sync
- Syncs your entire watch history
- Useful for:
  - First-time setup
  - Recovering from errors
  - Ensuring everything is in sync
- Takes longer but ensures completeness

## Troubleshooting

### "Trakt client not initialized"
- Check that your `client_id` and `client_secret` are correctly set in `config.yaml`
- Restart the container after updating the config

### "Connection test failed"
- Ensure you've completed Trakt authentication
- Check your internet connection
- Verify your Trakt API credentials are valid

### "No movies to sync"
- Check that you have watch history in Trakt.tv
- If using incremental sync, try a full sync
- Verify the `start_date` setting if configured

### Scheduler not running
- Check the cron expression is valid
- Look at logs for error messages: `docker logs trakt-letterboxd-sync`
- Try manually starting the scheduler from the web UI

### CSV import fails on Letterboxd
- Ensure the CSV file is not empty
- Check that movies have at least one identifier (Title, IMDb ID, or TMDB ID)
- Letterboxd has a 1MB file size limit - split large files if needed

## Development

### Running Locally

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp config/config.yaml.example config/config.yaml

# Run
python main.py
```

### Building Docker Image

```bash
docker build -t trakt-letterboxd-sync .
docker run -p 5000:5000 -v ./config:/app/config -v ./data:/app/data trakt-letterboxd-sync
```

## Limitations

- **Letterboxd API**: Letterboxd doesn't have a public API, so CSV import is currently manual
- **Movie Matching**: Movies are matched by IMDb/TMDB IDs or title+year. Very obscure films might not match correctly
- **TV Shows**: This application only syncs movies, not TV shows
- **Rating Scale**: Some precision is lost when converting from Trakt's 10-point scale to Letterboxd's 0.5-increment scale

## Future Features

- Automated CSV upload to Letterboxd (using Selenium/web automation)
- TV show support (if Letterboxd adds it)
- Reverse sync (Letterboxd → Trakt)
- Watchlist syncing
- Custom tag mapping
- Discord/Slack notifications

## Privacy & Security

- Your Trakt credentials are stored locally in the config file
- OAuth tokens are securely exchanged and stored
- No data is sent to third parties
- The web UI is password-protected
- All communication with Trakt uses HTTPS

## License

This project is provided as-is for personal use. Please respect Trakt.tv and Letterboxd's terms of service.

## Support

For issues, questions, or feature requests, please open an issue on the repository.

## Acknowledgments

- [Trakt.tv](https://trakt.tv) for their excellent API
- [Letterboxd](https://letterboxd.com) for being an amazing platform
- The Python `trakt.py` library
- The open-source community

---

**Happy Syncing!**

