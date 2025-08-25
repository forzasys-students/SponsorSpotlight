# SponsorSpotlight

AI-powered logo detection system for analyzing brand exposure in images and videos.

## Quick Start

### 1. Start the Backend Service
```bash
sudo systemctl start sponsorspotlight
sudo systemctl status sponsorspotlight  # Verify it's running
```

### 2. Start the Web Server
```bash
sudo systemctl start nginx
sudo systemctl status nginx  # Verify it's running
```

### 3. Access the Application
Open your browser and go to: **http://YOUR_SERVER_IP**

## Service Management

**Start services:**
```bash
c
```

**Stop services:**
```bash
sudo systemctl stop sponsorspotlight nginx
```

**Restart services:**
```bash
sudo systemctl restart sponsorspotlight nginx
```

**Check status:**
```bash
sudo systemctl status sponsorspotlight nginx
```

**Enable auto-start on boot:**
```bash
sudo systemctl enable sponsorspotlight nginx
```

## Troubleshooting

**If you get 502 Bad Gateway:**
1. Check if Gunicorn is running: `sudo systemctl status sponsorspotlight`
2. Check if Nginx is running: `sudo systemctl status nginx`
3. Restart both services: `sudo systemctl restart sponsorspotlight nginx`

**View logs:**
```bash
sudo journalctl -u sponsorspotlight -f  # Gunicorn logs
sudo tail -f /var/log/nginx/error.log  # Nginx error logs
```

## Architecture

- **Backend**: Flask app running on Gunicorn (port 8000)
- **Frontend**: Nginx serving static files and proxying to Gunicorn
- **AI Model**: YOLO-based logo detection
- **Video Processing**: OpenCV with H.264 codec support


