"""
VolGuard 3.3 - Main FastAPI Application
Complete trading system with execution and monitoring
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Core imports
from config import Config
from database.connection import get_connection
from database.schema import init_schema, upgrade_schema
from core.session_manager import session_manager
from core.position_monitor import initialize_position_monitor, position_monitor
from core.order_orchestrator import OrderOrchestrator
from utils.logger import logger
from utils.telegram import telegram

# API routes
from api.routes import analysis, metrics, orders, positions, trades
from api import websocket


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handle startup and shutdown events
    """
    # Startup
    logger.info("🚀 VolGuard 3.3 starting up...")
    
    try:
        # 1. Initialize database
        with get_connection() as conn:
            try:
                init_schema(conn)
                logger.info("✅ Database schema initialized")
            except:
                # Schema already exists, try upgrade
                upgrade_schema(conn)
                logger.info("✅ Database schema upgraded")
        
        # 2. Validate session
        if not session_manager.validate_session():
            logger.warning("⚠️ Session validation failed, attempting refresh...")
            if not session_manager.refresh_session():
                logger.error("❌ Session refresh failed - manual login required")
                telegram.send("Session refresh failed - manual login required", "CRITICAL")
        else:
            logger.info("✅ Session validated")
        
        # 3. Initialize position monitor
        try:
            with get_connection() as conn:
                order_orchestrator = OrderOrchestrator(conn)
                global position_monitor
                position_monitor = initialize_position_monitor(conn, order_orchestrator)
                
                # Start monitoring
                position_monitor.start_monitoring()
                logger.info("✅ Position monitor started")
        except Exception as e:
            logger.error(f"Failed to start position monitor: {e}")
        
        # 4. Send startup notification
        telegram.send(
            f"✅ VolGuard 3.3 Started\n"
            f"Environment: {Config.ENVIRONMENT}\n"
            f"Mode: {'DRY RUN' if Config.DRY_RUN_MODE else 'LIVE TRADING'}\n"
            f"Session: {'Valid' if session_manager.is_session_valid() else 'Invalid'}",
            "SUCCESS"
        )
        
        logger.info("✅ VolGuard 3.3 ready")
        
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        telegram.send(f"Startup error: {str(e)}", "CRITICAL")
    
    yield
    
    # Shutdown
    logger.info("👋 VolGuard 3.3 shutting down...")
    
    try:
        # Stop position monitor
        if position_monitor:
            position_monitor.stop_monitoring()
            logger.info("✅ Position monitor stopped")
        
        telegram.send("VolGuard 3.3 shutdown complete", "SYSTEM")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")
    
    logger.info("Goodbye.")


# Create FastAPI app
app = FastAPI(
    title="VolGuard 3.3 API",
    description="Professional Options Trading System",
    version="3.3.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "version": "3.3.0",
        "environment": Config.ENVIRONMENT,
        "dry_run": Config.DRY_RUN_MODE,
        "session_valid": session_manager.is_session_valid(),
        "position_monitor_running": position_monitor.monitoring if position_monitor else False
    }


@app.get("/")
async def root():
    """
    Root endpoint with API info
    """
    return {
        "name": "VolGuard 3.3 API",
        "version": "3.3.0",
        "description": "Professional Options Trading System",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "analysis": "/api/analysis",
            "orders": "/api/orders",
            "positions": "/api/positions",
            "trades": "/api/trades",
            "metrics": "/api/metrics",
            "websocket": "/ws"
        }
    }


# Include routers
app.include_router(analysis.router)
app.include_router(orders.router)
app.include_router(positions.router)
app.include_router(trades.router)
app.include_router(metrics.router)

# WebSocket
app.add_api_websocket_route("/ws", websocket.websocket_endpoint)


# Session management endpoints
@app.post("/api/session/refresh")
async def refresh_session():
    """
    Manually refresh session token
    """
    try:
        success = session_manager.refresh_session()
        
        if success:
            return {
                "success": True,
                "message": "Session refreshed successfully"
            }
        else:
            raise HTTPException(status_code=401, detail="Session refresh failed")
            
    except Exception as e:
        logger.error(f"Session refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/status")
async def get_session_status():
    """
    Get session status
    """
    return {
        "valid": session_manager.is_session_valid(),
        "token_expiry": session_manager.token_expiry.isoformat() if session_manager.token_expiry else None,
        "last_validation": session_manager.last_validation.isoformat() if session_manager.last_validation else None,
        "user_profile": session_manager.user_profile
    }


# Risk management endpoints
@app.get("/api/risk/status")
async def get_risk_status():
    """
    Get current risk status
    """
    try:
        from core.risk_manager import RiskManager
        
        with get_connection() as conn:
            risk_manager = RiskManager(conn)
            status = risk_manager.get_risk_status()
            
            return status
            
    except Exception as e:
        logger.error(f"Get risk status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/risk/circuit-breaker/activate")
async def activate_circuit_breaker(reason: str):
    """
    Manually activate circuit breaker
    """
    try:
        from core.risk_manager import RiskManager
        
        with get_connection() as conn:
            risk_manager = RiskManager(conn)
            risk_manager.activate_circuit_breaker(reason)
            
            return {
                "success": True,
                "message": "Circuit breaker activated"
            }
            
    except Exception as e:
        logger.error(f"Activate circuit breaker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/risk/circuit-breaker/deactivate")
async def deactivate_circuit_breaker():
    """
    Manually deactivate circuit breaker
    """
    try:
        from core.risk_manager import RiskManager
        
        with get_connection() as conn:
            risk_manager = RiskManager(conn)
            risk_manager.deactivate_circuit_breaker()
            
            return {
                "success": True,
                "message": "Circuit breaker deactivated"
            }
            
    except Exception as e:
        logger.error(f"Deactivate circuit breaker error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# System status endpoint
@app.get("/api/system/status")
async def get_system_status():
    """
    Get comprehensive system status
    """
    try:
        from core.risk_manager import RiskManager
        from database.repositories import TradeRepository
        
        with get_connection() as conn:
            trade_repo = TradeRepository(conn)
            risk_manager = RiskManager(conn)
            
            open_trades = trade_repo.get_open_trades()
            risk_status = risk_manager.get_risk_status()
            
            # Position summary
            position_summary = {}
            if position_monitor:
                position_summary = position_monitor.get_position_summary()
            
            return {
                "session": {
                    "valid": session_manager.is_session_valid(),
                    "token_expiry": session_manager.token_expiry.isoformat() if session_manager.token_expiry else None
                },
                "trading": {
                    "open_trades": len(open_trades),
                    "total_pnl": position_summary.get('total_pnl', 0)
                },
                "monitoring": {
                    "position_monitor_running": position_monitor.monitoring if position_monitor else False
                },
                "risk": risk_status,
                "config": {
                    "environment": Config.ENVIRONMENT,
                    "dry_run": Config.DRY_RUN_MODE,
                    "base_capital": Config.BASE_CAPITAL
                }
            }
            
    except Exception as e:
        logger.error(f"Get system status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        log_level="info"
    )
