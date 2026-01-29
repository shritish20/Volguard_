"""
Portfolio Service - P&L and Greeks calculations
"""
import sqlite3
from typing import Dict, List
from database.repositories import TradeRepository
from core.upstox import UpstoxFetcher
from utils.logger import logger
import json

class PortfolioService:
    """Calculate real-time portfolio metrics"""
    
    def __init__(self, db_conn: sqlite3.Connection):
        self.db_conn = db_conn
        self.trade_repo = TradeRepository(db_conn)
        self.upstox = UpstoxFetcher()
    
    def calculate_live_portfolio(self) -> Dict:
        """Calculate live P&L and Greeks for all open positions"""
        try:
            open_trades = self.trade_repo.get_open_trades()
            
            total_pnl = 0.0
            net_delta = 0.0
            net_theta = 0.0
            net_gamma = 0.0
            net_vega = 0.0
            
            positions = []
            
            for trade_dict in open_trades:
                # Parse legs
                legs = json.loads(trade_dict['legs']) if isinstance(trade_dict['legs'], str) else trade_dict['legs']
                
                trade_pnl = 0.0
                trade_delta = 0.0
                trade_theta = 0.0
                trade_gamma = 0.0
                trade_vega = 0.0
                
                for leg in legs:
                    # Get current LTP
                    ltp = self.upstox.get_ltp(leg['key'])
                    if not ltp:
                        ltp = leg.get('ltp', leg['entry_price'])
                    
                    # Calculate P&L
                    qty = leg['qty']
                    entry = leg['entry_price']
                    
                    if leg['side'].upper() == 'SELL':
                        leg_pnl = (entry - ltp) * qty * 50  # NIFTY lot size = 50
                    else:
                        leg_pnl = (ltp - entry) * qty * 50
                    
                    trade_pnl += leg_pnl
                    
                    # Aggregate Greeks (simplified - would need Black-Scholes)
                    trade_delta += leg.get('delta', 0)
                    trade_theta += leg.get('theta', 0)
                    trade_gamma += leg.get('gamma', 0)
                    trade_vega += leg.get('vega', 0)
                    
                    positions.append({
                        'trade_id': trade_dict['trade_id'],
                        'instrument_key': leg['key'],
                        'symbol': leg['symbol'],
                        'side': leg['side'],
                        'quantity': qty,
                        'entry_price': entry,
                        'ltp': ltp,
                        'pnl': leg_pnl,
                        'pnl_pct': (leg_pnl / (entry * qty * 50) * 100) if entry > 0 else 0
                    })
                
                # Update trade in DB
                self.trade_repo.update_pnl(
                    trade_dict['trade_id'],
                    trade_pnl,
                    {
                        'delta': trade_delta,
                        'theta': trade_theta,
                        'gamma': trade_gamma,
                        'vega': trade_vega
                    }
                )
                
                total_pnl += trade_pnl
                net_delta += trade_delta
                net_theta += trade_theta
                net_gamma += trade_gamma
                net_vega += trade_vega
            
            return {
                'timestamp': None,  # Will be set in WebSocket
                'portfolio': {
                    'total_pnl': total_pnl,
                    'net_delta': net_delta,
                    'net_theta': net_theta,
                    'net_gamma': net_gamma,
                    'net_vega': net_vega,
                    'open_trades_count': len(open_trades)
                },
                'positions': positions
            }
            
        except Exception as e:
            logger.error(f"Portfolio calculation failed: {e}")
            return {
                'portfolio': {
                    'total_pnl': 0,
                    'net_delta': 0,
                    'net_theta': 0,
                    'net_gamma': 0,
                    'net_vega': 0,
                    'open_trades_count': 0
                },
                'positions': []
            }
