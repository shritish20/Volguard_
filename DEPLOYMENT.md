# VolGuard 3.3 Backend - Deployment Guide

## Complete Production-Ready Backend

This is a **100% production-ready** FastAPI backend with ALL core trading logic preserved from the original VolGuard 3.3.

### ✅ What's Included

**Core Trading Logic (100% Preserved)**
- ✅ Analytics Engine - All volatility metrics (GARCH, Parkinson, VoV, IVP)
- ✅ Regime Engine - Complete scoring system with dynamic weights  
- ✅ Economic Calendar - RBI/Fed veto detection
- ✅ FII/DII Data - Participant position tracking
- ✅ Professional Strategies - Iron Fly, Iron Condor, Credit Spreads
- ✅ All Configuration Parameters - Every threshold preserved

**New Architecture**
- ✅ FastAPI REST API - 15+ endpoints
- ✅ WebSocket - Live P&L updates (1 sec interval)
- ✅ SQLite Database - Simple, no queues
- ✅ Clean Services Layer - Separation of concerns
- ✅ Repository Pattern - Clean data access

**Removed (Over-Engineering)**
- ❌ Prometheus metrics - Tracked in SQLite instead
- ❌ DB writer queue - Direct writes with WAL mode
- ❌ Multiprocessing - Single FastAPI process
- ❌ Complex circuit breaker - Simple flags
- ❌ Process manager - Not needed

## Quick Start

### 1. Prerequisites
```bash
# Python 3.10+ required
python3 --version

# Install virtualenv if needed
pip install virtualenv
```

### 2. Setup Environment
```bash
cd volguard-backend

# Create virtual environment
python3 -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
# Copy example
cp .env.example .env

# Edit with your credentials
nano .env
```

**Required Variables:**
```bash
# Upstox (REQUIRED)
UPSTOX_ACCESS_TOKEN=your_token
UPSTOX_CLIENT_ID=your_client_id
UPSTOX_CLIENT_SECRET=your_secret

# Telegram (OPTIONAL but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Groq AI (OPTIONAL)
GROQ_API_KEY=your_groq_key
```

### 4. Initialize Database
```bash
# Database will auto-initialize on first run
# Location: /app/data/volguard.db (configurable via VG_DB_PATH)

# Create data directory
mkdir -p /app/data /app/logs
```

### 5. Run Development Server
```bash
# Development mode with auto-reload
uvicorn main:app --reload --port 8000

# Access API at:
# http://localhost:8000
# http://localhost:8000/docs (Swagger UI)
```

### 6. Run Production Server
```bash
# Production with Gunicorn (4 workers)
gunicorn main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /app/logs/access.log \
  --error-logfile /app/logs/error.log
```

## API Endpoints

### Analysis
- `POST /api/analysis/run` - Run full market analysis
- `GET /api/analysis/latest` - Get saved analysis results

### Positions & Trades
- `GET /api/positions` - Get all open positions
- `GET /api/trades/history?status=OPEN&days=30` - Get trade history
- `GET /api/trades/{trade_id}` - Get specific trade details

### Portfolio Metrics
- `GET /api/metrics/portfolio` - Get live P&L and Greeks

### WebSocket
- `ws://localhost:8000/ws` - Live updates every 1 second

### System
- `GET /health` - Health check
- `GET /` - API info

## Testing the API

```bash
# 1. Check health
curl http://localhost:8000/health

# 2. Run analysis
curl -X POST http://localhost:8000/api/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'

# 3. Get latest analysis
curl http://localhost:8000/api/analysis/latest

# 4. Get positions
curl http://localhost:8000/api/positions

# 5. Test WebSocket
wscat -c ws://localhost:8000/ws
# or use browser: new WebSocket('ws://localhost:8000/ws')
```

## AWS EC2 Deployment

### Instance Setup
```bash
# 1. Launch EC2 instance (t3.medium or larger recommended)
# 2. SSH into instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# 3. Update system
sudo apt update && sudo apt upgrade -y

# 4. Install Python 3.10+
sudo apt install python3.10 python3.10-venv python3-pip -y

# 5. Clone/upload backend code
# Upload volguard-backend directory via scp or git
```

### Install and Configure
```bash
cd volguard-backend
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
nano .env
# Add all required credentials

# Create directories
sudo mkdir -p /app/data /app/logs
sudo chown ubuntu:ubuntu /app/data /app/logs
```

### Systemd Service (Auto-start on boot)
```bash
sudo nano /etc/systemd/system/volguard.service
```

```ini
[Unit]
Description=VolGuard 3.3 FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/volguard-backend
Environment="PATH=/home/ubuntu/volguard-backend/venv/bin"
ExecStart=/home/ubuntu/volguard-backend/venv/bin/gunicorn main:app \
  -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable volguard
sudo systemctl start volguard

# Check status
sudo systemctl status volguard

# View logs
sudo journalctl -u volguard -f
```

### Nginx Reverse Proxy (Optional)
```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/volguard
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/volguard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Docker Deployment

### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Run application
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  volguard:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    env_file:
      - .env
    restart: unless-stopped
```

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Monitoring

### Logs
```bash
# Application logs
tail -f /app/logs/volguard.log

# Access logs (if using Gunicorn)
tail -f /app/logs/access.log

# Error logs
tail -f /app/logs/error.log

# Systemd logs
sudo journalctl -u volguard -f
```

### Database
```bash
# Connect to database
sqlite3 /app/data/volguard.db

# Check tables
.tables

# View recent trades
SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;

# View system state
SELECT * FROM system_state;
```

## Troubleshooting

### Issue: "Module not found"
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Database locked"
```bash
# Check if another process is using DB
lsof /app/data/volguard.db

# WAL mode should prevent this, but you can reset:
sqlite3 /app/data/volguard.db "PRAGMA journal_mode=DELETE; PRAGMA journal_mode=WAL;"
```

### Issue: "WebSocket not connecting"
```bash
# Check if server is running
curl http://localhost:8000/health

# Test WebSocket with wscat
npm install -g wscat
wscat -c ws://localhost:8000/ws
```

### Issue: "Upstox API errors"
```bash
# Verify token is valid
# Check environment variables
env | grep UPSTOX

# Test token manually
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.upstox.com/v2/user/profile
```

## Backup and Recovery

### Backup Database
```bash
# Daily backup
sqlite3 /app/data/volguard.db ".backup '/app/data/backup_$(date +%Y%m%d).db'"

# Compress
tar -czf volguard_backup_$(date +%Y%m%d).tar.gz \
  /app/data/volguard.db \
  /app/logs/volguard.log
```

### Restore Database
```bash
# Stop service
sudo systemctl stop volguard

# Restore
cp /app/data/backup_20240129.db /app/data/volguard.db

# Start service
sudo systemctl start volguard
```

## Performance Tuning

### Gunicorn Workers
```bash
# Rule of thumb: (2 x CPU cores) + 1
# For 4-core EC2 instance: 9 workers
gunicorn main:app -w 9 -k uvicorn.workers.UvicornWorker
```

### SQLite Optimization
```sql
-- Run periodically to optimize
PRAGMA optimize;
VACUUM;
```

### WebSocket Scaling
For very high concurrent users (>1000), consider:
- Redis pub/sub for WebSocket broadcasting
- Separate WebSocket server process
- Load balancer with sticky sessions

## Security Checklist

- [ ] Keep `.env` file secure (never commit to git)
- [ ] Use HTTPS in production (Let's Encrypt)
- [ ] Restrict EC2 security group (only ports 80, 443, 22)
- [ ] Rotate Upstox tokens regularly
- [ ] Enable UFW firewall
- [ ] Keep dependencies updated
- [ ] Monitor logs for suspicious activity

## Next Steps

1. **Frontend**: Connect React frontend to this API
2. **Monitoring**: Add Grafana/Prometheus if needed
3. **Alerts**: Configure Telegram alerts
4. **Backtesting**: Add historical analysis endpoints
5. **Strategy Builder**: Add custom strategy configuration

## Support

For issues or questions:
1. Check logs: `/app/logs/volguard.log`
2. Review API docs: `http://localhost:8000/docs`
3. Test individual endpoints with `curl`
4. Verify environment variables

---

**Version**: 3.3 Professional Refactored
**Last Updated**: January 29, 2026
