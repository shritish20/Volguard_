"""
VolGuard 3.3 - Session Manager
Handles Upstox token lifecycle and automatic refresh
"""
import time
import requests
import threading
from typing import Optional, Dict
from datetime import datetime, timedelta
from config import Config
from utils.logger import logger
from utils.telegram import telegram


class SessionManager:
    """
    Manages Upstox session with automatic token refresh
    """
    
    def __init__(self):
        self.access_token = Config.UPSTOX_ACCESS_TOKEN
        self.refresh_token = Config.UPSTOX_REFRESH_TOKEN
        self.client_id = Config.UPSTOX_CLIENT_ID
        self.client_secret = Config.UPSTOX_CLIENT_SECRET
        
        self.token_expiry = None
        self.last_validation = None
        self.user_profile = None
        self.validation_lock = threading.Lock()
        
        # Token typically expires in 24 hours
        if self.access_token:
            # Assume token expires 23 hours from now (conservative)
            self.token_expiry = datetime.now() + timedelta(hours=23)
    
    def validate_session(self, force: bool = False) -> bool:
        """
        Validate current session and refresh if needed
        
        Args:
            force: Force validation even if recently checked
            
        Returns:
            bool: True if session is valid
        """
        with self.validation_lock:
            now = datetime.now()
            
            # Check if we need to validate
            if not force and self.last_validation:
                # Don't validate more than once per 5 minutes
                if (now - self.last_validation).seconds < 300:
                    return self.access_token is not None
            
            # Check if token is about to expire (within 1 hour)
            if self.token_expiry and (self.token_expiry - now).total_seconds() < 3600:
                logger.warning("⚠️ Token expiring soon, attempting refresh")
                telegram.send("Access token expiring soon, refreshing...", "WARNING")
                return self.refresh_session()
            
            # Validate by checking profile
            profile = self.get_user_profile()
            self.last_validation = now
            
            if profile:
                logger.info(f"✅ Session valid for user: {profile.get('user_name', 'Unknown')}")
                return True
            else:
                logger.warning("❌ Session invalid, attempting refresh")
                return self.refresh_session()
    
    def refresh_session(self) -> bool:
        """
        Refresh access token using refresh token
        
        Returns:
            bool: True if refresh successful
        """
        if not self.refresh_token:
            logger.error("❌ No refresh token available")
            telegram.send("No refresh token available - manual login required", "CRITICAL")
            return False
        
        try:
            logger.info("🔄 Attempting token refresh...")
            
            url = "https://api.upstox.com/v2/login/authorization/token"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                new_access_token = result.get("access_token")
                new_refresh_token = result.get("refresh_token")
                
                if new_access_token:
                    self.access_token = new_access_token
                    Config.UPSTOX_ACCESS_TOKEN = new_access_token
                    
                    # Update refresh token if provided
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token
                        Config.UPSTOX_REFRESH_TOKEN = new_refresh_token
                    
                    # Set new expiry
                    self.token_expiry = datetime.now() + timedelta(hours=23)
                    
                    logger.info("✅ Token refresh successful")
                    telegram.send("Access token refreshed successfully", "SUCCESS")
                    
                    # Save to environment/config file if needed
                    self._persist_tokens(new_access_token, new_refresh_token)
                    
                    return True
                else:
                    logger.error("❌ No access token in refresh response")
                    return False
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code} - {response.text}")
                telegram.send(f"Token refresh failed: {response.status_code}", "CRITICAL")
                return False
                
        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}", exc_info=True)
            telegram.send(f"Token refresh error: {str(e)}", "CRITICAL")
            return False
    
    def get_user_profile(self) -> Optional[Dict]:
        """
        Get user profile to validate session
        
        Returns:
            Dict: User profile if successful, None otherwise
        """
        if not self.access_token:
            return None
        
        try:
            url = "https://api.upstox.com/v2/user/profile"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    self.user_profile = result.get("data", {})
                    return self.user_profile
            elif response.status_code == 401:
                logger.warning("⚠️ Unauthorized - token invalid")
                return None
            else:
                logger.error(f"Profile fetch failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
            return None
    
    def _persist_tokens(self, access_token: str, refresh_token: Optional[str] = None):
        """
        Persist tokens to storage (optional)
        Override this method to save to database or file
        """
        # For now, just update in-memory config
        # In production, you might want to save to database or encrypted file
        
        try:
            # Option 1: Save to database
            from database.repositories import StateRepository
            from database.connection import get_connection
            
            with get_connection() as conn:
                state_repo = StateRepository(conn)
                state_repo.set_state("upstox_access_token", access_token)
                if refresh_token:
                    state_repo.set_state("upstox_refresh_token", refresh_token)
                
            logger.info("✅ Tokens persisted to database")
            
        except Exception as e:
            logger.warning(f"Failed to persist tokens: {e}")
    
    def get_current_token(self) -> Optional[str]:
        """
        Get current valid access token
        
        Returns:
            str: Access token or None
        """
        if self.validate_session():
            return self.access_token
        return None
    
    def is_session_valid(self) -> bool:
        """
        Quick check if session is valid
        
        Returns:
            bool: True if valid
        """
        return self.access_token is not None and self.token_expiry and datetime.now() < self.token_expiry


# Global instance
session_manager = SessionManager()
