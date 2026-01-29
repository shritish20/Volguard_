"""
Telegram Alerting - PRESERVED FROM ORIGINAL
"""
import requests
import threading
import time
from config import Config
from utils.logger import logger

class TelegramAlerter:
    """Send alerts via Telegram"""
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.rate_limit_lock = threading.Lock()
        self.last_send_time = 0
        self.min_interval = 1.0
    
    def send(self, message: str, level: str = "INFO", retry: int = 3) -> bool:
        """Send telegram message with retry logic"""
        if not self.bot_token or not self.chat_id:
            logger.debug(f"Telegram not configured, skipping: {message}")
            return False
        
        emoji_map = {
            "CRITICAL": "🚨",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "TRADE": "💰",
            "SYSTEM": "⚙️"
        }
        prefix = emoji_map.get(level, "📢")
        full_msg = f"{prefix} *VOLGUARD 3.3*\n{message}"
        
        # Rate limiting
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_send_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        
        # Retry logic
        for attempt in range(retry):
            try:
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": full_msg,
                        "parse_mode": "Markdown"
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    with self.rate_limit_lock:
                        self.last_send_time = time.time()
                    return True
            except Exception as e:
                logger.error(f"Telegram send error (attempt {attempt+1}/{retry}): {e}")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)
        
        logger.error(f"Failed to send Telegram after {retry} attempts")
        return False

# Global instance
telegram = TelegramAlerter()
