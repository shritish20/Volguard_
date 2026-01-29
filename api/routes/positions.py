"""
Positions API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List
import sqlite3
from main import get_db
from database.repositories import TradeRepository
from utils.logger import logger
import json

router = APIRouter()

@router.get("")
async def get_positions(db: sqlite3.Connection = Depends(get_db)) -> Dict:
    """Get all open positions"""
    try:
        repo = TradeRepository(db)
        open_trades = repo.get_open_trades()
        
        positions = []
        for trade in open_trades:
            # Parse legs
            legs = json.loads(trade['legs']) if isinstance(trade['legs'], str) else trade['legs']
            for leg in legs:
                positions.append({
                    'trade_id': trade['trade_id'],
                    'instrument_key': leg['key'],
                    'symbol': leg['symbol'],
                    'side': leg['side'],
                    'role': leg['role'],
                    'quantity': leg['qty'],
                    'entry_price': leg['entry_price'],
                    'current_price': leg.get('ltp', leg['entry_price'])
                })
        
        return {
            "success": True,
            "data": {
                "positions": positions,
                "count": len(positions)
            }
        }
    except Exception as e:
        logger.error(f"Get positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{position_id}/close")
async def close_position(
    position_id: str,
    db: sqlite3.Connection = Depends(get_db)
) -> Dict:
    """Close a specific position"""
    # Implementation would require actual order placement
    return {
        "success": False,
        "message": "Position closing not implemented in MVP"
    }
