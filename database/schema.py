"""
Database Schema for VolGuard
Simple SQLite schema with WAL mode
"""

SCHEMA_SQL = """
-- System state
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    expiry_type TEXT NOT NULL,
    regime_name TEXT,
    status TEXT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    legs JSON NOT NULL,
    entry_premium REAL,
    current_premium REAL,
    realized_pnl REAL,
    current_pnl REAL,
    max_profit REAL,
    max_loss REAL,
    net_delta REAL,
    net_theta REAL,
    net_gamma REAL,
    net_vega REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Positions table (from open trades)
CREATE TABLE IF NOT EXISTS positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    instrument_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    role TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    delta REAL,
    theta REAL,
    gamma REAL,
    vega REAL,
    pnl REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

-- Analysis history
CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    weekly_mandate JSON,
    monthly_mandate JSON,
    next_weekly_mandate JSON,
    vol_metrics JSON,
    struct_metrics JSON,
    edge_metrics JSON,
    external_metrics JSON,
    veto_events JSON,
    regime_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    trade_id TEXT,
    instrument_key TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    filled_quantity INTEGER DEFAULT 0,
    average_price REAL,
    placed_at TIMESTAMP NOT NULL,
    filled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

-- Performance metrics
CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE PRIMARY KEY,
    trades_count INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    total_pnl REAL,
    max_drawdown REAL,
    realized_pnl REAL,
    unrealized_pnl REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indices
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_positions_trade_id ON positions(trade_id);
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(trade_id);
"""

def init_schema(conn):
    """Initialize database schema"""
    conn.executescript(SCHEMA_SQL)
    # Enable WAL mode
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.commit()
