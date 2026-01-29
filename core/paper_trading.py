"""
Paper Trading Engine - SIMULATED EXECUTION FOR TESTING
=======================================================
Test strategies without real money

All logic preserved from P__Py__1_.txt lines 920-994
"""
import threading
import time
from typing import Dict, List, Optional
import numpy as np

from config import Config
from utils.logger import logger


class PaperTradingEngine:
    """
    COMPLETE Paper Trading Engine - PRODUCTION READY
    
    Simulates order execution for testing without risk:
    - Probabilistic fill simulation
    - Realistic slippage modeling
    - Order status tracking
    - Position management
    
    Use with Config.DRY_RUN_MODE = True
    """
    
    def __init__(self):
        """Initialize paper trading engine"""
        self.paper_positions: Dict[str, Dict] = {}
        self.paper_orders: Dict[str, Dict] = {}
        self.order_counter = 0
        self.lock = threading.Lock()
        
        logger.info("📄 Paper Trading Engine initialized")
    
    def place_order(
        self,
        instrument_key: str,
        qty: int,
        side: str,
        order_type: str,
        price: float
    ) -> Optional[str]:
        """
        Simulate order placement
        
        Args:
            instrument_key: Instrument to trade
            qty: Quantity
            side: 'BUY' or 'SELL'
            order_type: 'LIMIT', 'MARKET', etc.
            price: Limit price
            
        Returns:
            Simulated order_id or None if rejected
        """
        with self.lock:
            self.order_counter += 1
            order_id = f"PAPER_{int(time.time())}_{self.order_counter}"
            
            # Simulate probabilistic fill
            if np.random.random() > Config.DRY_RUN_FILL_PROBABILITY:
                logger.info(f"📄 PAPER ORDER REJECTED (simulated): {order_id}")
                
                self.paper_orders[order_id] = {
                    'status': 'rejected',
                    'filled_qty': 0,
                    'avg_price': 0
                }
                
                return order_id
            
            # Simulate slippage (normal distribution)
            slippage = np.random.normal(
                Config.DRY_RUN_SLIPPAGE_MEAN,
                Config.DRY_RUN_SLIPPAGE_STD
            )
            
            # Apply slippage
            if side.upper() == 'BUY':
                fill_price = price * (1 + slippage)  # Buyer pays more
            else:
                fill_price = price * (1 - slippage)  # Seller gets less
            
            fill_price = round(fill_price, 1)
            
            # Store order
            self.paper_orders[order_id] = {
                'status': 'complete',
                'filled_qty': qty,
                'avg_price': fill_price,
                'instrument_key': instrument_key,
                'side': side.upper()
            }
            
            # Update position
            pos_key = f"{instrument_key}_{side.upper()}"
            
            if pos_key not in self.paper_positions:
                self.paper_positions[pos_key] = {
                    'qty': 0,
                    'avg_price': 0,
                    'instrument_key': instrument_key,
                    'side': side.upper()
                }
            
            pos = self.paper_positions[pos_key]
            pos['qty'] += qty
            pos['avg_price'] = fill_price  # Simplified - use latest price
            
            logger.info(
                f"📄 PAPER ORDER FILLED: {side} {qty}x {instrument_key} "
                f"@ {fill_price} (slippage: {slippage*100:.2f}%)"
            )
            
            return order_id
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get simulated order status
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status dict or None
        """
        with self.lock:
            return self.paper_orders.get(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Simulate order cancellation
        
        Args:
            order_id: Order to cancel
            
        Returns:
            True if cancelled, False otherwise
        """
        with self.lock:
            if order_id in self.paper_orders:
                # Only cancel if not already complete
                if self.paper_orders[order_id]['status'] != 'complete':
                    self.paper_orders[order_id]['status'] = 'cancelled'
                    logger.info(f"📄 PAPER ORDER CANCELLED: {order_id}")
                    return True
            
            return False
    
    def get_positions(self) -> List[Dict]:
        """
        Get all simulated positions
        
        Returns:
            List of position dicts
        """
        with self.lock:
            return list(self.paper_positions.values())
    
    def clear_position(self, instrument_key: str, side: str):
        """
        Clear a simulated position
        
        Args:
            instrument_key: Instrument
            side: 'BUY' or 'SELL'
        """
        with self.lock:
            pos_key = f"{instrument_key}_{side.upper()}"
            
            if pos_key in self.paper_positions:
                del self.paper_positions[pos_key]
                logger.info(f"📄 PAPER POSITION CLEARED: {pos_key}")
    
    def clear_all_positions(self):
        """Clear all simulated positions"""
        with self.lock:
            self.paper_positions.clear()
            logger.info("📄 ALL PAPER POSITIONS CLEARED")
    
    def get_portfolio_value(self) -> float:
        """
        Calculate simulated portfolio value
        
        Returns:
            Total portfolio value (very simplified)
        """
        with self.lock:
            total = 0.0
            
            for pos in self.paper_positions.values():
                # Simplified P&L calculation
                # In reality, would need current market prices
                value = pos['qty'] * pos['avg_price']
                
                if pos['side'] == 'SELL':
                    total -= value  # Short position
                else:
                    total += value  # Long position
            
            return total
    
    def reset(self):
        """Reset all simulated state"""
        with self.lock:
            self.paper_positions.clear()
            self.paper_orders.clear()
            self.order_counter = 0
            logger.info("📄 Paper Trading Engine reset")
