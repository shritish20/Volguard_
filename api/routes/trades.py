"""
Trades API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Optional
import sqlite3
from datetime import datetime, timedelta
from main import get_db
from database.repositories import TradeRepository
from utils.logger import logger

router = APIRouter()

@router.get("/history")
async def get_trade_history(
    status: Optional[str] = Query(None, description="Filter by status"),
    days: int = Query(30, description="Number of days to look back"),
    db: sqlite3.Connection = Depends(get_db)
) -> Dict:
    """Get trade history with filters"""
    try:
        cursor = db.cursor()
        
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        
        cutoff_date = datetime.now() - timedelta(days=days)
        query += " AND entry_time >= ?"
        params.append(cutoff_date.isoformat())
        
        query += " ORDER BY entry_time DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        trades = [dict(row) for row in rows]
        
        # Calculate summary stats
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('realized_pnl', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('realized_pnl', 0) < 0)
        total_pnl = sum(t.get('realized_pnl', 0) for t in trades)
        
        return {
            "success": True,
            "data": {
                "trades": trades,
                "summary": {
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
                    "total_pnl": total_pnl
                }
            }
        }
    except Exception as e:
        logger.error(f"Get trade history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{trade_id}")
async def get_trade_details(
    trade_id: str,
    db: sqlite3.Connection = Depends(get_db)
) -> Dict:
    """Get detailed information for a specific trade"""
    try:
        repo = TradeRepository(db)
        trade = repo.get_trade(trade_id)
        
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        
        return {
            "success": True,
            "data": trade
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trade details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
