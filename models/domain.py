"""
Domain Models for VolGuard 3.3 - COMPLETE VERSION
All @dataclass models from original code - FULLY PRESERVED
NOT THE SIMPLIFIED MVP VERSION
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date

@dataclass
class VolMetrics:
    """
    Complete volatility metrics - ALL FIELDS FROM ORIGINAL
    """
    # Current prices
    spot_price: float
    vix: float
    
    # Realized Volatility (multiple windows)
    rv7: float  # 7-day realized vol
    rv28: float  # 28-day realized vol
    rv90: float  # 90-day realized vol
    
    # GARCH Forecasts
    garch7: float  # 7-day GARCH forecast
    garch28: float  # 28-day GARCH forecast
    
    # Parkinson Volatility (high-low range estimator)
    parkinson7: float
    parkinson28: float
    
    # Vol-of-Vol metrics
    vov: float  # Volatility of VIX
    vov_zscore: float  # How many std devs from mean
    
    # IV Percentile (multiple windows)
    ivp_30d: float  # 30-day IV percentile
    ivp_90d: float  # 90-day IV percentile
    ivp_1yr: float  # 1-year IV percentile
    
    # Trend metrics
    ma20: float  # 20-day moving average
    atr14: float  # 14-day Average True Range
    trend_strength: float  # Distance from MA / ATR
    
    # Classifications
    vol_regime: str  # EXPLODING, RICH, CHEAP, FAIR
    is_fallback: bool  # True if using historical data instead of live
    
    # VIX momentum
    vix_change_5d: float  # VIX change over 5 days
    vix_momentum: str  # EXPLOSIVE_UP, RISING, STABLE, FALLING, COLLAPSING

@dataclass
class StructMetrics:
    """
    Complete market structure metrics - ALL FIELDS FROM ORIGINAL
    """
    # Gamma Exposure
    gamma_exposure: float  # Net gamma exposure
    gex_sticky_level: float  # Strike with max GEX concentration
    gex_ratio: float  # GEX / Spot²
    gex_regime: str  # STICKY or SLIPPERY
    
    # Put-Call Ratios
    pcr: float  # Total put/call ratio
    pcr_atm: float  # ATM put/call ratio
    
    # Volatility Skew
    skew_25delta: float  # 25Δ Put IV - 25Δ Call IV
    skew_regime: str  # CRASH_FEAR, BALANCED, MELT_UP
    
    # Other metrics
    max_pain: float  # Max pain strike level
    atm_iv: float  # ATM implied volatility
    lot_size: int  # Contract lot size

@dataclass
class EdgeMetrics:
    """
    Complete edge and opportunity metrics - ALL FIELDS FROM ORIGINAL
    """
    # Volatility Risk Premium
    vrp: float  # Implied - Realized volatility
    
    # Weighted VRP by expiry (accounts for DTE decay)
    weighted_vrp_weekly: float
    weighted_vrp_monthly: float
    weighted_vrp_next_weekly: float
    
    # Term structure
    term_structure_edge: float  # Near-term vs far-term vol difference
    
    # Smart expiry selection
    smart_expiry_weekly: Optional[str] = None
    smart_expiry_monthly: Optional[str] = None
    
    # DTE tracking
    weekly_dte: Optional[int] = None
    monthly_dte: Optional[int] = None

@dataclass
class ExternalMetrics:
    """
    External market metrics - ALL FIELDS FROM ORIGINAL
    """
    # FII/DII positioning
    fii_net: float  # Net FII position in contracts
    fii_context: str  # Strong Long, Strong Short, Moderate, Neutral
    dii_net: float  # Net DII position in contracts
    
    # FII direction classification
    fii_direction: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    
    # High impact events
    high_impact_events: List[Any] = field(default_factory=list)
    
    # Veto event tracking
    veto_event_name: Optional[str] = None
    veto_hours_until: float = 999.0
    veto_square_off_needed: bool = False

@dataclass
class DynamicWeights:
    """
    Dynamic weighting system - FROM ORIGINAL
    """
    vol_weight: float
    struct_weight: float
    edge_weight: float
    risk_weight: float
    rationale: str  # Explanation of why these weights

@dataclass
class Score:
    """
    Complete composite scoring - ALL FIELDS FROM ORIGINAL
    """
    # Individual scores (0-10 scale)
    vol_score: float
    struct_score: float
    edge_score: float
    risk_score: float
    
    # Composite score (weighted average)
    composite: float
    
    # Confidence level
    confidence: str  # VERY_HIGH, HIGH, MODERATE, LOW
    
    # Score stability (how much composite changes with different weights)
    score_stability: float  # 0-1, higher = more stable
    
    # Dynamic weights used
    weights_used: DynamicWeights
    
    # Detailed drivers (list of strings explaining each component)
    score_drivers: List[str] = field(default_factory=list)

@dataclass
class TradingMandate:
    """
    Complete trading recommendation with full context - ALL FIELDS FROM ORIGINAL
    """
    expiry_type: str  # WEEKLY, MONTHLY, NEXT_WEEKLY
    regime_name: str  # VOL_SPIKE, HIGH_VOL, LOW_VOL, NORMAL, etc.
    suggested_structure: str  # IRON_FLY, IRON_CONDOR, CREDIT_SPREAD, etc.
    directional_bias: str  # BULLISH, BEARISH, NEUTRAL
    
    # Allocation
    allocation_pct: float  # Percentage of capital to deploy
    deployment_amount: float  # Actual rupees to deploy
    max_lots: int  # Maximum number of lots
    
    # Scoring details
    score: Score
    
    # Explanations
    rationale: List[str]  # Why this mandate
    warnings: List[str]  # Risk warnings
    veto_reasons: List[str]  # Why trade might be blocked
    
    # Technical details
    dynamic_weights: DynamicWeights
    metrics_snapshot: Dict[str, Any]  # Snapshot of all metrics
    
    # Trade execution details (optional)
    dte: int = 0
    expiry_date: Optional[date] = None
    is_trade_allowed: bool = True
    square_off_instruction: Optional[str] = None
    data_relevance: str = "CURRENT"
    wing_protection: str = "NONE"
    strategy_type: str = "NONE"

@dataclass
class EconomicEvent:
    """
    Economic calendar event - FROM ORIGINAL
    """
    title: str
    country: str
    event_date: datetime
    impact_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    event_type: str  # VETO, HIGH_IMPACT, MEDIUM_IMPACT, LOW_IMPACT
    forecast: str
    previous: str
    days_until: int
    hours_until: float
    is_veto_event: bool
    suggested_square_off_time: Optional[datetime]

@dataclass
class TradeLegs:
    """
    Trade leg information - FROM ORIGINAL
    """
    key: str  # Instrument key
    symbol: str
    side: str  # BUY or SELL
    role: str  # CORE or HEDGE
    qty: int
    entry_price: float
    ltp: float
    delta: float
    theta: float
    gamma: float
    vega: float
    type: str  # CE or PE
    strike: float

@dataclass
class Trade:
    """
    Complete trade record - FROM ORIGINAL
    """
    trade_id: str
    strategy: str  # IRON_FLY, IRON_CONDOR, etc.
    expiry_type: str  # WEEKLY, MONTHLY
    status: str  # OPEN, CLOSED, REJECTED
    entry_time: datetime
    exit_time: Optional[datetime] = None
    
    # Trade legs
    legs: List[Dict] = field(default_factory=list)
    
    # P&L tracking
    entry_premium: float = 0.0
    current_premium: float = 0.0
    realized_pnl: float = 0.0
    current_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    
    # Greeks
    net_delta: float = 0.0
    net_theta: float = 0.0
    net_gamma: float = 0.0
    net_vega: float = 0.0
    
    # Metadata
    regime_name: Optional[str] = None
    mandate_snapshot: Optional[Dict] = None

@dataclass
class TimeMetrics:
    """
    Time-based metrics - FROM ORIGINAL
    """
    current_date: date
    weekly_exp: Optional[date]
    monthly_exp: Optional[date]
    next_weekly_exp: Optional[date]
    
    dte_weekly: int
    dte_monthly: int
    dte_next_weekly: int
    
    is_expiry_day_weekly: bool
    is_expiry_day_monthly: bool
    is_past_square_off_time: bool
    is_gamma_week: bool
    is_gamma_month: bool
    days_to_next_weekly: int

@dataclass
class ParticipantData:
    """
    FII/DII participant data - FROM ORIGINAL
    """
    fut_long: float
    fut_short: float
    fut_net: float
    call_long: float
    call_short: float
    call_net: float
    put_long: float
    put_short: float
    put_net: float
    stock_net: float

@dataclass
class GreeksData:
    """
    Option Greeks container - FROM ORIGINAL
    """
    delta: float = 0.0
    theta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0
    ltp: float = 0.0
    oi: float = 0.0
    timestamp: float = 0.0

@dataclass
class RegimeScore:
    """
    Complete regime scoring - FROM ORIGINAL
    Used in v3.3 scoring system
    """
    vol_score: float
    struct_score: float
    edge_score: float
    composite: float
    confidence: str
    score_stability: float
    weights_used: DynamicWeights
    score_drivers: List[str]
