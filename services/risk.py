"""
VolGuard 3.3 - Risk Service Integration Wrapper
Combines all risk components into single interface
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime, date
from dataclasses import dataclass

# Imports from other modules
# from config import ProductionConfig
# from core.risk import CircuitBreaker
# from core.validation import InstrumentValidator
# from core.greeks import LiveGreeksManager
# from utils.logger import logger
# from utils.telegram import telegram
# from utils.database import db_writer


@dataclass
class RiskCheckResult:
    """Result of pre-flight risk checks"""
    passed: bool
    failures: List[str]
    warnings: List[str]
    

class RiskService:
    """
    Unified risk management service.
    Coordinates all risk components for pre-flight checks.
    
    Components:
    - CircuitBreaker: Daily limits, drawdown, consecutive losses
    - InstrumentValidator: Ban list, lot size, contract validation
    - LiveGreeksManager: Portfolio Greeks risk limits
    - Pre-flight checks: Max loss, position size, concentration
    """
    
    def __init__(
        self, 
        circuit_breaker,  # CircuitBreaker instance
        validator,        # InstrumentValidator instance
        greeks_manager    # LiveGreeksManager instance (optional)
    ):
        self.circuit_breaker = circuit_breaker
        self.validator = validator
        self.greeks_manager = greeks_manager
    
    def pre_flight_check(
        self, 
        legs: List[Dict], 
        capital: float,
        existing_positions: Optional[List[Dict]] = None
    ) -> RiskCheckResult:
        """
        Complete pre-flight risk check before trade execution.
        
        Args:
            legs: Strategy legs to execute
            capital: Available capital
            existing_positions: Currently open positions (for concentration check)
        
        Returns:
            RiskCheckResult with passed/failed status and messages
        """
        failures = []
        warnings = []
        
        # ===== CIRCUIT BREAKER CHECKS =====
        if self.circuit_breaker.is_active():
            status = self.circuit_breaker.get_status()
            failures.append(f"Circuit breaker active: {status.get('reason', 'Unknown')}")
            return RiskCheckResult(passed=False, failures=failures, warnings=warnings)
        
        # Check daily trade limit
        can_trade, msg = self.circuit_breaker.check_daily_trade_limit()
        if not can_trade:
            failures.append(f"Trade limit: {msg}")
        
        # ===== POSITION SIZE CHECKS =====
        total_qty = sum(l['qty'] for l in legs)
        if total_qty > ProductionConfig.MAX_CONTRACTS_PER_INSTRUMENT:
            failures.append(
                f"Position size {total_qty} exceeds limit {ProductionConfig.MAX_CONTRACTS_PER_INSTRUMENT}"
            )
        
        # ===== MAX LOSS CALCULATION =====
        if len(legs) >= 4:  # Multi-leg strategy
            strikes = sorted([l['strike'] for l in legs])
            max_spread_width = max(strikes) - min(strikes)
            premium = sum(l['ltp'] * l['qty'] for l in legs if l['side'] == 'SELL')
            max_loss = (max_spread_width - premium) * legs[0]['qty']
            
            if max_loss > ProductionConfig.MAX_LOSS_PER_TRADE:
                failures.append(
                    f"Max loss ₹{max_loss:,.0f} exceeds limit ₹{ProductionConfig.MAX_LOSS_PER_TRADE:,.0f}"
                )
            
            # Check as percentage of capital
            loss_pct = (max_loss / capital * 100) if capital > 0 else 0
            if loss_pct > 5:  # >5% of capital at risk
                warnings.append(
                    f"Max loss is {loss_pct:.1f}% of capital (₹{max_loss:,.0f})"
                )
        
        # ===== INSTRUMENT VALIDATION =====
        for leg in legs:
            # Check ban list
            if self.validator.is_instrument_banned(leg['key']):
                failures.append(f"Instrument banned: {leg['key']}")
            
            # Validate contract exists
            if not self.validator.validate_contract_exists(leg['key']):
                failures.append(f"Contract does not exist: {leg['key']}")
        
        # Validate lot size
        lot_size = legs[0]['qty'] // 25 if legs else 25
        if not self.validator.validate_lot_size(ProductionConfig.NIFTY_KEY, lot_size):
            failures.append(f"Invalid lot size: {lot_size}")
        
        # ===== CONCENTRATION RISK =====
        if existing_positions:
            # Count positions with same expiry
            new_expiry = legs[0].get('expiry') if legs else None
            same_expiry_count = sum(
                1 for pos in existing_positions 
                if pos.get('expiry') == new_expiry
            )
            
            if same_expiry_count >= 3:
                warnings.append(
                    f"Concentration risk: {same_expiry_count} positions on same expiry"
                )
        
        # ===== GREEKS RISK (if available) =====
        if self.greeks_manager and existing_positions:
            try:
                portfolio = self.greeks_manager.get_portfolio_greeks(
                    existing_positions, 
                    trade_id="PRE_FLIGHT"
                )
                
                # Check delta exposure
                if abs(portfolio['delta']) > 50:
                    warnings.append(
                        f"Existing delta exposure: {portfolio['delta']:.1f}"
                    )
                
                # Check theta/vega ratio
                if portfolio['theta_vega_ratio'] < 1.0:
                    warnings.append(
                        f"Portfolio θ/ν ratio: {portfolio['theta_vega_ratio']:.2f} (volatility risk high)"
                    )
            except Exception as e:
                logger.debug(f"Greeks check failed: {e}")
        
        # ===== FINAL DECISION =====
        passed = len(failures) == 0
        
        if not passed:
            logger.error(f"Pre-flight check FAILED: {len(failures)} failures")
            for failure in failures:
                logger.error(f"  - {failure}")
        
        if warnings:
            logger.warning(f"Pre-flight check has {len(warnings)} warnings")
            for warning in warnings:
                logger.warning(f"  - {warning}")
        
        return RiskCheckResult(
            passed=passed,
            failures=failures,
            warnings=warnings
        )
    
    def post_trade_update(
        self, 
        success: bool, 
        pnl: float,
        capital: float,
        slippage_events: int = 0
    ):
        """
        Update risk state after trade execution.
        
        Args:
            success: Whether trade was profitable
            pnl: Profit/loss amount
            capital: Current capital
            slippage_events: Number of slippage events
        """
        # Update circuit breaker
        self.circuit_breaker.update_capital(capital)
        self.circuit_breaker.record_trade_result(success)
        
        # Check daily loss limit
        if pnl < 0:
            can_continue, msg = self.circuit_breaker.check_daily_loss_limit(abs(pnl))
            if not can_continue:
                logger.critical(f"Daily loss limit triggered: {msg}")
                telegram.send(f"🚨 {msg}", "CRITICAL")
        
        # Record slippage events
        for _ in range(slippage_events):
            self.circuit_breaker.record_slippage_event(0.01)  # Dummy value
    
    def emergency_exit_check(self, portfolio_value: float, peak_value: float) -> Tuple[bool, str]:
        """
        Check if emergency exit is required.
        
        Args:
            portfolio_value: Current portfolio value
            peak_value: Peak portfolio value
        
        Returns:
            (should_exit, reason)
        """
        # Drawdown check
        drawdown = (peak_value - portfolio_value) / peak_value if peak_value > 0 else 0
        
        if drawdown > ProductionConfig.MAX_DRAWDOWN_PCT:
            return (
                True, 
                f"Drawdown {drawdown*100:.1f}% exceeds limit {ProductionConfig.MAX_DRAWDOWN_PCT*100:.1f}%"
            )
        
        # Circuit breaker check
        if self.circuit_breaker.is_active():
            status = self.circuit_breaker.get_status()
            return (True, f"Circuit breaker: {status.get('reason', 'Unknown')}")
        
        return (False, "")
    
    def get_risk_summary(self) -> Dict:
        """
        Get current risk state summary for monitoring.
        
        Returns:
            {
                'circuit_breaker_active': bool,
                'daily_trades': int,
                'consecutive_losses': int,
                'peak_capital': float,
                'current_drawdown_pct': float,
                'can_trade': bool
            }
        """
        status = self.circuit_breaker.get_status()
        
        return {
            'circuit_breaker_active': status.get('active', False),
            'daily_trades': status.get('daily_trades', 0),
            'consecutive_losses': status.get('consecutive_losses', 0),
            'peak_capital': status.get('peak_capital', 0),
            'current_drawdown_pct': status.get('current_drawdown_pct', 0),
            'can_trade': not status.get('active', False),
            'reason': status.get('reason', '')
        }


# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def create_risk_service(
    circuit_breaker,
    validator, 
    greeks_manager=None
) -> RiskService:
    """
    Factory function to create RiskService instance.
    
    Usage:
        risk_service = create_risk_service(
            circuit_breaker=CircuitBreaker(),
            validator=InstrumentValidator(api_client),
            greeks_manager=get_live_greeks_manager(api_client)
        )
    """
    return RiskService(circuit_breaker, validator, greeks_manager)
