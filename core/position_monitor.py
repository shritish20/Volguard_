"""
API Routes for Position Monitoring
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict
from database.connection import get_connection
from database.repositories import TradeRepository
from core.position_monitor import position_monitor, initialize_position_monitor
from core.order_orchestrator import OrderOrchestrator
from utils.logger import logger

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("/")
async def get_positions():
    """
    Get all open positions with current P&L
    """
    try:
        with get_connection() as conn:
            trade_repo = TradeRepository(conn)
            open_trades = trade_repo.get_open_trades()
            
            # Calculate current P&L for each
            if position_monitor:
                positions = []
                for trade in open_trades:
                    current_pnl = position_monitor.calculate_current_pnl(trade)
                    
                    positions.append({
                        'trade_id': trade['trade_id'],
                        'strategy': trade['strategy'],
                        'expiry_type': trade['expiry_type'],
                        'expiry_date': trade.get('expiry_date'),
                        'entry_time': trade['entry_time'],
                        'entry_credit': trade.get('entry_credit', 0),
                        'current_pnl': current_pnl,
                        'max_loss': trade.get('max_loss', 0),
                        'legs': trade.get('legs', [])
                    })
                
                return {
                    "success": True,
                    "count": len(positions),
                    "positions": positions
                }
            else:
                # Fallback without monitor
                return {
                    "success": True,
                    "count": len(open_trades),
                    "positions": open_trades
                }
            
    except Exception as e:
        logger.error(f"Get positions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_position_summary():
    """
    Get summary of all positions
    """
    try:
        if not position_monitor:
            raise HTTPException(status_code=503, detail="Position monitor not running")
        
        summary = position_monitor.get_position_summary()
        
        return {
            "success": True,
            **summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get position summary error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trade_id}")
async def get_position_details(trade_id: str):
    """
    Get detailed position information for specific trade
    """
    try:
        with get_connection() as conn:
            trade_repo = TradeRepository(conn)
            trade = trade_repo.get_trade(trade_id)
            
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            
            # Calculate current P&L
            current_pnl = None
            if position_monitor:
                current_pnl = position_monitor.calculate_current_pnl(trade)
            
            return {
                "success": True,
                "trade": {
                    **trade,
                    "current_pnl": current_pnl
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get position details error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/start")
async def start_position_monitor():
    """
    Start position monitoring
    """
    try:
        global position_monitor
        
        if position_monitor and position_monitor.monitoring:
            return {
                "success": True,
                "message": "Position monitor already running"
            }
        
        # Initialize if not exists
        if not position_monitor:
            with get_connection() as conn:
                order_orchestrator = OrderOrchestrator(conn)
                position_monitor = initialize_position_monitor(conn, order_orchestrator)
        
        position_monitor.start_monitoring()
        
        return {
            "success": True,
            "message": "Position monitor started"
        }
        
    except Exception as e:
        logger.error(f"Start monitor error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/stop")
async def stop_position_monitor():
    """
    Stop position monitoring
    """
    try:
        if not position_monitor:
            return {
                "success": True,
                "message": "Position monitor not running"
            }
        
        position_monitor.stop_monitoring()
        
        return {
            "success": True,
            "message": "Position monitor stopped"
        }
        
    except Exception as e:
        logger.error(f"Stop monitor error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitor/status")
async def get_monitor_status():
    """
    Get position monitor status
    """
    try:
        if not position_monitor:
            return {
                "running": False,
                "message": "Position monitor not initialized"
            }
        
        return {
            "running": position_monitor.monitoring,
            "check_interval": position_monitor.check_interval
        }
        
    except Exception as e:
        logger.error(f"Get monitor status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exit-all")
async def exit_all_positions():
    """
    Emergency exit all positions
    """
    try:
        if not position_monitor:
            raise HTTPException(status_code=503, detail="Position monitor not running")
        
        position_monitor.force_exit_all(reason="MANUAL_REQUEST")
        
        return {
            "success": True,
            "message": "Exit all positions initiated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exit all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{trade_id}/set-manual-exit")
async def set_manual_exit_flag(trade_id: str):
    """
    Set manual exit flag for a trade
    Position monitor will exit on next check
    """
    try:
        with get_connection() as conn:
            trade_repo = TradeRepository(conn)
            
            trade = trade_repo.get_trade(trade_id)
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            
            trade_repo.update_trade(trade_id, manual_exit_flag=1)
            
            return {
                "success": True,
                "message": f"Manual exit flag set for {trade_id}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set manual exit error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{trade_id}/pnl")
async def get_trade_pnl(trade_id: str):
    """
    Get current P&L for specific trade
    """
    try:
        with get_connection() as conn:
            trade_repo = TradeRepository(conn)
            trade = trade_repo.get_trade(trade_id)
            
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            
            if not position_monitor:
                raise HTTPException(status_code=503, detail="Position monitor not running")
            
            current_pnl = position_monitor.calculate_current_pnl(trade)
            entry_credit = trade.get('entry_credit', 0)
            
            pnl_pct = (current_pnl / entry_credit * 100) if entry_credit > 0 else 0
            
            return {
                "success": True,
                "trade_id": trade_id,
                "current_pnl": current_pnl,
                "entry_credit": entry_credit,
                "pnl_percentage": pnl_pct,
                "max_loss": trade.get('max_loss', 0)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get trade P&L error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
