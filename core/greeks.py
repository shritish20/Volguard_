"""
VolGuard 3.3 - Live Greeks Manager
CRITICAL: Real-time WebSocket streaming of option Greeks
Lines 1085-1485 from original monolithic code
"""

import threading
import time
import json
from typing import List, Dict, Optional
from datetime import date, datetime
from dataclasses import dataclass
import upstox_client

# Imports needed from other modules
# from config import ProductionConfig
# from models.domain import GreeksData
# from utils.logger import logger
# from utils.telegram import telegram
# from utils.metrics import update_greeks, PROM_REGISTRY


@dataclass
class GreeksData:
    """Real-time option Greeks data"""
    ltp: float = 0.0
    delta: float = 0.0
    theta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0
    oi: float = 0.0
    timestamp: float = 0.0


class LiveGreeksManager:
    """
    Real-time Greeks streaming via Upstox WebSocket V3 (option_greeks mode)
    
    Features:
    - WebSocket streaming with auto-reconnect
    - Real-time Greeks updates (delta, theta, gamma, vega, rho, IV, OI)
    - Portfolio aggregation across all legs
    - Stale data detection (>60 seconds old)
    - Theta/Vega ratio monitoring
    - Risk limit checking (delta, gamma, vega)
    - Prometheus metrics integration
    """
    
    def __init__(self, api_client: upstox_client.ApiClient):
        self.api_client = api_client
        self.ws = None
        self.subscribed_keys = set()
        self.greeks_cache = {}  # instrument_key -> GreeksData
        self.lock = threading.RLock()
        self.running = False
        self.thread = None
        self.connected = False
        self.message_count = 0
        self.last_message_time = time.time()
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
        # Register Prometheus metrics if not already existing
        try:
            from prometheus_client import Gauge
            self.theta_vega_ratio_gauge = Gauge(
                "volguard_theta_vega_ratio_normalized", 
                "Portfolio Theta/Vega ratio (normalized by 1000)",
                ["trade_id"],
                registry=PROM_REGISTRY
            )
            self.ws_connection_status = Gauge(
                "volguard_greeks_ws_connected",
                "WebSocket connection status (1=connected)",
                registry=PROM_REGISTRY
            )
        except Exception as e:
            logger.warning(f"Prometheus metrics registration skipped: {e}")
            self.theta_vega_ratio_gauge = None
            self.ws_connection_status = None
    
    def start(self):
        """Start WebSocket connection in background thread"""
        if self.running:
            logger.debug("LiveGreeksManager already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._ws_loop, daemon=True, name="LiveGreeks-WS")
        self.thread.start()
        logger.info("📡 LiveGreeks Manager started")
    
    def stop(self):
        """Graceful shutdown of WebSocket"""
        logger.info("Shutting down LiveGreeks Manager...")
        self.running = False
        
        if self.ws:
            try:
                self.ws.disconnect()
                logger.debug("WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        if self.ws_connection_status:
            self.ws_connection_status.set(0)
        
        logger.info("📡 LiveGreeks Manager stopped")
    
    def _ws_loop(self):
        """Main connection loop with exponential backoff"""
        while self.running:
            try:
                self._connect()
                # Reset delay on successful connection
                self.reconnect_delay = 1
                
                # Monitor connection health
                while self.running and self.connected:
                    time.sleep(5)
                    # Check for stale data (>30 seconds)
                    if time.time() - self.last_message_time > 30:
                        logger.warning("WebSocket stale (no data for 30s), forcing reconnect")
                        break
                
            except Exception as e:
                logger.error(f"WebSocket loop error: {e}")
                self.connected = False
                if self.ws_connection_status:
                    self.ws_connection_status.set(0)
            
            # Exponential backoff for reconnection
            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _connect(self):
        """Establish WebSocket connection to Upstox"""
        with self.lock:
            keys = list(self.subscribed_keys) if self.subscribed_keys else []
        
        if not keys:
            logger.warning("No instruments to subscribe, skipping connection")
            return
        
        logger.info(f"🔌 Connecting to Option Greeks WebSocket ({len(keys)} instruments)")
        
        try:
            # Initialize WebSocket with option_greeks mode
            self.ws = upstox_client.MarketDataStreamerV3(
                self.api_client, 
                keys, 
                "option_greeks"
            )
            
            # Register callbacks
            self.ws.on("open", self._on_open)
            self.ws.on("message", self._on_message)
            self.ws.on("error", self._on_error)
            self.ws.on("close", self._on_close)
            
            # Connect (blocking call)
            self.ws.connect()
            
            # Keep thread alive while connected
            while self.running and self.connected:
                time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connected = False
            if self.ws_connection_status:
                self.ws_connection_status.set(0)
            raise
    
    def _on_open(self):
        """Handle connection open"""
        logger.info("✅ Live Greeks WebSocket connected")
        self.connected = True
        self.last_message_time = time.time()
        if self.ws_connection_status:
            self.ws_connection_status.set(1)
    
    def _on_message(self, msg):
        """Handle incoming WebSocket message"""
        self.last_message_time = time.time()
        
        try:
            # Parse JSON if string
            if isinstance(msg, str):
                data = json.loads(msg)
            else:
                data = msg
            
            # Skip non-feed messages (market_info, heartbeats)
            if not isinstance(data, dict) or 'feeds' not in data:
                return
            
            self.message_count += 1
            
            # Process each instrument in feeds dictionary
            feeds = data.get('feeds', {})
            for instrument_key, feed_data in feeds.items():
                self._process_instrument(instrument_key, feed_data)
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.debug(f"Message processing error: {e}")
    
    def _process_instrument(self, instrument_key: str, feed_data: dict):
        """
        Parse Greek data from Upstox format.
        
        Upstox structure:
        {
            "firstLevelWithGreeks": {
                "ltpc": {"ltp": 123.45},
                "iv": 18.5,
                "oi": 1234567,
                "optionGreeks": {
                    "delta": 0.52,
                    "theta": -12.5,
                    "gamma": 0.003,
                    "vega": 25.6,
                    "rho": 1.2
                }
            }
        }
        """
        try:
            first_level = feed_data.get('firstLevelWithGreeks', {})
            
            # Extract LTP from ltpc (last traded price container)
            ltpc = first_level.get('ltpc', {})
            ltp = float(ltpc.get('ltp', 0) or 0)
            
            # Extract Greeks from optionGreeks sub-dictionary
            greeks_dict = first_level.get('optionGreeks', {})
            
            # Create data object
            data = GreeksData()
            data.ltp = ltp
            data.delta = float(greeks_dict.get('delta', 0) or 0)
            data.theta = float(greeks_dict.get('theta', 0) or 0)
            data.gamma = float(greeks_dict.get('gamma', 0) or 0)
            data.vega = float(greeks_dict.get('vega', 0) or 0)
            data.rho = float(greeks_dict.get('rho', 0) or 0)
            data.iv = float(first_level.get('iv', 0) or 0)  # IV is in firstLevel, not optionGreeks
            data.oi = float(first_level.get('oi', 0) or 0)
            data.timestamp = time.time()
            
            # Store in cache (thread-safe)
            with self.lock:
                self.greeks_cache[instrument_key] = data
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Data conversion error for {instrument_key}: {e}")
        except Exception as e:
            logger.debug(f"Parse error for {instrument_key}: {e}")
    
    def _on_error(self, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")
        telegram.send(f"⚠️ Greeks WebSocket error: {str(error)[:100]}", "WARNING")
        self.connected = False
        if self.ws_connection_status:
            self.ws_connection_status.set(0)
    
    def _on_close(self):
        """Handle connection close"""
        if self.connected:
            logger.warning("Live Greeks WebSocket disconnected")
        self.connected = False
        if self.ws_connection_status:
            self.ws_connection_status.set(0)
    
    def update_subscriptions(self, instrument_keys: List[str]):
        """
        Dynamically update subscribed instruments.
        Call this when opening new positions or closing existing ones.
        """
        new_keys = set(instrument_keys)
        
        with self.lock:
            if new_keys == self.subscribed_keys:
                return  # No change
            self.subscribed_keys = new_keys
        
        logger.info(f"Updated Greek subscriptions: {len(new_keys)} instruments")
        
        # Force reconnect to update subscriptions
        if self.ws and self.connected:
            logger.debug("Forcing reconnect to update subscriptions")
            try:
                self.ws.disconnect()
            except Exception as e:
                logger.error(f"Error forcing disconnect: {e}")
    
    def get_position_greeks(self, instrument_key: str) -> Optional[GreeksData]:
        """
        Retrieve cached Greeks for specific instrument.
        Returns None if data is stale (>60 seconds old).
        """
        with self.lock:
            data = self.greeks_cache.get(instrument_key)
            if data and (time.time() - data.timestamp) < 60:  # Less than 1 minute old
                return data
            return None
    
    def calculate_position_greeks(self, leg: Dict, trade_id: str) -> Dict[str, float]:
        """
        Calculate notional Greeks for a position leg (quantity-adjusted).
        
        IMPORTANT: 
        - Negative sign for SELL positions
        - Theta is negative for long options, positive for short
        - Vega risk is relevant for option sellers
        """
        live = self.get_position_greeks(leg['key'])
        if not live:
            return {}
        
        qty = leg.get('filled_qty', leg.get('qty', 0))
        side_mult = -1 if leg['side'] == 'SELL' else 1
        
        # Calculate position-level Greeks
        notional = {
            'delta': live.delta * qty * side_mult,
            'theta': live.theta * qty * side_mult,
            'gamma': live.gamma * qty * side_mult,
            'vega': live.vega * qty * side_mult,
            'iv': live.iv,
            'ltp': live.ltp,
            'oi': live.oi
        }
        
        # Calculate Theta/Vega ratio (normalized to 0-10 scale)
        if abs(notional['vega']) > 0.0001:
            raw_ratio = abs(notional['theta']) / abs(notional['vega'])
            notional['theta_vega_ratio'] = raw_ratio / 1000.0  # Normalized
        else:
            notional['theta_vega_ratio'] = 0.0
        
        return notional
    
    def get_portfolio_greeks(self, legs: List[Dict], trade_id: str) -> Dict[str, float]:
        """
        Aggregate Greeks across all legs in a trade/portfolio.
        Also updates Prometheus metrics.
        
        Returns:
        {
            'delta': portfolio delta,
            'theta': portfolio theta (daily decay),
            'gamma': portfolio gamma,
            'vega': portfolio vega (volatility risk),
            'theta_vega_ratio': normalized ratio (higher = better),
            'short_vega_exposure': total vega from short positions,
            'legs_count': number of legs,
            'stale_count': number of legs with stale data
        }
        """
        portfolio = {
            'delta': 0.0,
            'theta': 0.0,
            'gamma': 0.0,
            'vega': 0.0,
            'theta_vega_ratio': 0.0,
            'short_vega_exposure': 0.0,
            'legs_count': len(legs),
            'stale_count': 0
        }
        
        for leg in legs:
            pos = self.calculate_position_greeks(leg, trade_id)
            if not pos:
                portfolio['stale_count'] += 1
                continue
            
            # Aggregate
            portfolio['delta'] += pos['delta']
            portfolio['theta'] += pos['theta']
            portfolio['gamma'] += pos['gamma']
            portfolio['vega'] += pos['vega']
            
            # Track short vega exposure (risk for option sellers)
            if leg['side'] == 'SELL' and pos['vega'] > 0:
                portfolio['short_vega_exposure'] += pos['vega']
        
        # Calculate portfolio Theta/Vega ratio (normalized)
        if abs(portfolio['vega']) > 0.0001:
            raw_ratio = abs(portfolio['theta']) / abs(portfolio['vega'])
            portfolio['theta_vega_ratio'] = raw_ratio / 1000.0
            
            # Update Prometheus metric
            if self.theta_vega_ratio_gauge:
                try:
                    self.theta_vega_ratio_gauge.labels(trade_id=trade_id).set(portfolio['theta_vega_ratio'])
                except Exception as e:
                    logger.debug(f"Prometheus update error: {e}")
        
        # Update global portfolio Greeks metrics
        try:
            update_greeks(
                portfolio['delta'],
                portfolio['theta'],
                portfolio['gamma'],
                portfolio['vega']
            )
        except Exception as e:
            logger.debug(f"Global metrics update error: {e}")
        
        return portfolio
    
    def check_risk_limits(self, legs: List[Dict], trade_id: str) -> List[str]:
        """
        Check risk limits and return list of warnings.
        Call this periodically in RiskManager.monitor().
        
        Checks:
        1. Data freshness (>50% stale = critical)
        2. Theta/Vega ratio (volatility risk vs time income)
        3. Delta exposure (directional risk)
        4. Gamma danger near expiry (<2 DTE)
        """
        warnings = []
        port = self.get_portfolio_greeks(legs, trade_id)
        
        # Check data freshness
        if port['stale_count'] > len(legs) / 2:
            warnings.append(f"⚠️ CRITICAL: {port['stale_count']}/{len(legs)} legs have stale Greeks data")
        
        # Theta/Vega ratio analysis (using normalized values)
        # Good ratio: >2.0 (time decay > 2x volatility risk)
        # Warning: 1.0-2.0 (monitor volatility)
        # Critical: <1.0 (volatility risk exceeds income)
        ratio = port['theta_vega_ratio']
        if ratio > 0:
            if ratio < 1.0:
                msg = f"🔴 CRITICAL θ/ν Ratio: {ratio:.2f} (Volatility risk exceeds time income)"
                warnings.append(msg)
                telegram.send(f"🚨 {trade_id}: {msg}", "CRITICAL")
            elif ratio < 2.0:
                warnings.append(f"🟡 LOW θ/ν Ratio: {ratio:.2f} (Monitor volatility closely)")
            elif ratio > 5.0:
                warnings.append(f"🟢 STRONG θ/ν Ratio: {ratio:.2f} (Excellent time decay)")
            else:
                warnings.append(f"✅ NORMAL θ/ν Ratio: {ratio:.2f}")
        
        # Delta limit check (directional risk)
        max_delta = getattr(ProductionConfig, 'MAX_PORTFOLIO_DELTA', 50)
        if abs(port['delta']) > max_delta:
            warnings.append(f"🔴 DELTA ALERT: {port['delta']:.1f} (Limit: ±{max_delta})")
        
        # Gamma risk near expiry
        if legs:
            # Get expiry from first leg
            expiry = legs[0].get('expiry', date.today())
            if isinstance(expiry, str):
                expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
            days_to_expiry = (expiry - date.today()).days
            
            # Gamma week (0-2 DTE): High gamma = high risk
            if days_to_expiry <= 2 and abs(port['gamma']) > 100:
                msg = f"🔴 GAMMA DANGER: {port['gamma']:.1f} with {days_to_expiry} DTE (Gamma Week)"
                warnings.append(msg)
                telegram.send(msg, "CRITICAL")
        
        return warnings


# ===================================================================
# SINGLETON INSTANCE
# ===================================================================

_live_greeks_instance: Optional[LiveGreeksManager] = None


def get_live_greeks_manager(api_client: upstox_client.ApiClient) -> LiveGreeksManager:
    """
    Get or create singleton instance of LiveGreeksManager.
    Use this function rather than direct instantiation.
    
    Usage:
        greeks_mgr = get_live_greeks_manager(api_client)
        greeks_mgr.start()
        greeks_mgr.update_subscriptions([key1, key2, key3])
        portfolio = greeks_mgr.get_portfolio_greeks(legs, trade_id)
    """
    global _live_greeks_instance
    if _live_greeks_instance is None:
        _live_greeks_instance = LiveGreeksManager(api_client)
    return _live_greeks_instance
