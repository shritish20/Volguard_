"""
Circuit Breaker - COMPLETE RISK CONTROL SYSTEM
===============================================
Multi-layer risk protection with automatic trade halting

All logic preserved from P__Py__1_.txt lines 807-916
"""
import os
from datetime import datetime, timedelta, date
from config import Config
from utils.logger import logger
from utils.telegram import telegram
from database.repositories import SystemStateRepository
import sqlite3


class CircuitBreaker:
    """
    COMPLETE Circuit Breaker - PRODUCTION READY
    
    Multi-layer risk protection system that halts trading when limits are breached:
    1. Daily loss limit (3% of capital)
    2. Max drawdown (15% from peak)
    3. Consecutive losses (3 in a row)
    4. Excessive slippage (5+ events per day)
    5. Daily trade limit (3 trades/day)
    6. Kill switch (emergency file)
    
    When triggered:
    - Sets breaker_triggered = True
    - Enters cooldown period (24 hours default)
    - Sends Telegram alerts
    - Logs to database
    - Prevents all new trades
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize circuit breaker
        
        Args:
            db_connection: SQLite database connection for state persistence
        """
        self.db_conn = db_connection
        self.state_repo = SystemStateRepository(db_connection)
        
        # Load persistent state
        self.consecutive_losses = self._load_consecutive_losses()
        self.peak_capital = self._load_peak_capital()
        
        # Runtime state
        self.breaker_triggered = False
        self.breaker_until = None
        self.current_capital = Config.BASE_CAPITAL
        
        # Daily counters (reset each day)
        self.daily_slippage_events = 0
        self.last_reset_date = date.today()
        
        logger.info(
            f"Circuit Breaker initialized: "
            f"ConsecLosses={self.consecutive_losses}, "
            f"PeakCapital=₹{self.peak_capital:,.0f}"
        )
    
    def _load_consecutive_losses(self) -> int:
        """Load consecutive losses from database"""
        try:
            value = self.state_repo.get("consecutive_losses")
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Failed to load consecutive losses: {e}")
            return 0
    
    def _load_peak_capital(self) -> float:
        """Load peak capital from database"""
        try:
            value = self.state_repo.get("peak_capital")
            return float(value) if value else Config.BASE_CAPITAL
        except Exception as e:
            logger.error(f"Failed to load peak capital: {e}")
            return Config.BASE_CAPITAL
    
    def _save_consecutive_losses(self):
        """Save consecutive losses to database"""
        self.state_repo.set("consecutive_losses", str(self.consecutive_losses))
    
    def _save_peak_capital(self):
        """Save peak capital to database"""
        self.state_repo.set("peak_capital", str(self.peak_capital))
    
    def _check_daily_reset(self):
        """Reset daily counters if new day"""
        if date.today() > self.last_reset_date:
            self.daily_slippage_events = 0
            self.last_reset_date = date.today()
            logger.info("Circuit breaker daily counters reset")
    
    def update_capital(self, new_capital: float) -> bool:
        """
        Update current capital and check drawdown
        
        Args:
            new_capital: Current portfolio value
            
        Returns:
            True if within limits, False if breaker triggered
        """
        self.current_capital = new_capital
        
        # Update peak if new high
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
            self._save_peak_capital()
            logger.info(f"New peak capital: ₹{self.peak_capital:,.0f}")
        
        # Calculate drawdown from peak
        drawdown = (self.peak_capital - new_capital) / self.peak_capital
        
        # Check if drawdown exceeds limit
        if drawdown >= Config.MAX_DRAWDOWN_PCT:
            self.trigger_breaker(
                "MAX_DRAWDOWN",
                f"Drawdown: {drawdown*100:.1f}% (Limit: {Config.MAX_DRAWDOWN_PCT*100:.0f}%)"
            )
            return False
        
        return True
    
    def check_daily_trade_limit(self) -> bool:
        """
        Check if daily trade limit is reached
        
        Returns:
            True if can trade, False if limit reached
        """
        try:
            # Query database for today's trade count
            cursor = self.db_conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM trades 
                WHERE DATE(entry_time) = DATE('now')
            """)
            row = cursor.fetchone()
            trades_today = row[0] if row else 0
            
            if trades_today >= Config.MAX_TRADES_PER_DAY:
                logger.warning(
                    f"Daily trade limit reached: {trades_today}/{Config.MAX_TRADES_PER_DAY}"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check daily trade limit: {e}")
            return True  # Allow trading on error (fail-open)
    
    def check_daily_loss_limit(self, current_pnl: float) -> bool:
        """
        Check if daily loss limit is breached
        
        Args:
            current_pnl: Current day's P&L (negative = loss)
            
        Returns:
            True if within limit, False if breaker triggered
        """
        loss_pct = abs(current_pnl) / Config.BASE_CAPITAL
        
        if current_pnl < 0 and loss_pct >= Config.DAILY_LOSS_LIMIT:
            self.trigger_breaker(
                "DAILY_LOSS_LIMIT",
                f"Loss: ₹{current_pnl:,.2f} ({loss_pct*100:.1f}%)"
            )
            return False
        
        return True
    
    def record_slippage_event(self, slippage_pct: float) -> bool:
        """
        Record a slippage event and check if limit exceeded
        
        Args:
            slippage_pct: Slippage as percentage (e.g., 0.02 = 2%)
            
        Returns:
            True if within limit, False if breaker triggered
        """
        self._check_daily_reset()
        
        self.daily_slippage_events += 1
        
        if self.daily_slippage_events >= Config.MAX_SLIPPAGE_EVENTS_PER_DAY:
            self.trigger_breaker(
                "EXCESSIVE_SLIPPAGE",
                f"{self.daily_slippage_events} events today (Limit: {Config.MAX_SLIPPAGE_EVENTS_PER_DAY})"
            )
            return False
        
        return True
    
    def record_trade_result(self, pnl: float) -> bool:
        """
        Record trade result and check consecutive losses
        
        Args:
            pnl: Trade P&L (negative = loss)
            
        Returns:
            True if within limit, False if breaker triggered
        """
        if pnl < 0:
            # Loss - increment counter
            self.consecutive_losses += 1
            self._save_consecutive_losses()
            
            logger.warning(f"Consecutive losses: {self.consecutive_losses}")
            
            # Check if limit reached
            if self.consecutive_losses >= Config.MAX_CONSECUTIVE_LOSSES:
                self.trigger_breaker(
                    "CONSECUTIVE_LOSSES",
                    f"{self.consecutive_losses} losses in a row (Limit: {Config.MAX_CONSECUTIVE_LOSSES})"
                )
                return False
        
        else:
            # Win - reset counter
            if self.consecutive_losses > 0:
                logger.info(
                    f"Winning trade after {self.consecutive_losses} losses - resetting counter"
                )
                self.consecutive_losses = 0
                self._save_consecutive_losses()
        
        return True
    
    def trigger_breaker(self, reason: str, details: str):
        """
        Trigger circuit breaker - HALT ALL TRADING
        
        Args:
            reason: Trigger reason (e.g., "MAX_DRAWDOWN")
            details: Additional details
        """
        self.breaker_triggered = True
        self.breaker_until = datetime.now() + timedelta(seconds=Config.COOL_DOWN_PERIOD)
        
        # Alert via Telegram
        telegram.send(
            f"🔴 *CIRCUIT BREAKER*\n"
            f"{reason}: {details}\n"
            f"Cooldown until: {self.breaker_until.strftime('%Y-%m-%d %H:%M:%S')}",
            "CRITICAL"
        )
        
        # Log to database
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO risk_events (event_type, severity, reason, details, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, ("CIRCUIT_BREAKER", "CRITICAL", reason, details))
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Failed to log risk event: {e}")
        
        logger.critical(f"🔴 CIRCUIT BREAKER: {reason} - {details}")
    
    def is_active(self) -> bool:
        """
        Check if circuit breaker is currently active
        
        Returns:
            True if breaker is active (trading halted)
            False if system is operational
        """
        # Check kill switch file
        if os.path.exists(Config.KILL_SWITCH_FILE):
            logger.critical(f"KILL SWITCH DETECTED: {Config.KILL_SWITCH_FILE}")
            if not self.breaker_triggered:
                self.trigger_breaker("KILL_SWITCH", "Manual emergency stop")
            return True
        
        # Check if in cooldown period
        if self.breaker_triggered and self.breaker_until:
            if datetime.now() > self.breaker_until:
                # Cooldown expired - reset
                logger.info("Circuit breaker cooldown expired - resetting")
                self.breaker_triggered = False
                self.breaker_until = None
                
                telegram.send(
                    "✅ Circuit breaker cooldown expired - system ready",
                    "SYSTEM"
                )
                
                return False
        
        return self.breaker_triggered
    
    def get_status(self) -> dict:
        """
        Get current circuit breaker status
        
        Returns:
            Dict with status information
        """
        return {
            'is_active': self.is_active(),
            'consecutive_losses': self.consecutive_losses,
            'peak_capital': self.peak_capital,
            'current_capital': self.current_capital,
            'drawdown_pct': ((self.peak_capital - self.current_capital) / self.peak_capital * 100) 
                            if self.peak_capital > 0 else 0,
            'daily_slippage_events': self.daily_slippage_events,
            'breaker_until': self.breaker_until.isoformat() if self.breaker_until else None
        }
    
    def reset(self, admin_override: bool = False):
        """
        Reset circuit breaker (USE WITH CAUTION)
        
        Args:
            admin_override: Must be True to reset (safety check)
        """
        if not admin_override:
            logger.error("Circuit breaker reset attempted without admin override")
            return False
        
        logger.warning("🔧 Circuit breaker manually reset by admin")
        
        self.breaker_triggered = False
        self.breaker_until = None
        
        telegram.send(
            "🔧 Circuit breaker manually reset by admin",
            "SYSTEM"
        )
        
        return True
