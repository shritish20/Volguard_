"""
VolGuard 3.3 - Strategy Builder
Constructs multi-leg option strategies from trading mandates
"""
from typing import Optional, List, Dict
from datetime import datetime
from config import Config
from utils.logger import logger
from core.option_searcher import OptionSearcher
from models.domain import TradingMandate


class StrategyBuilder:
    """
    Build executable strategy legs from trading mandates
    """
    
    def __init__(self, upstox_fetcher):
        """
        Args:
            upstox_fetcher: UpstoxFetcher instance
        """
        self.upstox = upstox_fetcher
        self.option_searcher = OptionSearcher(upstox_fetcher)
    
    def build_strategy(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build strategy legs based on mandate
        
        Args:
            mandate: TradingMandate with strategy type and parameters
            
        Returns:
            List[Dict]: Strategy legs or None if failed
        """
        strategy_type = mandate.suggested_structure.upper()
        
        logger.info(f"🔨 Building {strategy_type} strategy")
        
        if "IRON FLY" in strategy_type or "IRON_FLY" in strategy_type:
            return self.build_iron_fly(mandate)
        elif "IRON CONDOR" in strategy_type or "IRON_CONDOR" in strategy_type:
            return self.build_iron_condor(mandate)
        elif "CREDIT SPREAD" in strategy_type or "CREDIT_SPREAD" in strategy_type:
            return self.build_credit_spread(mandate)
        elif "SHORT STRADDLE" in strategy_type or "SHORT_STRADDLE" in strategy_type:
            return self.build_short_straddle(mandate)
        elif "RATIO SPREAD" in strategy_type or "RATIO_SPREAD" in strategy_type:
            return self.build_ratio_spread(mandate)
        else:
            logger.error(f"Unknown strategy type: {strategy_type}")
            return None
    
    def build_iron_fly(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build Iron Fly (ATM sell + OTM wings)
        
        Structure:
        - SELL ATM Call
        - SELL ATM Put
        - BUY OTM Call (wing)
        - BUY OTM Put (wing)
        
        Args:
            mandate: Trading mandate
            
        Returns:
            List[Dict]: 4 legs or None
        """
        try:
            # Get spot price
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            if not spot_price:
                logger.error("Failed to get spot price")
                return None
            
            expiry = mandate.smart_expiry_weekly if mandate.expiry_type == "WEEKLY" else mandate.smart_expiry_monthly
            
            # 1. Find ATM strike
            atm_strike = self.option_searcher.find_atm_strike(spot_price)
            
            # Validate ATM tolerance
            atm_diff_pct = abs(spot_price - atm_strike) / spot_price
            if atm_diff_pct > Config.IRON_FLY_ATM_TOLERANCE:
                logger.warning(f"ATM strike {atm_strike} is {atm_diff_pct:.2%} from spot {spot_price}")
            
            # 2. Find wing strikes
            call_wing, put_wing = self.option_searcher.find_wing_strikes_symmetric(
                atm_strike=atm_strike,
                expiry=expiry,
                min_width=Config.IRON_FLY_MIN_WING_WIDTH,
                max_width=Config.IRON_FLY_MAX_WING_WIDTH,
                target_delta=Config.IRON_FLY_WING_DELTA_TARGET
            )
            
            if not call_wing or not put_wing:
                logger.error("Failed to find wing strikes")
                return None
            
            # 3. Validate wing widths
            call_width = call_wing - atm_strike
            put_width = atm_strike - put_wing
            
            if call_width < Config.IRON_FLY_MIN_WING_WIDTH or call_width > Config.IRON_FLY_MAX_WING_WIDTH:
                logger.error(f"Call wing width {call_width} out of range")
                return None
            
            if put_width < Config.IRON_FLY_MIN_WING_WIDTH or put_width > Config.IRON_FLY_MAX_WING_WIDTH:
                logger.error(f"Put wing width {put_width} out of range")
                return None
            
            # 4. Get instrument keys and prices
            legs = []
            
            # Leg 1: SELL ATM Call
            atm_call_key = self._get_instrument_key(atm_strike, "CE", expiry)
            atm_call_ltp = self.upstox.get_ltp(atm_call_key)
            
            if not atm_call_key or not atm_call_ltp:
                logger.error("Failed to get ATM call details")
                return None
            
            legs.append({
                "side": "SELL",
                "option_type": "CE",
                "strike": atm_strike,
                "instrument_key": atm_call_key,
                "ltp": atm_call_ltp,
                "quantity": mandate.max_lots,
                "role": "SHORT_CALL",
                "expiry": expiry
            })
            
            # Leg 2: SELL ATM Put
            atm_put_key = self._get_instrument_key(atm_strike, "PE", expiry)
            atm_put_ltp = self.upstox.get_ltp(atm_put_key)
            
            if not atm_put_key or not atm_put_ltp:
                logger.error("Failed to get ATM put details")
                return None
            
            legs.append({
                "side": "SELL",
                "option_type": "PE",
                "strike": atm_strike,
                "instrument_key": atm_put_key,
                "ltp": atm_put_ltp,
                "quantity": mandate.max_lots,
                "role": "SHORT_PUT",
                "expiry": expiry
            })
            
            # Leg 3: BUY Call Wing
            call_wing_key = self._get_instrument_key(call_wing, "CE", expiry)
            call_wing_ltp = self.upstox.get_ltp(call_wing_key)
            
            if not call_wing_key or call_wing_ltp is None:
                logger.error("Failed to get call wing details")
                return None
            
            legs.append({
                "side": "BUY",
                "option_type": "CE",
                "strike": call_wing,
                "instrument_key": call_wing_key,
                "ltp": call_wing_ltp,
                "quantity": mandate.max_lots,
                "role": "LONG_CALL_WING",
                "expiry": expiry
            })
            
            # Leg 4: BUY Put Wing
            put_wing_key = self._get_instrument_key(put_wing, "PE", expiry)
            put_wing_ltp = self.upstox.get_ltp(put_wing_key)
            
            if not put_wing_key or put_wing_ltp is None:
                logger.error("Failed to get put wing details")
                return None
            
            legs.append({
                "side": "BUY",
                "option_type": "PE",
                "strike": put_wing,
                "instrument_key": put_wing_key,
                "ltp": put_wing_ltp,
                "quantity": mandate.max_lots,
                "role": "LONG_PUT_WING",
                "expiry": expiry
            })
            
            # 5. Calculate net credit/debit
            net_credit = (atm_call_ltp + atm_put_ltp - call_wing_ltp - put_wing_ltp) * mandate.max_lots * 25
            
            logger.info(f"✅ Iron Fly built: ATM {atm_strike}, Wings {put_wing}/{call_wing}, Net Credit: ₹{net_credit:,.0f}")
            
            # 6. Validate liquidity
            strikes = [atm_strike, call_wing, put_wing]
            liquid_strikes = self.option_searcher.validate_liquid_strikes(strikes, expiry)
            
            if len(liquid_strikes) < len(strikes):
                logger.warning(f"Some strikes may be illiquid: {set(strikes) - set(liquid_strikes)}")
            
            return legs
            
        except Exception as e:
            logger.error(f"Error building Iron Fly: {e}", exc_info=True)
            return None
    
    def build_iron_condor(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build Iron Condor (OTM sells + further OTM wings)
        
        Structure:
        - SELL OTM Call
        - SELL OTM Put
        - BUY Further OTM Call
        - BUY Further OTM Put
        
        Args:
            mandate: Trading mandate
            
        Returns:
            List[Dict]: 4 legs or None
        """
        try:
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            if not spot_price:
                return None
            
            expiry = mandate.smart_expiry_weekly if mandate.expiry_type == "WEEKLY" else mandate.smart_expiry_monthly
            
            atm_strike = self.option_searcher.find_atm_strike(spot_price)
            
            # For Iron Condor, sell strikes are further OTM than Iron Fly
            # Typical: Sell at 0.20-0.30 delta, Buy at 0.10 delta
            
            # Sell strikes
            sell_call_strike = self.option_searcher.find_strike_by_delta(0.25, "CE", spot_price, expiry)
            sell_put_strike = self.option_searcher.find_strike_by_delta(0.25, "PE", spot_price, expiry)
            
            if not sell_call_strike or not sell_put_strike:
                logger.error("Failed to find sell strikes for Iron Condor")
                return None
            
            # Wing width (typically 100-200 points)
            wing_width = 150
            
            buy_call_strike = sell_call_strike + wing_width
            buy_put_strike = sell_put_strike - wing_width
            
            # Round to 50
            buy_call_strike = round(buy_call_strike / 50) * 50
            buy_put_strike = round(buy_put_strike / 50) * 50
            
            # Build legs
            legs = []
            
            strikes_and_types = [
                (sell_call_strike, "CE", "SELL", "SHORT_CALL"),
                (sell_put_strike, "PE", "SELL", "SHORT_PUT"),
                (buy_call_strike, "CE", "BUY", "LONG_CALL_WING"),
                (buy_put_strike, "PE", "BUY", "LONG_PUT_WING")
            ]
            
            for strike, opt_type, side, role in strikes_and_types:
                key = self._get_instrument_key(strike, opt_type, expiry)
                ltp = self.upstox.get_ltp(key)
                
                if not key or ltp is None:
                    logger.error(f"Failed to get details for {strike} {opt_type}")
                    return None
                
                legs.append({
                    "side": side,
                    "option_type": opt_type,
                    "strike": strike,
                    "instrument_key": key,
                    "ltp": ltp,
                    "quantity": mandate.max_lots,
                    "role": role,
                    "expiry": expiry
                })
            
            net_credit = (
                legs[0]["ltp"] + legs[1]["ltp"] - legs[2]["ltp"] - legs[3]["ltp"]
            ) * mandate.max_lots * 25
            
            logger.info(f"✅ Iron Condor built: Sells {sell_put_strike}/{sell_call_strike}, Net Credit: ₹{net_credit:,.0f}")
            
            return legs
            
        except Exception as e:
            logger.error(f"Error building Iron Condor: {e}", exc_info=True)
            return None
    
    def build_credit_spread(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build Credit Spread (directional 2-leg)
        
        Bull Put Spread (bullish):
        - SELL OTM Put
        - BUY Further OTM Put
        
        Bear Call Spread (bearish):
        - SELL OTM Call
        - BUY Further OTM Call
        
        Args:
            mandate: Trading mandate
            
        Returns:
            List[Dict]: 2 legs or None
        """
        try:
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            if not spot_price:
                return None
            
            expiry = mandate.smart_expiry_weekly if mandate.expiry_type == "WEEKLY" else mandate.smart_expiry_monthly
            
            # Determine direction from mandate
            is_bullish = mandate.directional_bias.upper() in ["BULLISH", "BULL"]
            
            if is_bullish:
                # Bull Put Spread
                option_type = "PE"
                sell_delta = 0.30
                spread_width = 100
            else:
                # Bear Call Spread
                option_type = "CE"
                sell_delta = 0.30
                spread_width = 100
            
            # Find sell strike
            sell_strike = self.option_searcher.find_strike_by_delta(sell_delta, option_type, spot_price, expiry)
            
            if not sell_strike:
                logger.error("Failed to find sell strike for credit spread")
                return None
            
            # Buy strike is spread_width away
            if is_bullish:
                buy_strike = sell_strike - spread_width
            else:
                buy_strike = sell_strike + spread_width
            
            buy_strike = round(buy_strike / 50) * 50
            
            # Build legs
            legs = []
            
            for strike, side, role in [(sell_strike, "SELL", "SHORT"), (buy_strike, "BUY", "LONG")]:
                key = self._get_instrument_key(strike, option_type, expiry)
                ltp = self.upstox.get_ltp(key)
                
                if not key or ltp is None:
                    return None
                
                legs.append({
                    "side": side,
                    "option_type": option_type,
                    "strike": strike,
                    "instrument_key": key,
                    "ltp": ltp,
                    "quantity": mandate.max_lots,
                    "role": f"{role}_{option_type}",
                    "expiry": expiry
                })
            
            net_credit = (legs[0]["ltp"] - legs[1]["ltp"]) * mandate.max_lots * 25
            
            logger.info(f"✅ Credit Spread built: {sell_strike}/{buy_strike} {option_type}, Net Credit: ₹{net_credit:,.0f}")
            
            return legs
            
        except Exception as e:
            logger.error(f"Error building Credit Spread: {e}", exc_info=True)
            return None
    
    def build_short_straddle(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build Short Straddle (ATM sell both Call and Put)
        
        Structure:
        - SELL ATM Call
        - SELL ATM Put
        
        Args:
            mandate: Trading mandate
            
        Returns:
            List[Dict]: 2 legs or None
        """
        try:
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            if not spot_price:
                return None
            
            expiry = mandate.smart_expiry_weekly if mandate.expiry_type == "WEEKLY" else mandate.smart_expiry_monthly
            
            atm_strike = self.option_searcher.find_atm_strike(spot_price)
            
            legs = []
            
            for opt_type, role in [("CE", "SHORT_CALL"), ("PE", "SHORT_PUT")]:
                key = self._get_instrument_key(atm_strike, opt_type, expiry)
                ltp = self.upstox.get_ltp(key)
                
                if not key or ltp is None:
                    return None
                
                legs.append({
                    "side": "SELL",
                    "option_type": opt_type,
                    "strike": atm_strike,
                    "instrument_key": key,
                    "ltp": ltp,
                    "quantity": mandate.max_lots,
                    "role": role,
                    "expiry": expiry
                })
            
            net_credit = (legs[0]["ltp"] + legs[1]["ltp"]) * mandate.max_lots * 25
            
            logger.info(f"✅ Short Straddle built: ATM {atm_strike}, Net Credit: ₹{net_credit:,.0f}")
            
            return legs
            
        except Exception as e:
            logger.error(f"Error building Short Straddle: {e}", exc_info=True)
            return None
    
    def build_ratio_spread(self, mandate: TradingMandate) -> Optional[List[Dict]]:
        """
        Build Ratio Spread (1:2 or 1:3 ratio)
        
        Typical structure:
        - BUY 1 ATM
        - SELL 2 OTM (same side)
        
        Args:
            mandate: Trading mandate
            
        Returns:
            List[Dict]: 2 legs or None
        """
        try:
            spot_price = self.upstox.get_ltp(Config.NIFTY_KEY)
            if not spot_price:
                return None
            
            expiry = mandate.smart_expiry_weekly if mandate.expiry_type == "WEEKLY" else mandate.smart_expiry_monthly
            
            # Determine direction
            is_bullish = mandate.directional_bias.upper() in ["BULLISH", "BULL"]
            option_type = "CE" if is_bullish else "PE"
            
            atm_strike = self.option_searcher.find_atm_strike(spot_price)
            
            # OTM strike for selling (ratio)
            otm_distance = 200
            if is_bullish:
                otm_strike = atm_strike + otm_distance
            else:
                otm_strike = atm_strike - otm_distance
            
            otm_strike = round(otm_strike / 50) * 50
            
            legs = []
            
            # Leg 1: BUY 1 ATM
            key = self._get_instrument_key(atm_strike, option_type, expiry)
            ltp = self.upstox.get_ltp(key)
            
            if not key or ltp is None:
                return None
            
            legs.append({
                "side": "BUY",
                "option_type": option_type,
                "strike": atm_strike,
                "instrument_key": key,
                "ltp": ltp,
                "quantity": mandate.max_lots,
                "role": f"LONG_{option_type}",
                "expiry": expiry
            })
            
            # Leg 2: SELL 2 OTM
            key = self._get_instrument_key(otm_strike, option_type, expiry)
            ltp = self.upstox.get_ltp(key)
            
            if not key or ltp is None:
                return None
            
            legs.append({
                "side": "SELL",
                "option_type": option_type,
                "strike": otm_strike,
                "instrument_key": key,
                "ltp": ltp,
                "quantity": mandate.max_lots * 2,  # 2x ratio
                "role": f"SHORT_{option_type}",
                "expiry": expiry
            })
            
            net_credit = (legs[1]["ltp"] * 2 - legs[0]["ltp"]) * mandate.max_lots * 25
            
            logger.info(f"✅ Ratio Spread built: 1x{atm_strike}/2x{otm_strike} {option_type}, Net: ₹{net_credit:,.0f}")
            
            return legs
            
        except Exception as e:
            logger.error(f"Error building Ratio Spread: {e}", exc_info=True)
            return None
    
    def _get_instrument_key(self, strike: int, option_type: str, expiry: str) -> Optional[str]:
        """
        Construct Upstox instrument key
        
        Format: NSE_FO|NIFTY24JAN24000CE
        
        Args:
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Expiry date (YYYY-MM-DD)
            
        Returns:
            str: Instrument key or None
        """
        try:
            # Parse expiry date
            expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
            
            # Format: NIFTY{YY}{MMM}{STRIKE}{CE/PE}
            # Example: NIFTY24JAN24000CE
            
            year_short = expiry_dt.strftime("%y")
            month_short = expiry_dt.strftime("%b").upper()
            
            symbol = f"NIFTY{year_short}{month_short}{strike}{option_type}"
            
            instrument_key = f"NSE_FO|{symbol}"
            
            return instrument_key
            
        except Exception as e:
            logger.error(f"Error constructing instrument key: {e}")
            return None
    
    def validate_strategy(self, legs: List[Dict]) -> Tuple[bool, str]:
        """
        Validate strategy before execution
        
        Args:
            legs: Strategy legs
            
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        if not legs:
            return False, "No legs provided"
        
        # Check all legs have required fields
        required_fields = ["side", "option_type", "strike", "instrument_key", "ltp", "quantity"]
        
        for i, leg in enumerate(legs):
            for field in required_fields:
                if field not in leg:
                    return False, f"Leg {i} missing field: {field}"
        
        # Check reasonable prices
        for leg in legs:
            if leg["ltp"] <= 0:
                return False, f"Invalid LTP for {leg['strike']} {leg['option_type']}: {leg['ltp']}"
            
            if leg["ltp"] > 1000:
                return False, f"Unreasonably high premium: {leg['ltp']}"
        
        return True, "Valid"
