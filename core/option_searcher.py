"""
VolGuard 3.3 - Option Searcher
Intelligent strike selection for multi-leg strategies
"""
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import pandas as pd
from config import Config
from utils.logger import logger


class OptionSearcher:
    """
    Find optimal option strikes based on various criteria
    """
    
    def __init__(self, upstox_fetcher):
        """
        Args:
            upstox_fetcher: UpstoxFetcher instance
        """
        self.upstox = upstox_fetcher
    
    def find_atm_strike(self, spot_price: float) -> int:
        """
        Find ATM (At-The-Money) strike
        
        Args:
            spot_price: Current spot price
            
        Returns:
            int: ATM strike (rounded to nearest 50)
        """
        # Round to nearest 50
        atm = round(spot_price / 50) * 50
        logger.debug(f"ATM strike for spot {spot_price}: {atm}")
        return int(atm)
    
    def find_strike_by_delta(
        self, 
        target_delta: float,
        option_type: str,
        spot_price: float,
        expiry: str,
        tolerance: float = 0.05
    ) -> Optional[int]:
        """
        Find strike closest to target delta
        
        Args:
            target_delta: Target delta (e.g., 0.10 for wing)
            option_type: "CE" or "PE"
            spot_price: Current spot price
            expiry: Expiry date (YYYY-MM-DD)
            tolerance: Delta tolerance (default 0.05)
            
        Returns:
            int: Strike price or None
        """
        try:
            # Get option chain
            chain_df = self.upstox.get_option_chain(expiry)
            
            if chain_df is None or chain_df.empty:
                logger.error(f"No option chain data for expiry {expiry}")
                return None
            
            # Filter by option type
            options = chain_df[chain_df['option_type'] == option_type].copy()
            
            if options.empty:
                logger.error(f"No {option_type} options found")
                return None
            
            # Calculate delta for each option
            # Note: If Upstox provides delta directly, use it
            # Otherwise, approximate using Black-Scholes
            if 'delta' not in options.columns:
                from core.greeks import GreeksCalculator
                greeks_calc = GreeksCalculator()
                
                options['calculated_delta'] = options.apply(
                    lambda row: greeks_calc.calculate_delta(
                        spot=spot_price,
                        strike=row['strike_price'],
                        time_to_expiry=self._calculate_dte(expiry) / 365,
                        volatility=row.get('iv', 20) / 100,  # IV in decimal
                        option_type=option_type,
                        rate=0.07  # Risk-free rate
                    ),
                    axis=1
                )
                delta_col = 'calculated_delta'
            else:
                delta_col = 'delta'
            
            # For puts, delta is negative, so use absolute value
            options['abs_delta'] = options[delta_col].abs()
            
            # Find closest to target
            options['delta_diff'] = (options['abs_delta'] - abs(target_delta)).abs()
            
            # Filter by tolerance
            valid_options = options[options['delta_diff'] <= tolerance]
            
            if valid_options.empty:
                logger.warning(f"No strikes found within delta tolerance {tolerance} for target {target_delta}")
                # Return closest anyway
                closest = options.loc[options['delta_diff'].idxmin()]
            else:
                closest = valid_options.loc[valid_options['delta_diff'].idxmin()]
            
            strike = int(closest['strike_price'])
            actual_delta = closest['abs_delta']
            
            logger.info(f"Found strike {strike} for target delta {target_delta} (actual: {actual_delta:.3f})")
            
            return strike
            
        except Exception as e:
            logger.error(f"Error finding strike by delta: {e}", exc_info=True)
            return None
    
    def find_strike_by_premium(
        self,
        target_premium: float,
        option_type: str,
        spot_price: float,
        expiry: str,
        tolerance_pct: float = 0.10
    ) -> Optional[int]:
        """
        Find strike closest to target premium
        
        Args:
            target_premium: Target premium price
            option_type: "CE" or "PE"
            spot_price: Current spot price
            expiry: Expiry date
            tolerance_pct: Tolerance as percentage (default 10%)
            
        Returns:
            int: Strike price or None
        """
        try:
            chain_df = self.upstox.get_option_chain(expiry)
            
            if chain_df is None or chain_df.empty:
                return None
            
            # Filter by option type
            options = chain_df[chain_df['option_type'] == option_type].copy()
            
            # Calculate premium difference
            options['premium_diff'] = (options['ltp'] - target_premium).abs()
            
            # Filter by tolerance
            tolerance = target_premium * tolerance_pct
            valid_options = options[options['premium_diff'] <= tolerance]
            
            if valid_options.empty:
                # Return closest
                closest = options.loc[options['premium_diff'].idxmin()]
            else:
                closest = valid_options.loc[valid_options['premium_diff'].idxmin()]
            
            strike = int(closest['strike_price'])
            actual_premium = closest['ltp']
            
            logger.info(f"Found strike {strike} for target premium {target_premium} (actual: {actual_premium})")
            
            return strike
            
        except Exception as e:
            logger.error(f"Error finding strike by premium: {e}", exc_info=True)
            return None
    
    def find_otm_strike(
        self,
        spot_price: float,
        option_type: str,
        distance_points: int,
        expiry: str
    ) -> Optional[int]:
        """
        Find OTM (Out-of-The-Money) strike at specific distance
        
        Args:
            spot_price: Current spot price
            option_type: "CE" or "PE"
            distance_points: Points away from spot (e.g., 200)
            expiry: Expiry date
            
        Returns:
            int: Strike price or None
        """
        atm = self.find_atm_strike(spot_price)
        
        if option_type == "CE":
            # Call: ATM + distance
            otm_strike = atm + distance_points
        else:  # PE
            # Put: ATM - distance
            otm_strike = atm - distance_points
        
        # Round to nearest 50
        otm_strike = round(otm_strike / 50) * 50
        
        logger.debug(f"OTM {option_type} strike {distance_points} points away: {otm_strike}")
        
        return int(otm_strike)
    
    def validate_liquid_strikes(
        self,
        strikes: List[int],
        expiry: str,
        min_oi: int = 1000,
        max_spread_pct: float = 0.05
    ) -> List[int]:
        """
        Filter out illiquid strikes
        
        Args:
            strikes: List of strike prices to validate
            expiry: Expiry date
            min_oi: Minimum open interest required
            max_spread_pct: Maximum bid-ask spread percentage
            
        Returns:
            List[int]: Liquid strikes only
        """
        try:
            chain_df = self.upstox.get_option_chain(expiry)
            
            if chain_df is None or chain_df.empty:
                logger.warning("No option chain for liquidity validation")
                return strikes
            
            liquid_strikes = []
            
            for strike in strikes:
                # Find options for this strike
                strike_options = chain_df[chain_df['strike_price'] == strike]
                
                if strike_options.empty:
                    logger.warning(f"Strike {strike} not found in chain")
                    continue
                
                # Check both CE and PE
                valid = True
                
                for _, option in strike_options.iterrows():
                    # Check open interest
                    oi = option.get('oi', 0)
                    if oi < min_oi:
                        logger.debug(f"Strike {strike} {option['option_type']} failed OI check: {oi} < {min_oi}")
                        valid = False
                        break
                    
                    # Check bid-ask spread
                    bid = option.get('bid', 0)
                    ask = option.get('ask', 0)
                    ltp = option.get('ltp', 0)
                    
                    if ltp > 0 and ask > bid:
                        spread_pct = (ask - bid) / ltp
                        if spread_pct > max_spread_pct:
                            logger.debug(f"Strike {strike} {option['option_type']} failed spread check: {spread_pct:.2%}")
                            valid = False
                            break
                
                if valid:
                    liquid_strikes.append(strike)
            
            logger.info(f"Liquid strikes: {len(liquid_strikes)}/{len(strikes)}")
            
            return liquid_strikes
            
        except Exception as e:
            logger.error(f"Error validating liquid strikes: {e}", exc_info=True)
            return strikes  # Return all if validation fails
    
    def get_strike_info(
        self,
        strike: int,
        option_type: str,
        expiry: str
    ) -> Optional[Dict]:
        """
        Get detailed info for a specific strike
        
        Args:
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Expiry date
            
        Returns:
            Dict: Strike info or None
        """
        try:
            chain_df = self.upstox.get_option_chain(expiry)
            
            if chain_df is None or chain_df.empty:
                return None
            
            option = chain_df[
                (chain_df['strike_price'] == strike) & 
                (chain_df['option_type'] == option_type)
            ]
            
            if option.empty:
                return None
            
            info = option.iloc[0].to_dict()
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting strike info: {e}")
            return None
    
    def find_wing_strikes_symmetric(
        self,
        atm_strike: int,
        expiry: str,
        min_width: int = 100,
        max_width: int = 400,
        target_delta: float = 0.10
    ) -> Optional[Tuple[int, int]]:
        """
        Find symmetric wing strikes for Iron Fly
        
        Args:
            atm_strike: ATM strike price
            expiry: Expiry date
            min_width: Minimum wing width (points)
            max_width: Maximum wing width (points)
            target_delta: Target delta for wings
            
        Returns:
            Tuple[int, int]: (call_wing, put_wing) or None
        """
        spot_price = atm_strike  # Approximate
        
        # Try to find by delta first
        call_wing = self.find_strike_by_delta(target_delta, "CE", spot_price, expiry)
        put_wing = self.find_strike_by_delta(target_delta, "PE", spot_price, expiry)
        
        if call_wing and put_wing:
            call_width = call_wing - atm_strike
            put_width = atm_strike - put_wing
            
            # Validate widths
            if min_width <= call_width <= max_width and min_width <= put_width <= max_width:
                logger.info(f"Found symmetric wings: Call {call_wing} (+{call_width}), Put {put_wing} (-{put_width})")
                return (call_wing, put_wing)
        
        # Fallback: Use fixed width
        logger.warning("Delta-based wings not found, using fixed width")
        
        # Use middle of range
        wing_width = (min_width + max_width) // 2
        wing_width = round(wing_width / 50) * 50  # Round to 50
        
        call_wing = atm_strike + wing_width
        put_wing = atm_strike - wing_width
        
        return (call_wing, put_wing)
    
    def _calculate_dte(self, expiry: str) -> int:
        """
        Calculate days to expiry
        
        Args:
            expiry: Expiry date string (YYYY-MM-DD)
            
        Returns:
            int: Days to expiry
        """
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            today = datetime.now().date()
            dte = (expiry_date - today).days
            return max(0, dte)
        except:
            return 7  # Default fallback
