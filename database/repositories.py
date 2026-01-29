"""
Data Access Layer - Repository Pattern
Simple CRUD operations for all entities
"""
import json
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.domain import Trade, TradingMandate
from utils.logger import logger

class TradeRepository:
    """Trade data access"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def create(self, trade: Dict) -> bool:
        """Create new trade"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, strategy, expiry_type, regime_name, status,
                    entry_time, legs, entry_premium, current_pnl,
                    net_delta, net_theta, net_gamma, net_vega
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade['trade_id'],
                trade['strategy'],
                trade['expiry_type'],
                trade.get('regime_name'),
                trade['status'],
                trade['entry_time'],
                json.dumps(trade['legs']),
                trade.get('entry_premium', 0),
                trade.get('current_pnl', 0),
                trade.get('net_delta', 0),
                trade.get('net_theta', 0),
                trade.get('net_gamma', 0),
                trade.get('net_vega', 0)
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to create trade: {e}")
            self.conn.rollback()
            return False
    
    def update_pnl(self, trade_id: str, pnl: float, greeks: Dict) -> bool:
        """Update trade P&L and Greeks"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE trades
                SET current_pnl = ?,
                    net_delta = ?,
                    net_theta = ?,
                    net_gamma = ?,
                    net_vega = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (
                pnl,
                greeks.get('delta', 0),
                greeks.get('theta', 0),
                greeks.get('gamma', 0),
                greeks.get('vega', 0),
                trade_id
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update P&L: {e}")
            return False
    
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades WHERE status = 'OPEN'
            ORDER BY entry_time DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get specific trade"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def close_trade(self, trade_id: str, realized_pnl: float) -> bool:
        """Close trade"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE trades
                SET status = 'CLOSED',
                    exit_time = CURRENT_TIMESTAMP,
                    realized_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE trade_id = ?
            """, (realized_pnl, trade_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to close trade: {e}")
            return False

class AnalysisRepository:
    """Analysis history data access"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def save_analysis(self, analysis: Dict) -> bool:
        """Save analysis results"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_history (
                    timestamp, weekly_mandate, monthly_mandate,
                    next_weekly_mandate, vol_metrics, struct_metrics,
                    edge_metrics, external_metrics, veto_events, regime_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(),
                json.dumps(analysis.get('weekly_mandate')),
                json.dumps(analysis.get('monthly_mandate')),
                json.dumps(analysis.get('next_weekly_mandate')),
                json.dumps(analysis.get('vol_metrics')),
                json.dumps(analysis.get('struct_metrics')),
                json.dumps(analysis.get('edge_metrics')),
                json.dumps(analysis.get('external_metrics')),
                json.dumps(analysis.get('veto_events', [])),
                analysis.get('regime_name')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
            return False
    
    def get_latest_analysis(self) -> Optional[Dict]:
        """Get most recent analysis"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM analysis_history
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        # Parse JSON fields
        for field in ['weekly_mandate', 'monthly_mandate', 'next_weekly_mandate',
                      'vol_metrics', 'struct_metrics', 'edge_metrics',
                      'external_metrics', 'veto_events']:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except:
                    result[field] = None
        return result

class SystemStateRepository:
    """System state key-value store"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def set(self, key: str, value: str) -> bool:
        """Set state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set state: {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get state value"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
