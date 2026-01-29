"""
Database Schema for VolGuard 3.3
Enhanced schema with all trading logic support
"""

SCHEMA_SQL = """
-- System state (for configuration and flags)
CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trades table (main trade records)
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    expiry_type TEXT NOT NULL,
    expiry_date TEXT,
    regime_name TEXT,
    status TEXT NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    entry_credit REAL,
    current_pnl REAL,
    realized_pnl REAL,
    max_loss REAL,
    max_profit REAL,
    deployment_amount REAL,
    exit_reason TEXT,
    manual_exit_flag INTEGER DEFAULT 0,
    net_delta REAL,
    net_theta REAL,
    net_gamma REAL,
    net_vega REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade legs table (individual options in strategy)
CREATE TABLE IF NOT EXISTS trade_legs (
    leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    order_id TEXT,
    instrument_key TEXT NOT NULL,
    side TEXT NOT NULL,
    option_type TEXT NOT NULL,
    strike INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    filled_qty INTEGER,
    entry_price REAL,
    expected_price REAL,
    current_price REAL,
    slippage_pct REAL,
    fill_time TIMESTAMP,
    role TEXT,
    expiry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

-- Exit legs table (for tracking exit execution)
CREATE TABLE IF NOT EXISTS exit_legs (
    exit_leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    order_id TEXT,
    instrument_key TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    exit_price REAL,
    fill_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

-- Positions table (current open positions)
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
    weekly_mandate TEXT,
    monthly_mandate TEXT,
    next_weekly_mandate TEXT,
    vol_metrics TEXT,
    struct_metrics TEXT,
    edge_metrics TEXT,
    external_metrics TEXT,
    veto_events TEXT,
    regime_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table (all order attempts)
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    trade_id TEXT,
    instrument_key TEXT NOT NULL,
    side TEXT NOT NULL,
    option_type TEXT,
    strike INTEGER,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    filled_quantity INTEGER DEFAULT 0,
    average_price REAL,
    status_message TEXT,
    placed_at TIMESTAMP NOT NULL,
    filled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

-- Performance metrics (daily rollup)
CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE PRIMARY KEY,
    trades_count INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    total_pnl REAL,
    max_drawdown REAL,
    realized_pnl REAL,
    unrealized_pnl REAL,
    capital_deployed REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alerts and notifications log
CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    trade_id TEXT,
    acknowledged INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk events log (drawdowns, circuit breakers, etc.)
CREATE TABLE IF NOT EXISTS risk_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    description TEXT,
    metrics TEXT,
    action_taken TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_expiry ON trades(expiry_date);
CREATE INDEX IF NOT EXISTS idx_legs_trade_id ON trade_legs(trade_id);
CREATE INDEX IF NOT EXISTS idx_legs_instrument ON trade_legs(instrument_key);
CREATE INDEX IF NOT EXISTS idx_positions_trade_id ON positions(trade_id);
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(trade_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp);
"""

def init_schema(conn):
    """
    Initialize database schema
    
    Args:
        conn: SQLite connection
    """
    # Execute schema
    conn.executescript(SCHEMA_SQL)
    
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.execute("PRAGMA temp_store=MEMORY")
    
    conn.commit()
    
    print("✅ Database schema initialized")


def upgrade_schema(conn):
    """
    Upgrade existing schema with new tables/columns
    Useful for migrations
    
    Args:
        conn: SQLite connection
    """
    cursor = conn.cursor()
    
    # Check if trade_legs table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='trade_legs'
    """)
    
    if not cursor.fetchone():
        print("📦 Creating trade_legs table...")
        cursor.execute("""
            CREATE TABLE trade_legs (
                leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                order_id TEXT,
                instrument_key TEXT NOT NULL,
                side TEXT NOT NULL,
                option_type TEXT NOT NULL,
                strike INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                filled_qty INTEGER,
                entry_price REAL,
                expected_price REAL,
                current_price REAL,
                slippage_pct REAL,
                fill_time TIMESTAMP,
                role TEXT,
                expiry TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
            )
        """)
    
    # Check if exit_legs table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='exit_legs'
    """)
    
    if not cursor.fetchone():
        print("📦 Creating exit_legs table...")
        cursor.execute("""
            CREATE TABLE exit_legs (
                exit_leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT NOT NULL,
                order_id TEXT,
                instrument_key TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                exit_price REAL,
                fill_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
            )
        """)
    
    # Add missing columns to trades table
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN entry_credit REAL")
        print("✅ Added entry_credit column")
    except:
        pass  # Column might already exist
    
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN deployment_amount REAL")
        print("✅ Added deployment_amount column")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN exit_reason TEXT")
        print("✅ Added exit_reason column")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN manual_exit_flag INTEGER DEFAULT 0")
        print("✅ Added manual_exit_flag column")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN expiry_date TEXT")
        print("✅ Added expiry_date column")
    except:
        pass
    
    # Check if alerts table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='alerts'
    """)
    
    if not cursor.fetchone():
        print("📦 Creating alerts table...")
        cursor.execute("""
            CREATE TABLE alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                trade_id TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # Check if risk_events table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='risk_events'
    """)
    
    if not cursor.fetchone():
        print("📦 Creating risk_events table...")
        cursor.execute("""
            CREATE TABLE risk_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                metrics TEXT,
                action_taken TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    conn.commit()
    print("✅ Schema upgrade complete")
