"""
VOLGUARD 3.3 - CONFIGURATION
==============================
All original configuration parameters preserved from v3.3
"""
import os
from typing import Optional

class Config:
    """
    Production configuration for VolGuard 3.3
    ALL PARAMETERS PRESERVED FROM ORIGINAL - DO NOT MODIFY
    """
    
    # Environment
    ENVIRONMENT = os.getenv("VG_ENV", "PRODUCTION")
    DRY_RUN_MODE = os.getenv("VG_DRY_RUN", "FALSE").upper() == "TRUE"
    
    # Upstox Credentials
    UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
    UPSTOX_CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
    UPSTOX_CLIENT_SECRET = os.getenv("UPSTOX_CLIENT_SECRET")
    UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
    UPSTOX_REFRESH_TOKEN = os.getenv("UPSTOX_REFRESH_TOKEN")
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # Groq AI
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    
    # Instrument Keys
    NIFTY_KEY = "NSE_INDEX|Nifty 50"
    VIX_KEY = "NSE_INDEX|India VIX"
    
    # Capital Management - PRESERVED FROM ORIGINAL
    BASE_CAPITAL = int(os.getenv("VG_BASE_CAPITAL", "1000000"))
    MARGIN_SELL_BASE = 125000
    MARGIN_BUY_BASE = 30000
    MAX_CAPITAL_USAGE = 0.80
    DAILY_LOSS_LIMIT = 0.03
    MAX_POSITION_SIZE = 0.25
    MAX_LOSS_PER_TRADE = int(os.getenv("VG_MAX_LOSS_PER_TRADE", "50000"))
    MAX_CAPITAL_PER_TRADE = int(os.getenv("VG_MAX_CAPITAL_PER_TRADE", "300000"))
    MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    MAX_DRAWDOWN_PCT = float(os.getenv("VG_MAX_DRAWDOWN_PCT", "0.15"))
    MAX_CONTRACTS_PER_INSTRUMENT = 1800
    PRICE_CHANGE_THRESHOLD = 0.10
    
    # Iron Fly Parameters - PRESERVED
    IRON_FLY_MIN_WING_WIDTH = 100
    IRON_FLY_MAX_WING_WIDTH = 400
    IRON_FLY_WING_DELTA_TARGET = 0.10
    IRON_FLY_ATM_TOLERANCE = 0.02
    
    # Volatility Thresholds - PRESERVED
    HIGH_VOL_IVP = 75.0
    LOW_VOL_IVP = 25.0
    VOV_CRASH_ZSCORE = 2.5
    VOV_WARNING_ZSCORE = 2.0
    VIX_MOMENTUM_BREAKOUT = 5.0
    GARCH_CRASH_VOL = 35.0
    
    # Structure Thresholds - PRESERVED
    GAMMA_DANGER_DTE = 1
    GEX_STICKY_RATIO = 0.03
    SKEW_CRASH_FEAR = 5.0
    SKEW_MELT_UP = -2.0
    
    # Scoring Weights - DYNAMIC (but these are defaults) - PRESERVED
    WEIGHT_VOL = 0.40
    WEIGHT_STRUCT = 0.30
    WEIGHT_EDGE = 0.20
    WEIGHT_RISK = 0.10
    
    # FII Thresholds - PRESERVED
    FII_STRONG_LONG = 50000
    FII_STRONG_SHORT = -50000
    FII_MODERATE = 20000
    
    # Trade Management - PRESERVED
    TARGET_PROFIT_PCT = 0.50
    STOP_LOSS_PCT = 1.0
    MAX_SHORT_DELTA = 0.20
    EXIT_DTE = 1
    
    # Order Execution - PRESERVED
    SLIPPAGE_TOLERANCE = 0.02
    PARTIAL_FILL_TOLERANCE = 0.95
    HEDGE_FILL_TOLERANCE = 0.98
    ORDER_TIMEOUT = 10
    MAX_BID_ASK_SPREAD = 0.05
    POLL_INTERVAL = 0.5
    
    # System Configuration
    ANALYSIS_INTERVAL = 1800  # 30 minutes
    MAX_API_RETRIES = 3
    DASHBOARD_REFRESH_RATE = 1.0
    PRICE_STALENESS_THRESHOLD = 5
    
    # File Paths
    DB_PATH = os.getenv("VG_DB_PATH", "/app/data/volguard.db")
    LOG_DIR = os.getenv("VG_LOG_DIR", "/app/logs")
    
    # Market Hours (IST)
    MARKET_OPEN_TIME = (9, 15)   # 9:15 AM
    MARKET_CLOSE_TIME = (15, 30)  # 3:30 PM
    MORNING_BRIEF_TIME = (8, 45)  # 8:45 AM
    
    # Timezone
    TIMEZONE = "Asia/Kolkata"
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []
        
        # Check required Upstox credentials
        if not cls.UPSTOX_ACCESS_TOKEN and not cls.DRY_RUN_MODE:
            errors.append("UPSTOX_ACCESS_TOKEN is required for live trading")
        
        if not cls.UPSTOX_CLIENT_ID:
            errors.append("UPSTOX_CLIENT_ID is required")
        
        if not cls.UPSTOX_CLIENT_SECRET:
            errors.append("UPSTOX_CLIENT_SECRET is required")
        
        # Check Telegram (optional but recommended)
        if not cls.TELEGRAM_BOT_TOKEN:
            print("⚠️ Warning: TELEGRAM_BOT_TOKEN not set - notifications disabled")
        
        if not cls.TELEGRAM_CHAT_ID:
            print("⚠️ Warning: TELEGRAM_CHAT_ID not set - notifications disabled")
        
        # Check Groq (optional)
        if not cls.GROQ_API_KEY:
            print("⚠️ Warning: GROQ_API_KEY not set - AI briefs disabled")
        
        # Validate numeric parameters
        if cls.BASE_CAPITAL <= 0:
            errors.append("BASE_CAPITAL must be positive")
        
        if not 0 < cls.MAX_CAPITAL_USAGE <= 1:
            errors.append("MAX_CAPITAL_USAGE must be between 0 and 1")
        
        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # Create directories if they don't exist
        os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
        os.makedirs(cls.LOG_DIR, exist_ok=True)
        
        return True

# Timezone helper
def get_timezone():
    """Get configured timezone"""
    import pytz
    return pytz.timezone(Config.TIMEZONE)
