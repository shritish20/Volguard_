"""
Metrics API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import sqlite3
from main import get_db
from services.portfolio_service import PortfolioService
from utils.logger import logger

router = APIRouter()

@router.get("/portfolio")
async def get_portfolio_metrics(db: sqlite3.Connection = Depends(get_db)) -> Dict:
    """Get current portfolio metrics (P&L, Greeks)"""
    try:
        service = PortfolioService(db)
        metrics = service.calculate_live_portfolio()
        
        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Get portfolio metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
