"""
VolGuard 3.3 - Risk Manager
Comprehensive pre-trade risk validation
"""
from typing import Tuple, List, Dict, Optional
from datetime import datetime, date
from config import Config
from utils.logger import logger
from database.repositories import TradeRepository, StateRepository
from core.upstox import UpstoxFetcher


class RiskManager:
    """
    Validate trades against all risk parameters before execution
    """
    
    def __init__(self, db_conn):
        """
        Args:
            db_conn: Database connection
        """
        self.db_conn = db_conn
        self.trade_repo = TradeRepository(db_conn)
        self.state_repo = StateRepository(db_conn)
        self.upstox = UpstoxFetcher()
        
        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None
    
    def validate_trade(
        self,
        mandate: Dict,
        legs: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive pre-trade validation
        
        Args:
            mandate: Trading mandate dictionary
            legs: Strategy legs
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_violations)
        """
        violations = []
        
        logger.info("🔍 Running pre-trade risk checks...")
        
        # 1. Circuit breaker check (critical)
        if self.circuit_breaker_active:
            violations.append(f"Circuit breaker active: {self.circuit_breaker_reason}")
            return False, violations
        
        # 2. Capital allocation check
        ok, msg = self._check_capital_allocation(mandate)
        if not ok:
            violations.append(msg)
        
        # 3. Margin requirements check
        ok, msg = self._check_margin_requirements(legs)
        if not ok:
            violations.append(msg)
        
        # 4. Position concentration check
        ok, msg = self._check_position_concentration(legs)
        if not ok:
            violations.append(msg)
        
        # 5. Daily trade limit check
        ok, msg = self._check_daily_trade_limit()
        if not ok:
            violations.append(msg)
        
        # 6. Drawdown limit check
        ok, msg = self._check_drawdown_limit()
        if not ok:
            violations.append(msg)
        
        # 7. Market conditions check
        ok, msg = self._check_market_conditions()
        if not ok:
            violations.append(msg)
        
        # 8. Veto events check
        ok, msg = self._check_veto_events()
        if not ok:
            violations.append(msg)
        
        # 9. Max capital per trade
        ok, msg = self._check_max_capital_per_trade(mandate)
        if not ok:
            violations.append(msg)
        
        is_valid = len(violations) == 0
        
        if is_valid:
            logger.info("✅ All risk checks passed")
        else:
            logger.warning(f"⚠️ Risk violations: {len(violations)}")
            for v in violations:
                logger.warning(f"   - {v}")
        
        return is_valid, violations
    
    def _check_capital_allocation(self, mandate: Dict) -> Tuple[bool, str]:
        """
        Check if deployment amount is within limits
        
        Args:
            mandate: Trading mandate
            
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        deployment_amount = mandate.get('deployment_amount', 0)
        
        # Check against base capital
        max_allowed = Config.BASE_CAPITAL * Config.MAX_CAPITAL_USAGE
        
        # Get currently deployed capital
        open_trades = self.trade_repo.get_open_trades()
        currently_deployed = sum([t.get('deployment_amount', 0) for t in open_trades])
        
        total_deployed = currently_deployed + deployment_amount
        
        if total_deployed > max_allowed:
            return False, f"Capital allocation exceeded: ₹{total_deployed:,.0f} > ₹{max_allowed:,.0f}"
        
        logger.debug(f"Capital check OK: ₹{total_deployed:,.0f} / ₹{max_allowed:,.0f}")
        return True, "OK"
    
    def _check_margin_requirements(self, legs: List[Dict]) -> Tuple[bool, str]:
        """
        Check if sufficient margin available
        
        Args:
            legs: Strategy legs
            
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            # Calculate required margin
            # For Nifty options, rough estimate:
            # Short options: ~125k per lot
            # Long options: premium amount
            
            required_margin = 0
            
            for leg in legs:
                qty = leg.get('quantity', 0)
                ltp = leg.get('ltp', 0)
                
                if leg['side'] == 'SELL':
                    # Short leg - requires margin
                    required_margin += Config.MARGIN_SELL_BASE * qty
                else:
                    # Long leg - requires premium
                    required_margin += ltp * qty * 25  # lot size
            
            # Get available margin from Upstox
            # Note: This would require Upstox margin API
            # For now, use a simplified check
            
            available_margin = Config.BASE_CAPITAL * Config.MAX_CAPITAL_USAGE
            
            # Use 90% threshold for safety
            if required_margin > available_margin * 0.9:
                return False, f"Insufficient margin: need ₹{required_margin:,.0f}, have ₹{available_margin:,.0f}"
            
            logger.debug(f"Margin check OK: ₹{required_margin:,.0f} / ₹{available_margin:,.0f}")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Margin check error: {e}")
            return False, f"Margin check failed: {str(e)}"
    
    def _check_position_concentration(self, legs: List[Dict]) -> Tuple[bool, str]:
        """
        Check position concentration limits
        
        Args:
            legs: Strategy legs
            
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            # Check max contracts per instrument
            total_qty = sum([leg.get('quantity', 0) for leg in legs])
            
            if total_qty > Config.MAX_CONTRACTS_PER_INSTRUMENT:
                return False, f"Position concentration exceeded: {total_qty} > {Config.MAX_CONTRACTS_PER_INSTRUMENT}"
            
            # Check against existing positions
            # This would require fetching broker positions
            # For now, simplified check
            
            logger.debug(f"Position concentration OK: {total_qty} lots")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Position concentration check error: {e}")
            return False, f"Position check failed: {str(e)}"
    
    def _check_daily_trade_limit(self) -> Tuple[bool, str]:
        """
        Check daily trade limit
        
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            today = date.today()
            
            # Count trades opened today
            today_trades = self.trade_repo.get_trades_by_date(today)
            
            if len(today_trades) >= Config.MAX_TRADES_PER_DAY:
                return False, f"Daily trade limit reached: {len(today_trades)}/{Config.MAX_TRADES_PER_DAY}"
            
            logger.debug(f"Daily trade limit OK: {len(today_trades)}/{Config.MAX_TRADES_PER_DAY}")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Daily trade limit check error: {e}")
            return True, "OK"  # Don't block on error
    
    def _check_drawdown_limit(self) -> Tuple[bool, str]:
        """
        Check drawdown limit
        
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            # Get peak capital
            peak_capital = self._get_peak_capital()
            
            # Get current capital (base + realized P&L - unrealized losses)
            current_capital = self._get_current_capital()
            
            if peak_capital <= 0:
                return True, "OK"
            
            drawdown_pct = (peak_capital - current_capital) / peak_capital
            
            if drawdown_pct > Config.MAX_DRAWDOWN_PCT:
                # Activate circuit breaker
                self.activate_circuit_breaker(f"Drawdown limit exceeded: {drawdown_pct:.1%}")
                return False, f"Drawdown limit exceeded: {drawdown_pct:.1%} > {Config.MAX_DRAWDOWN_PCT:.1%}"
            
            logger.debug(f"Drawdown OK: {drawdown_pct:.1%} / {Config.MAX_DRAWDOWN_PCT:.1%}")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Drawdown check error: {e}")
            return True, "OK"  # Don't block on error
    
    def _check_market_conditions(self) -> Tuple[bool, str]:
        """
        Check market conditions
        
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            # Check if market is open
            now = datetime.now()
            
            # Market hours: 9:15 AM to 3:30 PM IST
            market_open = now.hour >= 9 and (now.hour < 15 or (now.hour == 15 and now.minute <= 30))
            
            if not market_open:
                return False, "Market is closed"
            
            # Check spot price staleness
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            
            if not spot_price:
                return False, "Unable to fetch spot price"
            
            # Additional checks can be added here:
            # - Bid-ask spreads
            # - Volatility spikes
            # - Circuit limits
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Market conditions check error: {e}")
            return True, "OK"  # Don't block on error
    
    def _check_veto_events(self) -> Tuple[bool, str]:
        """
        Check for veto events
        
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        try:
            from core.calendar import CalendarEngine
            
            # Check upcoming events
            calendar_events = CalendarEngine.fetch_calendar(days_ahead=1)
            has_veto, veto_name, square_off_needed, hours_until = CalendarEngine.analyze_veto_risk(calendar_events)
            
            if has_veto and square_off_needed:
                return False, f"Veto event: {veto_name} in {hours_until:.1f}h"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Veto check error: {e}")
            return True, "OK"  # Don't block on error
    
    def _check_max_capital_per_trade(self, mandate: Dict) -> Tuple[bool, str]:
        """
        Check max capital per trade limit
        
        Args:
            mandate: Trading mandate
            
        Returns:
            Tuple[bool, str]: (is_ok, message)
        """
        deployment_amount = mandate.get('deployment_amount', 0)
        
        if deployment_amount > Config.MAX_CAPITAL_PER_TRADE:
            return False, f"Max capital per trade exceeded: ₹{deployment_amount:,.0f} > ₹{Config.MAX_CAPITAL_PER_TRADE:,.0f}"
        
        return True, "OK"
    
    def _get_peak_capital(self) -> float:
        """Get peak capital from database"""
        try:
            peak = self.state_repo.get_state('peak_capital', str(Config.BASE_CAPITAL))
            return float(peak)
        except:
            return Config.BASE_CAPITAL
    
    def _get_current_capital(self) -> float:
        """Calculate current capital"""
        try:
            # Base capital
            current = Config.BASE_CAPITAL
            
            # Add realized P&L
            realized_pnl = self.trade_repo.get_total_realized_pnl()
            current += realized_pnl
            
            # Subtract unrealized losses (open positions)
            open_trades = self.trade_repo.get_open_trades()
            
            for trade in open_trades:
                # Get current P&L
                # This requires position monitor
                current_pnl = trade.get('current_pnl', 0)
                if current_pnl < 0:
                    current += current_pnl  # Add negative (subtract loss)
            
            return current
            
        except Exception as e:
            logger.error(f"Error calculating current capital: {e}")
            return Config.BASE_CAPITAL
    
    def activate_circuit_breaker(self, reason: str):
        """
        Activate circuit breaker to stop all trading
        
        Args:
            reason: Reason for activation
        """
        if not self.circuit_breaker_active:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = reason
            
            logger.critical(f"🚨 CIRCUIT BREAKER ACTIVATED: {reason}")
            
            from utils.telegram import telegram
            telegram.send(
                f"🚨 CIRCUIT BREAKER ACTIVATED\n"
                f"Reason: {reason}\n"
                f"All new trades blocked\n"
                f"Existing positions can be exited",
                "CRITICAL"
            )
            
            # Save to database
            self.state_repo.set_state('circuit_breaker_active', 'true')
            self.state_repo.set_state('circuit_breaker_reason', reason)
            self.state_repo.set_state('circuit_breaker_time', datetime.now().isoformat())
    
    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker"""
        if self.circuit_breaker_active:
            self.circuit_breaker_active = False
            self.circuit_breaker_reason = None
            
            logger.info("✅ Circuit breaker deactivated")
            
            from utils.telegram import telegram
            telegram.send("Circuit breaker deactivated - trading resumed", "SUCCESS")
            
            # Save to database
            self.state_repo.set_state('circuit_breaker_active', 'false')
    
    def is_circuit_breaker_active(self) -> bool:
        """Check if circuit breaker is active"""
        # Check both in-memory and database
        if self.circuit_breaker_active:
            return True
        
        try:
            db_status = self.state_repo.get_state('circuit_breaker_active', 'false')
            return db_status.lower() == 'true'
        except:
            return False
    
    def get_risk_status(self) -> Dict:
        """
        Get current risk status
        
        Returns:
            Dict: Risk metrics
        """
        try:
            peak_capital = self._get_peak_capital()
            current_capital = self._get_current_capital()
            drawdown_pct = (peak_capital - current_capital) / peak_capital if peak_capital > 0 else 0
            
            today_trades = self.trade_repo.get_trades_by_date(date.today())
            open_trades = self.trade_repo.get_open_trades()
            
            return {
                'circuit_breaker_active': self.circuit_breaker_active,
                'circuit_breaker_reason': self.circuit_breaker_reason,
                'peak_capital': peak_capital,
                'current_capital': current_capital,
                'drawdown_pct': drawdown_pct,
                'drawdown_limit': Config.MAX_DRAWDOWN_PCT,
                'today_trades': len(today_trades),
                'max_trades_per_day': Config.MAX_TRADES_PER_DAY,
                'open_positions': len(open_trades)
            }
            
        except Exception as e:
            logger.error(f"Error getting risk status: {e}")
            return {}
