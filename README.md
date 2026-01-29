# VolGuard 3.3 - Backend API

Production-ready FastAPI backend for Option Selling System

## Features
- REST API for market analysis and trade execution
- WebSocket for live P&L and Greeks updates
- Regime-based strategy selection
- Economic calendar integration
- FII/DII participant data
- Comprehensive risk management

## Setup

### 1. Install Dependencies
```bash
cd volguard-backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Run Server
```bash
# Development
uvicorn main:app --reload --port 8000

# Production
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Endpoints

### Analysis
- `POST /api/analysis/run` - Run full market analysis
- `GET /api/analysis/latest` - Get latest analysis results

### Positions
- `GET /api/positions` - Get all open positions
- `POST /api/positions/{position_id}/close` - Close specific position

### Trades
- `GET /api/trades/history` - Get trade history
- `GET /api/trades/{trade_id}` - Get specific trade details

### Orders
- `POST /api/orders/execute` - Execute a trade mandate

### Metrics
- `GET /api/metrics/portfolio` - Get portfolio metrics (P&L, Greeks)

### WebSocket
- `ws://localhost:8000/ws` - Live updates (1 sec interval)

### Health
- `GET /health` - System health check

## Architecture

```
volguard-backend/
├── main.py              # FastAPI app entry point
├── config.py            # Configuration
├── models/
│   ├── domain.py        # Domain models (dataclasses)
│   └── database.py      # Database models
├── core/
│   ├── analytics.py     # Market analytics engine
│   ├── regime.py        # Regime detection & scoring
│   ├── calendar.py      # Economic calendar
│   ├── participant.py   # FII/DII data
│   └── upstox.py        # Broker integration
├── api/
│   ├── routes/          # API route handlers
│   └── websocket.py     # WebSocket handler
├── services/
│   ├── trading_service.py
│   └── portfolio_service.py
├── database/
│   ├── connection.py    # SQLite connection
│   ├── repositories.py  # Data access layer
│   └── schema.py        # Database schema
└── utils/
    ├── logger.py        # Logging setup
    └── telegram.py      # Telegram alerts
```

## Environment Variables

See `.env.example` for all required variables.

## Testing

```bash
# Test analysis endpoint
curl -X POST http://localhost:8000/api/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'

# Test WebSocket
wscat -c ws://localhost:8000/ws
```

## Production Deployment

### Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### AWS EC2
1. Install Python 3.10+
2. Clone repository
3. Install dependencies
4. Configure environment variables
5. Run with systemd or supervisor

## License
Proprietary - All Rights Reserved
