"""
VOLGUARD 3.3 - FASTAPI BACKEND
================================
Production-ready Option Selling System with FastAPI REST + WebSocket

Version: 3.3 Professional Refactored Edition
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import all routers
from api.routes import analysis, positions, trades, orders, metrics
from api.websocket import router as ws_router, start_websocket_broadcast
from database.connection import DatabaseManager, init_database
from utils.logger import setup_logger
from config import Config

# Setup logging
logger = setup_logger()

# Global database manager
db_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("=" * 80)
    logger.info("VOLGUARD 3.3 - BACKEND STARTING")
    logger.info("=" * 80)
    
    try:
        # Validate configuration
        Config.validate()
        logger.info("✅ Configuration validated")
        
        # Initialize database
        global db_manager
        db_manager = DatabaseManager()
        init_database(db_manager.get_connection())
        logger.info("✅ Database initialized")
        
        # Start WebSocket broadcast task
        await start_websocket_broadcast()
        logger.info("✅ WebSocket broadcast started")
        
        logger.info("🚀 System ready for trading")
        
    except Exception as e:
        logger.critical(f"❌ Startup failed: {e}")
        raise
    
    yield  # Application runs
    
    # Shutdown
    logger.info("System shutdown initiated")
    if db_manager:
        db_manager.close()
    logger.info("Goodbye.")

# Create FastAPI app
app = FastAPI(
    title="VolGuard 3.3 API",
    description="Professional Option Selling System - REST API",
    version="3.3.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(positions.router, prefix="/api/positions", tags=["Positions"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(ws_router, tags=["WebSocket"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "VolGuard 3.3 API",
        "version": "3.3.0",
        "status": "running",
        "environment": Config.ENVIRONMENT,
        "dry_run": Config.DRY_RUN_MODE
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "environment": Config.ENVIRONMENT,
            "dry_run": Config.DRY_RUN_MODE
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

def get_db():
    """Dependency to get database connection"""
    return db_manager.get_connection()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("VG_ENV", "PRODUCTION") != "PRODUCTION",
        log_level="info"
    )
