"""
Database Repositories for VolGuard 3.3
Enhanced with all trading logic support
"""
import json
from typing import Optional, List, Dict
from datetime import datetime, date
from utils.logger import logger


class StateRepository:
    """System state key-value storage"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def set_state(self, key: str, value: str):
        """Set state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error setting state {key}: {e}")
    
    def get_state(self, key: str, default: str = None) -> Optional[str]:
        """Get state value"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        except Exception as e:
            logger.error(f"Error getting state {key}: {e}")
            return default


class TradeRepository:
    """Trade and position management"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def create_trade(
        self,
        trade_id: str,
        strategy: str,
        expiry_type: str,
        expiry_date: str,
        status: str,
        entry_time: str,
        deployment_amount: float = 0
    ):
        """Create new trade record"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    trade_id, strategy, expiry_type, expiry_date, status, 
                    entry_time, deployment_amount, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, strategy, expiry_type, expiry_date, status,
                entry_time, deployment_amount, datetime.now().isoformat()
            ))
            self.conn.commit()
            logger.info(f"Trade created: {trade_id}")
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
    
    def update_trade(
        self,
        trade_id: str,
        status: Optional[str] = None,
        entry_credit: Optional[float] = None,
        max_loss: Optional[float] = None,
        legs: Optional[List[Dict]] = None,
        **kwargs
    ):
        """Update trade record"""
        try:
            updates = []
            params = []
            
            if status:
                updates.append("status = ?")
                params.append(status)
            
            if entry_credit is not None:
                updates.append("entry_credit = ?")
                params.append(entry_credit)
            
            if max_loss is not None:
                updates.append("max_loss = ?")
                params.append(max_loss)
            
            # Handle additional kwargs
            for key, value in kwargs.items():
                updates.append(f"{key} = ?")
                params.append(value)
            
            if not updates:
                return
            
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(trade_id)
            
            query = f"UPDATE trades SET {', '.join(updates)} WHERE trade_id = ?"
            
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error updating trade {trade_id}: {e}")
    
    def update_trade_status(self, trade_id: str, status: str):
        """Update trade status"""
        self.update_trade(trade_id, status=status)
    
    def update_trade_pnl(self, trade_id: str, current_pnl: float):
        """Update current P&L"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE trades SET current_pnl = ?, updated_at = ?
                WHERE trade_id = ?
            """, (current_pnl, datetime.now().isoformat(), trade_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error updating P&L: {e}")
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get trade by ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE trade_id = ?
            """, (trade_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            trade = dict(zip(columns, row))
            
            # Get legs
            cursor.execute("""
                SELECT * FROM trade_legs WHERE trade_id = ?
            """, (trade_id,))
            legs_rows = cursor.fetchall()
            
            if legs_rows:
                leg_columns = [desc[0] for desc in cursor.description]
                trade['legs'] = [dict(zip(leg_columns, leg_row)) for leg_row in legs_rows]
            else:
                trade['legs'] = []
            
            return trade
            
        except Exception as e:
            logger.error(f"Error getting trade {trade_id}: {e}")
            return None
    
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_time DESC
            """)
            rows = cursor.fetchall()
            
            columns = [desc[0] for desc in cursor.description]
            trades = [dict(zip(columns, row)) for row in rows]
            
            # Get legs for each trade
            for trade in trades:
                cursor.execute("""
                    SELECT * FROM trade_legs WHERE trade_id = ?
                """, (trade['trade_id'],))
                legs_rows = cursor.fetchall()
                
                if legs_rows:
                    leg_columns = [desc[0] for desc in cursor.description]
                    trade['legs'] = [dict(zip(leg_columns, leg_row)) for leg_row in legs_rows]
                else:
                    trade['legs'] = []
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting open trades: {e}")
            return []
    
    def get_trades_by_date(self, target_date: date) -> List[Dict]:
        """Get trades opened on specific date"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM trades 
                WHERE DATE(entry_time) = ?
                ORDER BY entry_time DESC
            """, (target_date.isoformat(),))
            rows = cursor.fetchall()
            
            columns = [desc[0] for desc in cursor.description]
            trades = [dict(zip(columns, row)) for row in rows]
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting trades by date: {e}")
            return []
    
    def get_total_realized_pnl(self) -> float:
        """Get total realized P&L from closed trades"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT SUM(realized_pnl) FROM trades WHERE status = 'CLOSED'
            """)
            result = cursor.fetchone()
            return result[0] if result[0] else 0.0
        except Exception as e:
            logger.error(f"Error getting realized P&L: {e}")
            return 0.0


class AnalysisRepository:
    """Analysis history management"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def save_analysis(self, analysis: Dict):
        """Save analysis result"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_history (
                    timestamp, weekly_mandate, monthly_mandate, next_weekly_mandate,
                    vol_metrics, struct_metrics, edge_metrics, external_metrics,
                    veto_events, regime_name, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis['timestamp'],
                json.dumps(analysis.get('weekly_mandate')),
                json.dumps(analysis.get('monthly_mandate')),
                json.dumps(analysis.get('next_weekly_mandate')),
                json.dumps(analysis.get('vol_metrics')),
                json.dumps(analysis.get('struct_metrics')),
                json.dumps(analysis.get('edge_metrics')),
                json.dumps(analysis.get('external_metrics')),
                json.dumps(analysis.get('veto_events', [])),
                analysis.get('regime_name'),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            logger.info("Analysis saved to database")
        except Exception as e:
            logger.error(f"Error saving analysis: {e}")
    
    def get_latest_analysis(self) -> Optional[Dict]:
        """Get most recent analysis"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM analysis_history 
                ORDER BY timestamp DESC LIMIT 1
            """)
            row = cursor.fetchone()
            
            if not row:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            analysis = dict(zip(columns, row))
            
            # Parse JSON fields
            json_fields = [
                'weekly_mandate', 'monthly_mandate', 'next_weekly_mandate',
                'vol_metrics', 'struct_metrics', 'edge_metrics', 
                'external_metrics', 'veto_events'
            ]
            
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting latest analysis: {e}")
            return None


class OrderRepository:
    """Order tracking"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def save_leg(self, trade_id: str, leg: Dict):
        """Save executed leg"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trade_legs (
                    trade_id, order_id, instrument_key, side, option_type,
                    strike, quantity, filled_qty, entry_price, expected_price,
                    slippage_pct, fill_time, role, expiry, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, leg.get("order_id"), leg["instrument_key"], leg["side"],
                leg["option_type"], leg["strike"], leg["quantity"], leg.get("filled_qty"),
                leg.get("entry_price"), leg.get("expected_price"), leg.get("slippage_pct"),
                leg.get("fill_time"), leg.get("role"), leg.get("expiry"),
                datetime.now().isoformat()
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving leg: {e}")
    
    def save_order(
        self,
        order_id: str,
        trade_id: str,
        instrument_key: str,
        side: str,
        quantity: int,
        order_type: str,
        status: str
    ):
        """Save order attempt"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO orders (
                    order_id, trade_id, instrument_key, side, quantity,
                    order_type, status, placed_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, trade_id, instrument_key, side, quantity,
                order_type, status, datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving order: {e}")


class AlertRepository:
    """Alert logging"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        trade_id: Optional[str] = None
    ):
        """Create alert"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (
                    timestamp, alert_type, severity, message, trade_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), alert_type, severity, message,
                trade_id, datetime.now().isoformat()
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error creating alert: {e}")


class RiskEventRepository:
    """Risk event logging"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def log_risk_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        metrics: Optional[Dict] = None,
        action_taken: Optional[str] = None
    ):
        """Log risk event"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO risk_events (
                    timestamp, event_type, severity, description, metrics, action_taken, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), event_type, severity, description,
                json.dumps(metrics) if metrics else None, action_taken,
                datetime.now().isoformat()
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error logging risk event: {e}")
