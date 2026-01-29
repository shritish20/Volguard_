"""
Analysis API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import sqlite3
from main import get_db
from services.trading_service import TradingService
from database.repositories import AnalysisRepository
from utils.logger import logger

router = APIRouter()

@router.post("/run")
async def run_analysis(
    force_refresh: bool = False,
    db: sqlite3.Connection = Depends(get_db)
) -> Dict:
    """Run full market analysis"""
    try:
        service = TradingService(db)
        result = service.run_full_analysis()
        
        if not result:
            raise HTTPException(status_code=500, detail="Analysis failed")
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Analysis endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/latest")
async def get_latest_analysis(db: sqlite3.Connection = Depends(get_db)) -> Dict:
    """Get most recent analysis results"""
    try:
        repo = AnalysisRepository(db)
        result = repo.get_latest_analysis()
        
        if not result:
            return {
                "success": False,
                "message": "No analysis found. Run /api/analysis/run first."
            }
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Get latest analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
