"""
Upstox Integration - Market Data Fetcher
PRESERVED FROM ORIGINAL with simplification
"""
import upstox_client
from upstox_client.rest import ApiException
from upstox_client.api.market_quote_api import MarketQuoteApi
from upstox_client.api.options_api import OptionsApi
from upstox_client.api.history_v3_api import HistoryV3Api
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config import Config
from utils.logger import logger
import pandas as pd

class UpstoxFetcher:
    """Market data fetching from Upstox"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token or Config.UPSTOX_ACCESS_TOKEN
        self.configuration = upstox_client.Configuration()
        self.configuration.access_token = self.access_token
        
        # Initialize API clients
        self.quote_api = MarketQuoteApi(upstox_client.ApiClient(self.configuration))
        self.options_api = OptionsApi(upstox_client.ApiClient(self.configuration))
        self.history_api = HistoryV3Api(upstox_client.ApiClient(self.configuration))
    
    def get_ltp(self, instrument_key: str) -> Optional[float]:
        """Get Last Traded Price"""
        try:
            response = self.quote_api.get_full_market_quote(instrument_key, "")
            if response.status == "success":
                return response.data[instrument_key].last_price
        except Exception as e:
            logger.error(f"Failed to get LTP for {instrument_key}: {e}")
        return None
    
    def get_option_chain(self, expiry: str) -> Optional[pd.DataFrame]:
        """Get option chain for expiry"""
        try:
            response = self.options_api.get_option_contract(
                instrument_name="NIFTY",
                expiry_date=expiry
            )
            if response.status == "success":
                return pd.DataFrame(response.data)
        except Exception as e:
            logger.error(f"Failed to get option chain: {e}")
        return None
    
    def get_historical_data(self, instrument_key: str, interval: str = "day", days: int = 365) -> Optional[pd.DataFrame]:
        """Get historical OHLC data"""
        try:
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_date = datetime.now().strftime("%Y-%m-%d")
            
            response = self.history_api.get_historical_candle_data(
                instrument_key=instrument_key,
                interval=interval,
                to_date=to_date,
                from_date=from_date
            )
            
            if response.status == "success" and response.data.candles:
                df = pd.DataFrame(
                    response.data.candles,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df.sort_values('timestamp')
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
        return None
