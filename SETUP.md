# Quick Setup Guide

## Step-by-Step Setup

### 1. Get Trakt API Credentials

1. Go to https://trakt.tv/oauth/applications
2. Click "New Application"
3. Fill in:
   - **Name**: Trakt to Letterboxd Sync
   - **Description**: Personal sync tool
   - **Redirect URI**: `urn:ietf:wg:oauth:2.0:oob`
   - **Permissions**: Check all boxes
4. Click "Save App"
5. Copy your **Client ID** and **Client Secret**

### 2. Configure the Application

1. Copy the example config:
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```

2. Edit `config/config.yaml`:
   ```yaml
   trakt:
     client_id: "paste_your_client_id_here"
     client_secret: "paste_your_client_secret_here"

   web:
     admin_password: "choose_a_secure_password"
   ```

### 3. Start the Application

**Using Docker Compose (Recommended):**
```bash
docker-compose up -d
```

**Using Docker directly:**
```bash
docker build -t trakt-letterboxd-sync .
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --name trakt-letterboxd-sync \
  trakt-letterboxd-sync
```

### 4. Access the Web UI

Open your browser:
```
http://localhost:5000
```

Or if on Unraid:
```
http://YOUR-UNRAID-IP:5000
```

### 5. Authenticate with Trakt

1. Login to the web UI with your admin password
2. Click **"Authenticate with Trakt"**
3. A new window will open - authorize the application
4. Copy the **PIN code** shown
5. Paste it back in the prompt
6. Done! You're authenticated

### 6. Run Your First Sync

1. Click **"Full Sync"** to sync your entire history
2. Wait for it to complete
3. Check the **"Recent Exports"** section
4. Download the CSV file

### 7. Import to Letterboxd

1. Go to Letterboxd
2. Click your avatar → **Settings**
3. Go to **Import & Export**
4. Upload your CSV file
5. Review the import
6. Click **Import**

### 8. Enable Scheduled Syncing

1. In the web UI, click **"Start Scheduler"**
2. By default, it runs daily at 2 AM
3. To change the schedule, edit `config/config.yaml`:
   ```yaml
   sync:
     schedule: "0 2 * * *"  # Change this cron expression
   ```
4. Restart the container

## Unraid Specific Setup

### Option 1: Docker Compose (Recommended)

1. Install **Compose Manager** from Community Applications
2. Create a new stack:
   - Name: `trakt-letterboxd-sync`
   - Compose: Paste contents of `docker-compose.yml`
3. Edit paths:
   ```yaml
   volumes:
     - /mnt/user/appdata/trakt-letterboxd/config:/app/config
     - /mnt/user/appdata/trakt-letterboxd/data:/app/data
     - /mnt/user/appdata/trakt-letterboxd/logs:/app/logs
   ```
4. Start the stack

### Option 2: Unraid Docker Template

1. **Docker** tab → **Add Container**
2. Fill in:
   - **Name**: `trakt-letterboxd-sync`
   - **Repository**: Build your image first
   - **Network Type**: Bridge
   - **Port**: `5000` → `5000`
   - **Path 1**: `/mnt/user/appdata/trakt-letterboxd/config` → `/app/config`
   - **Path 2**: `/mnt/user/appdata/trakt-letterboxd/data` → `/app/data`
   - **Path 3**: `/mnt/user/appdata/trakt-letterboxd/logs` → `/app/logs`
   - **Variable 1**: `TZ` = `America/New_York` (your timezone)
3. Apply

## Common Schedules

Edit the `schedule` in `config/config.yaml`:

```yaml
# Every 6 hours
schedule: "0 */6 * * *"

# Every day at 2 AM
schedule: "0 2 * * *"

# Every Sunday at midnight
schedule: "0 0 * * 0"

# Every hour
schedule: "0 * * * *"

# Twice daily (6 AM and 6 PM)
schedule: "0 6,18 * * *"
```

## Verification Checklist

- [ ] Trakt API credentials configured
- [ ] Admin password changed from default
- [ ] Container running (`docker ps`)
- [ ] Web UI accessible
- [ ] Trakt authentication completed
- [ ] First sync successful
- [ ] CSV file generated
- [ ] CSV imported to Letterboxd
- [ ] Scheduler started (if desired)

## Getting Help

Check logs:
```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f trakt-letterboxd-sync

# Or check the logs directory
tail -f logs/sync.log
```

Common issues are covered in the [README.md](README.md#troubleshooting) troubleshooting section.

## Next Steps

- Set up automated scheduling
- Configure your preferred sync time
- Consider backing up your `config/config.yaml`
- Check exports regularly or set up notifications

---

**You're all set! Enjoy automated syncing!**
