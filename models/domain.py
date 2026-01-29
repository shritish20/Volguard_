"""
Domain Models for VolGuard 3.3
All @dataclass models from original code - PRESERVED
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, date

@dataclass
class VolMetrics:
    """Volatility metrics"""
    spot_price: float
    vix: float
    vix_change_pct: float
    iv_percentile: float
    iv_rank: float
    historical_vol_20d: float
    garch_forecast: float
    parkinson_vol: float
    vov: float
    vov_zscore: float
    vix_term_structure_slope: float
    vix_momentum: Optional[float] = None

@dataclass
class StructMetrics:
    """Market structure metrics"""
    gamma_exposure: float
    gex_sticky_level: float
    put_call_ratio: float
    skew_25delta: float
    max_pain: float
    atm_iv: float

@dataclass
class EdgeMetrics:
    """Edge and opportunity metrics"""
    vrp: float
    term_structure_edge: float
    smart_expiry_weekly: Optional[str] = None
    smart_expiry_monthly: Optional[str] = None
    weekly_dte: Optional[int] = None
    monthly_dte: Optional[int] = None

@dataclass
class ExternalMetrics:
    """External market metrics"""
    fii_net: float
    fii_context: str
    dii_net: float

@dataclass
class Score:
    """Composite scoring"""
    vol_score: float
    struct_score: float
    edge_score: float
    risk_score: float
    composite: float
    confidence: str
    score_stability: float
    vol_drivers: List[str] = field(default_factory=list)
    struct_drivers: List[str] = field(default_factory=list)
    edge_drivers: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

@dataclass
class TradingMandate:
    """Trading recommendation with full context"""
    expiry_type: str
    regime_name: str
    suggested_structure: str
    directional_bias: str
    allocation_pct: float
    deployment_amount: float
    max_lots: int
    score: Score
    rationale: List[str]
    warnings: List[str]
    veto_reasons: List[str]
    dynamic_weights: Dict[str, float]
    metrics_snapshot: Dict[str, Any]

@dataclass
class EconomicEvent:
    """Economic calendar event"""
    title: str
    country: str
    event_date: datetime
    impact_level: str
    event_type: str
    forecast: str
    previous: str
    days_until: int
    hours_until: float
    is_veto_event: bool
    suggested_square_off_time: Optional[datetime]

@dataclass
class TradeLegs:
    """Trade leg information"""
    key: str
    symbol: str
    side: str
    role: str
    qty: int
    entry_price: float
    ltp: float
    delta: float
    theta: float
    gamma: float
    vega: float

@dataclass
class Trade:
    """Trade record"""
    trade_id: str
    strategy: str
    expiry_type: str
    status: str
    entry_time: datetime
    legs: List[Dict]
    current_pnl: float
    net_delta: float
    net_theta: float
    net_gamma: float
    net_vega: float
