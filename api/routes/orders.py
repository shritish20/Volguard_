"""
Orders API Routes  
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict
import sqlite3
from main import get_db
from utils.logger import logger

router = APIRouter()

class ExecuteOrderRequest(BaseModel):
    mandate_type: str  # "WEEKLY" or "MONTHLY"
    strategy: str      # "IRON_FLY", etc.

@router.post("/execute")
async def execute_order(
    request: ExecuteOrderRequest,
    db: sqlite3.Connection = Depends(get_db)
) -> Dict:
    """Execute a trading mandate"""
    # This would require full order placement logic
    # For MVP, return placeholder
    logger.info(f"Order execution requested: {request.mandate_type} {request.strategy}")
    
    return {
        "success": False,
        "message": "Order execution not implemented in MVP. Manual trading required."
    }
