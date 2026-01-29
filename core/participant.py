"""
FII/DII Participant Data Fetcher
PRESERVED FROM ORIGINAL - informational only in v3.3
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from config import Config
from utils.logger import logger
import io

class ParticipantDataFetcher:
    """Fetch FII/DII data from NSE archives"""
    
    BASE_URL = "https://archives.nseindia.com/content/nsccl/fao_participant_oi_{}.csv"
    
    @staticmethod
    def get_candidate_dates(max_attempts: int = 10) -> List[str]:
        """Get potential dates to fetch (accounting for holidays)"""
        dates = []
        current = datetime.now()
        attempts = 0
        while len(dates) < 5 and attempts < max_attempts:
            if current.weekday() < 5:  # Monday=0, Friday=4
                dates.append(current.strftime("%d%m%Y"))
            current -= timedelta(days=1)
            attempts += 1
        return dates
    
    @staticmethod
    def fetch_oi_csv(date_str: str) -> Optional[pd.DataFrame]:
        """Fetch single CSV from NSE"""
        try:
            url = ParticipantDataFetcher.BASE_URL.format(date_str)
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/csv'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                logger.info(f"✅ Fetched FII data for {date_str}")
                return df
        except Exception as e:
            logger.debug(f"Failed to fetch {date_str}: {e}")
        return None
    
    @staticmethod
    def process_participant_data(df: pd.DataFrame) -> Tuple[float, float]:
        """
        Process FII/DII data
        Returns: (fii_net_contracts, dii_net_contracts)
        """
        try:
            # Filter for INDEX FUTURES (NIFTY)
            index_fut = df[df['FutureIndex'].str.contains('NIFTY', case=False, na=False)]
            
            if index_fut.empty:
                return 0.0, 0.0
            
            # Calculate net for each participant type
            fii_long = index_fut[index_fut['ClientType'] == 'Client']['LongQtyContracts'].sum()
            fii_short = index_fut[index_fut['ClientType'] == 'Client']['ShortQtyContracts'].sum()
            
            dii_long = index_fut[index_fut['ClientType'] == 'DII']['LongQtyContracts'].sum()
            dii_short = index_fut[index_fut['ClientType'] == 'DII']['ShortQtyContracts'].sum()
            
            fii_net = fii_long - fii_short
            dii_net = dii_long - dii_short
            
            logger.info(f"FII Net: {fii_net:,.0f} | DII Net: {dii_net:,.0f}")
            return fii_net, dii_net
            
        except Exception as e:
            logger.error(f"Failed to process participant data: {e}")
            return 0.0, 0.0
    
    @staticmethod
    def fetch_smart_participant_data() -> Tuple[float, float, str]:
        """
        Smart fetch with fallback
        Returns: (fii_net, dii_net, context_string)
        PRESERVED FROM ORIGINAL
        """
        dates = ParticipantDataFetcher.get_candidate_dates()
        
        for date_str in dates:
            df = ParticipantDataFetcher.fetch_oi_csv(date_str)
            if df is not None:
                fii_net, dii_net = ParticipantDataFetcher.process_participant_data(df)
                
                # Context (informational only)
                if fii_net > Config.FII_STRONG_LONG:
                    context = "FII Strong Long"
                elif fii_net < Config.FII_STRONG_SHORT:
                    context = "FII Strong Short"
                elif abs(fii_net) > Config.FII_MODERATE:
                    context = "FII Moderate Position"
                else:
                    context = "FII Neutral"
                
                return fii_net, dii_net, context
        
        logger.warning("Could not fetch FII data - using defaults")
        return 0.0, 0.0, "Data Unavailable"
