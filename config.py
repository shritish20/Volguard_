"""
VOLGUARD 3.3 - COMPLETE PRODUCTION CONFIGURATION
=================================================
ALL parameters from original P__Py__1_.txt preserved
"""
import os
import logging
from datetime import time as dtime
import pytz

class Config:
    """Production configuration for VolGuard 3.3 - COMPLETE"""
    
    # =========================================================================
    # ENVIRONMENT
    # =========================================================================
    ENVIRONMENT = os.getenv("VG_ENV", "PRODUCTION")
    DRY_RUN_MODE = os.getenv("VG_DRY_RUN", "FALSE").upper() == "TRUE"
    
    # =========================================================================
    # UPSTOX CREDENTIALS
    # =========================================================================
    UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")
    UPSTOX_CLIENT_ID = os.getenv("UPSTOX_CLIENT_ID")
    UPSTOX_CLIENT_SECRET = os.getenv("UPSTOX_CLIENT_SECRET")
    UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI")
    UPSTOX_REFRESH_TOKEN = os.getenv("UPSTOX_REFRESH_TOKEN")
    
    # =========================================================================
    # TELEGRAM
    # =========================================================================
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # =========================================================================
    # GROQ AI
    # =========================================================================
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    
    # =========================================================================
    # INSTRUMENT KEYS
    # =========================================================================
    NIFTY_KEY = "NSE_INDEX|Nifty 50"
    VIX_KEY = "NSE_INDEX|India VIX"
    
    # =========================================================================
    # CAPITAL MANAGEMENT
    # =========================================================================
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
    MARGIN_BUFFER = 0.20
    
    # =========================================================================
    # IRON FLY PARAMETERS
    # =========================================================================
    IRON_FLY_MIN_WING_WIDTH = 100
    IRON_FLY_MAX_WING_WIDTH = 400
    IRON_FLY_WING_DELTA_TARGET = 0.10
    IRON_FLY_ATM_TOLERANCE = 0.02
    
    # =========================================================================
    # VOLATILITY THRESHOLDS
    # =========================================================================
    HIGH_VOL_IVP = 75.0
    LOW_VOL_IVP = 25.0
    VOV_CRASH_ZSCORE = 2.5
    VOV_WARNING_ZSCORE = 2.0
    VIX_MOMENTUM_BREAKOUT = 5.0
    GARCH_CRASH_VOL = 35.0
    
    # =========================================================================
    # STRUCTURE THRESHOLDS
    # =========================================================================
    GAMMA_DANGER_DTE = 1
    GEX_STICKY_RATIO = 0.03
    SKEW_CRASH_FEAR = 3.0
    SKEW_MELT_UP = -1.0
    
    # =========================================================================
    # SCORING WEIGHTS (Base - Dynamic system adjusts these)
    # =========================================================================
    WEIGHT_VOL = 0.40
    WEIGHT_STRUCT = 0.30
    WEIGHT_EDGE = 0.20
    WEIGHT_RISK = 0.10
    
    # =========================================================================
    # FII THRESHOLDS
    # =========================================================================
    FII_STRONG_LONG = 50000
    FII_STRONG_SHORT = -50000
    FII_MODERATE = 20000
    FII_VERY_HIGH_CONVICTION = 150000
    FII_HIGH_CONVICTION = 80000
    FII_MODERATE_CONVICTION = 40000
    
    # =========================================================================
    # TRADE MANAGEMENT
    # =========================================================================
    TARGET_PROFIT_PCT = 0.50
    STOP_LOSS_PCT = 1.0
    MAX_SHORT_DELTA = 0.20
    EXIT_DTE = 1
    
    # =========================================================================
    # ORDER EXECUTION
    # =========================================================================
    SLIPPAGE_TOLERANCE = 0.02
    PARTIAL_FILL_TOLERANCE = 0.95
    HEDGE_FILL_TOLERANCE = 0.98
    ORDER_TIMEOUT = 10
    MAX_BID_ASK_SPREAD = 0.05
    POLL_INTERVAL = 0.5
    MAX_API_RETRIES = 3
    
    # =========================================================================
    # STRATEGY FACTORY PARAMETERS
    # =========================================================================
    DEFAULT_STRIKE_INTERVAL = 50
    MIN_STRIKE_OI = 1000
    
    # Wing width factors by IVP
    WING_FACTOR_EXTREME_VOL = 1.4
    WING_FACTOR_HIGH_VOL = 1.1
    WING_FACTOR_LOW_VOL = 0.8
    WING_FACTOR_STANDARD = 1.0
    
    # IVP thresholds for wing calculation
    IVP_THRESHOLD_EXTREME = 80.0
    IVP_THRESHOLD_HIGH = 50.0
    IVP_THRESHOLD_LOW = 20.0
    
    MIN_WING_INTERVAL_MULTIPLIER = 2
    
    # Delta targets for strategy construction
    DELTA_SHORT_WEEKLY = 0.20
    DELTA_SHORT_MONTHLY = 0.16
    DELTA_LONG_HEDGE = 0.05
    DELTA_CREDIT_SHORT = 0.30
    DELTA_CREDIT_LONG = 0.10
    
    # Directional bias thresholds
    TREND_BULLISH_THRESHOLD = 0.0
    PCR_BULLISH_THRESHOLD = 1.0
    
    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================
    MAX_CONSECUTIVE_LOSSES = 3
    COOL_DOWN_PERIOD = 86400  # 24 hours
    MAX_SLIPPAGE_EVENTS_PER_DAY = 5
    KILL_SWITCH_FILE = os.getenv("VG_KILL_SWITCH_FILE", "/app/data/KILL_SWITCH")
    
    # =========================================================================
    # LIVE GREEKS CONFIGURATION
    # =========================================================================
    GREEKS_WS_RECONNECT_DELAY = 1
    GREEKS_WS_MAX_RECONNECT_DELAY = 60
    GREEKS_STALE_THRESHOLD = 60
    MAX_PORTFOLIO_DELTA = 50.0
    THETA_VEGA_RATIO_CRITICAL = 1.0
    THETA_VEGA_RATIO_WARNING = 2.0
    MAX_POSITION_GAMMA = 100.0
    
    # =========================================================================
    # SYSTEM CONFIGURATION
    # =========================================================================
    ANALYSIS_INTERVAL = 1800  # 30 minutes
    DASHBOARD_REFRESH_RATE = 1.0
    PRICE_STALENESS_THRESHOLD = 5
    POSITION_RECONCILE_INTERVAL = 300
    ANALYTICS_PROCESS_TIMEOUT = 300
    DB_WRITER_QUEUE_MAX_SIZE = 10000
    HEARTBEAT_INTERVAL = 30
    WEBSOCKET_RECONNECT_DELAY = 5
    MAX_ZOMBIE_PROCESSES = 3
    
    # =========================================================================
    # FILE PATHS
    # =========================================================================
    DB_PATH = os.getenv("VG_DB_PATH", "/app/data/volguard.db")
    LOG_DIR = os.getenv("VG_LOG_DIR", "/app/logs")
    LOG_FILE = os.path.join(LOG_DIR, f"volguard_{ENVIRONMENT.lower()}.log")
    LOG_LEVEL = logging.INFO
    
    # =========================================================================
    # MARKET HOURS (IST)
    # =========================================================================
    MARKET_OPEN = (9, 15)
    MARKET_CLOSE = (15, 30)
    SAFE_ENTRY_START = (9, 0)
    SAFE_EXIT_END = (15, 15)
    MORNING_BRIEF_TIME = (8, 45)
    SQUARE_OFF_TIME_IST = dtime(14, 0)
    
    # =========================================================================
    # TIMEZONE
    # =========================================================================
    IST = pytz.timezone('Asia/Kolkata')
    TIMEZONE = "Asia/Kolkata"
    
    # =========================================================================
    # DRY RUN / PAPER TRADING
    # =========================================================================
    DRY_RUN_SLIPPAGE_MEAN = 0.001
    DRY_RUN_SLIPPAGE_STD = 0.0005
    DRY_RUN_FILL_PROBABILITY = 0.95
    
    # =========================================================================
    # ECONOMIC CALENDAR
    # =========================================================================
    ECONOMIC_CALENDAR_URL = "https://economic-calendar.tradingview.com/events"
    EVENT_RISK_DAYS_AHEAD = 7
    
    VETO_KEYWORDS = [
        "RBI Monetary Policy", "RBI Policy", "Reserve Bank of India",
        "Repo Rate Decision", "MPC Meeting",
        "FOMC", "Federal Reserve Meeting", "Fed Meeting",
        "Federal Funds Rate Decision"
    ]
    
    HIGH_IMPACT_KEYWORDS = [
        "GDP", "Gross Domestic Product",
        "NFP", "Non-Farm Payroll",
        "CPI", "Consumer Price Index",
        "Union Budget", "Budget Speech"
    ]
    
    MEDIUM_IMPACT_KEYWORDS = [
        "PMI", "Manufacturing PMI", "Services PMI",
        "Industrial Production",
        "Retail Sales"
    ]
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []
        
        # Check required Upstox credentials (except in dry run)
        if not cls.DRY_RUN_MODE:
            if not cls.UPSTOX_ACCESS_TOKEN:
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

def get_timezone():
    """Get configured timezone"""
    return Config.IST
