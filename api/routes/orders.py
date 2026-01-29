"""
API Routes for Order Execution
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
from database.connection import get_connection
from core.strategy_builder import StrategyBuilder
from core.order_orchestrator import OrderOrchestrator
from core.risk_manager import RiskManager
from core.upstox import UpstoxFetcher
from models.domain import TradingMandate
from utils.logger import logger
from utils.telegram import telegram

router = APIRouter(prefix="/api/orders", tags=["orders"])


class ExecuteStrategyRequest(BaseModel):
    """Request to execute a strategy"""
    mandate: Dict
    validate_only: bool = False


class ExitTradeRequest(BaseModel):
    """Request to exit a trade"""
    trade_id: str
    reason: str = "MANUAL"


@router.post("/execute-strategy")
async def execute_strategy(request: ExecuteStrategyRequest):
    """
    Build and execute strategy from mandate
    
    Steps:
    1. Parse mandate
    2. Build strategy legs
    3. Validate risks
    4. Execute (if validate_only=False)
    """
    try:
        with get_connection() as conn:
            # Initialize components
            upstox = UpstoxFetcher()
            strategy_builder = StrategyBuilder(upstox)
            order_orchestrator = OrderOrchestrator(conn)
            risk_manager = RiskManager(conn)
            
            # Parse mandate
            mandate_dict = request.mandate
            
            # Build strategy
            logger.info(f"🔨 Building strategy: {mandate_dict.get('suggested_structure')}")
            
            # Create simple mandate object
            class SimpleMandateused for building
                pass
            
            mandate_obj = SimpleMandate()
            mandate_obj.suggested_structure = mandate_dict.get('suggested_structure', '')
            mandate_obj.expiry_type = mandate_dict.get('expiry_type', 'WEEKLY')
            mandate_obj.smart_expiry_weekly = mandate_dict.get('smart_expiry_weekly')
            mandate_obj.smart_expiry_monthly = mandate_dict.get('smart_expiry_monthly')
            mandate_obj.max_lots = mandate_dict.get('max_lots', 1)
            mandate_obj.directional_bias = mandate_dict.get('directional_bias', 'NEUTRAL')
            
            legs = strategy_builder.build_strategy(mandate_obj)
            
            if not legs:
                raise HTTPException(status_code=400, detail="Failed to build strategy")
            
            logger.info(f"✅ Strategy built with {len(legs)} legs")
            
            # Validate strategy
            valid, violations = risk_manager.validate_trade(mandate_dict, legs)
            
            if not valid:
                logger.warning(f"⚠️ Risk violations: {violations}")
                
                if request.validate_only:
                    return {
                        "success": False,
                        "validated": False,
                        "violations": violations,
                        "legs": legs
                    }
                else:
                    raise HTTPException(status_code=400, detail={"violations": violations})
            
            logger.info("✅ Risk validation passed")
            
            # If validate_only, return validation result
            if request.validate_only:
                # Calculate estimated costs
                net_credit = sum([
                    leg['ltp'] * leg['quantity'] * 25 * (1 if leg['side'] == 'SELL' else -1)
                    for leg in legs
                ])
                
                return {
                    "success": True,
                    "validated": True,
                    "violations": [],
                    "legs": legs,
                    "net_credit": net_credit,
                    "leg_count": len(legs)
                }
            
            # Execute strategy
            logger.info("🚀 Executing strategy...")
            
            trade_id = order_orchestrator.execute_strategy(
                legs=legs,
                strategy_name=mandate_dict.get('suggested_structure', 'UNKNOWN'),
                mandate_data=mandate_dict
            )
            
            if not trade_id:
                raise HTTPException(status_code=500, detail="Strategy execution failed")
            
            logger.info(f"✅ Strategy executed: {trade_id}")
            
            return {
                "success": True,
                "trade_id": trade_id,
                "legs": len(legs),
                "message": "Strategy executed successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Execute strategy error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exit-trade")
async def exit_trade(request: ExitTradeRequest):
    """
    Exit an open trade
    """
    try:
        with get_connection() as conn:
            order_orchestrator = OrderOrchestrator(conn)
            
            success = order_orchestrator.exit_strategy(
                trade_id=request.trade_id,
                reason=request.reason
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Exit failed")
            
            return {
                "success": True,
                "trade_id": request.trade_id,
                "message": "Trade exited successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exit trade error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-strategy")
async def build_strategy_preview(mandate: Dict):
    """
    Build strategy without executing (preview only)
    """
    try:
        upstox = UpstoxFetcher()
        strategy_builder = StrategyBuilder(upstox)
        
        # Create mandate object
        class SimpleMandate:
            pass
        
        mandate_obj = SimpleMandate()
        mandate_obj.suggested_structure = mandate.get('suggested_structure', '')
        mandate_obj.expiry_type = mandate.get('expiry_type', 'WEEKLY')
        mandate_obj.smart_expiry_weekly = mandate.get('smart_expiry_weekly')
        mandate_obj.smart_expiry_monthly = mandate.get('smart_expiry_monthly')
        mandate_obj.max_lots = mandate.get('max_lots', 1)
        mandate_obj.directional_bias = mandate.get('directional_bias', 'NEUTRAL')
        
        legs = strategy_builder.build_strategy(mandate_obj)
        
        if not legs:
            raise HTTPException(status_code=400, detail="Failed to build strategy")
        
        # Calculate costs
        net_credit = sum([
            leg['ltp'] * leg['quantity'] * 25 * (1 if leg['side'] == 'SELL' else -1)
            for leg in legs
        ])
        
        return {
            "success": True,
            "legs": legs,
            "leg_count": len(legs),
            "net_credit": net_credit,
            "strikes": [leg['strike'] for leg in legs]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Build strategy error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate-trade")
async def validate_trade(mandate: Dict):
    """
    Validate trade without building/executing
    """
    try:
        with get_connection() as conn:
            risk_manager = RiskManager(conn)
            
            # For validation without legs, do partial checks
            violations = []
            
            # Capital check
            ok, msg = risk_manager._check_capital_allocation(mandate)
            if not ok:
                violations.append(msg)
            
            # Daily trade limit
            ok, msg = risk_manager._check_daily_trade_limit()
            if not ok:
                violations.append(msg)
            
            # Drawdown limit
            ok, msg = risk_manager._check_drawdown_limit()
            if not ok:
                violations.append(msg)
            
            # Circuit breaker
            if risk_manager.is_circuit_breaker_active():
                violations.append("Circuit breaker is active")
            
            return {
                "valid": len(violations) == 0,
                "violations": violations
            }
            
    except Exception as e:
        logger.error(f"Validate trade error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-status")
async def get_risk_status():
    """
    Get current risk status
    """
    try:
        with get_connection() as conn:
            risk_manager = RiskManager(conn)
            status = risk_manager.get_risk_status()
            
            return status
            
    except Exception as e:
        logger.error(f"Get risk status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
