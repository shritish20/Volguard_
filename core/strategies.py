"""
Strategy Factory - COMPLETE IMPLEMENTATION FROM ORIGINAL
=========================================================
Constructs professional option strategies:
- Iron Fly (ATM straddle with wings)
- Iron Condor (OTM strangles with wings)
- Credit Spreads (Bull Put / Bear Call)

All logic preserved from P__Py__1_.txt lines 2597-2794
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import upstox_client

from config import Config
from models.domain import TradingMandate, VolMetrics, StructMetrics
from utils.logger import logger
from utils.telegram import telegram


class StrategyFactory:
    """
    COMPLETE Strategy Factory - PRODUCTION READY
    Constructs multi-leg option strategies from trading mandates
    """
    
    def __init__(self, api_client: upstox_client.ApiClient = None):
        self.api_client = api_client
        
    def _discover_strike_interval(self, df: pd.DataFrame) -> int:
        """
        Discover actual strike spacing from option chain
        Returns: Strike interval (e.g., 50, 100)
        """
        if df.empty or len(df) < 2:
            return Config.DEFAULT_STRIKE_INTERVAL
            
        strikes = sorted(df['strike'].unique())
        diffs = np.diff(strikes)
        valid_diffs = diffs[diffs > 0]
        
        if len(valid_diffs) == 0:
            return Config.DEFAULT_STRIKE_INTERVAL
            
        try:
            # Use mode (most common difference)
            return int(pd.Series(valid_diffs).mode().iloc[0])
        except:
            return Config.DEFAULT_STRIKE_INTERVAL
    
    def _find_professional_atm(self, df: pd.DataFrame, spot: float) -> Optional[Dict]:
        """
        Find professional ATM strike with minimum call-put skew
        
        Returns: {
            'strike': ATM strike,
            'straddle_cost': Call + Put premium,
            'interval': Strike spacing
        }
        """
        interval = self._discover_strike_interval(df)
        
        # Geometric ATM (rounded to interval)
        closest = int(spot / interval + 0.5) * interval
        
        # Check nearby strikes
        candidates = [closest, closest + interval, closest - interval]
        
        best_strike = None
        min_skew = float('inf')
        best_cost = 0.0
        
        for strike in candidates:
            # Find call and put at this strike
            ce = df[(df['strike'] == strike) & (df['ce_oi'] > Config.MIN_STRIKE_OI)]
            pe = df[(df['strike'] == strike) & (df['pe_oi'] > Config.MIN_STRIKE_OI)]
            
            if ce.empty or pe.empty:
                continue
                
            ce_ltp = ce.iloc[0]['ce_ltp']
            pe_ltp = pe.iloc[0]['pe_ltp']
            
            # Skip if prices are too low (illiquid)
            if ce_ltp <= 0.1 or pe_ltp <= 0.1:
                continue
                
            # Calculate skew (difference between call and put)
            skew = abs(ce_ltp - pe_ltp)
            
            # Pick strike with minimum skew (most balanced)
            if skew < min_skew:
                min_skew = skew
                best_strike = strike
                best_cost = ce_ltp + pe_ltp
        
        if not best_strike:
            logger.warning(f"Using Geometric ATM {closest} (Liquidity Low)")
            return {'strike': closest, 'straddle_cost': 0.0, 'interval': interval}
        
        logger.info(f"🎯 Pro ATM: {best_strike} (Skew: ₹{min_skew:.1f}) | Interval: {interval}")
        return {'strike': best_strike, 'straddle_cost': best_cost, 'interval': interval}
    
    def _calculate_pro_wing_width(self, straddle_cost: float, vol_metrics: VolMetrics, interval: int) -> int:
        """
        Calculate wing width based on IV percentile and straddle cost
        
        Logic:
        - Higher IVP → Wider wings (more protection)
        - Lower IVP → Tighter wings (max theta)
        - Always rounds to strike interval
        """
        # Select factor based on IV percentile
        if vol_metrics.ivp_1yr > Config.IVP_THRESHOLD_EXTREME:
            factor = Config.WING_FACTOR_EXTREME_VOL  # 1.4
        elif vol_metrics.ivp_1yr > Config.IVP_THRESHOLD_HIGH:
            factor = Config.WING_FACTOR_HIGH_VOL  # 1.1
        elif vol_metrics.ivp_1yr < Config.IVP_THRESHOLD_LOW:
            factor = Config.WING_FACTOR_LOW_VOL  # 0.8
        else:
            factor = Config.WING_FACTOR_STANDARD  # 1.0
        
        # Calculate target width
        target = straddle_cost * factor
        
        # Round to nearest interval
        rounded = int(target / interval + 0.5) * interval
        
        # Ensure minimum width
        min_width = interval * Config.MIN_WING_INTERVAL_MULTIPLIER
        final = max(min_width, rounded)
        
        logger.info(f"📏 Wing Width: Target {target:.1f} → Rounded {final} (Factor {factor})")
        return final
    
    def _get_leg_details(self, df: pd.DataFrame, strike: float, type_: str) -> Optional[Dict]:
        """
        Extract option details for a specific strike
        
        Args:
            df: Option chain
            strike: Strike price
            type_: 'CE' or 'PE'
            
        Returns: Leg dict with key, strike, ltp, delta, bid, ask
        """
        rows = df[(df['strike'] - strike).abs() < 0.1]
        if rows.empty:
            return None
            
        row = rows.iloc[0]
        pref = type_.lower()
        
        ltp = row[f'{pref}_ltp']
        if ltp <= 0:
            return None
        
        return {
            'key': row[f'{pref}_key'],
            'strike': row['strike'],
            'ltp': ltp,
            'delta': row[f'{pref}_delta'],
            'type': type_,
            'bid': row[f'{pref}_bid'],
            'ask': row[f'{pref}_ask']
        }
    
    def _find_leg_by_delta(self, df: pd.DataFrame, type_: str, target_delta: float) -> Optional[Dict]:
        """
        Find option closest to target delta
        
        Used for Iron Condor and Credit Spreads
        
        Args:
            df: Option chain
            type_: 'CE' or 'PE'
            target_delta: Target delta (e.g., 0.16 for 16-delta)
            
        Returns: Best matching leg or None
        """
        target = abs(target_delta)
        col_delta = f"{type_.lower()}_delta"
        
        # Filter for liquid options
        df = df.copy()
        df = df[
            (df[f'{type_.lower()}_oi'] > Config.MIN_STRIKE_OI) &
            (df[f'{type_.lower()}_ltp'] > 0.5)
        ]
        
        # Calculate delta difference
        df['delta_diff'] = (df[col_delta].abs() - target).abs()
        
        # Try top 3 candidates
        for _, row in df.sort_values('delta_diff').head(3).iterrows():
            bid = row[f'{type_.lower()}_bid']
            ask = row[f'{type_.lower()}_ask']
            ltp = row[f'{type_.lower()}_ltp']
            
            # Skip if illiquid
            if ltp <= 0 or ask <= 0:
                continue
            
            # Skip if spread too wide
            if (ask - bid) / ltp > Config.MAX_BID_ASK_SPREAD:
                continue
            
            return self._get_leg_details(df, row['strike'], type_)
        
        return None
    
    def _calculate_defined_risk(self, legs: List[Dict], qty: int) -> float:
        """
        Calculate exact max loss for defined-risk strategy
        
        Formula: Max(CallWidth, PutWidth) - NetCredit
        
        This is CRITICAL - determines actual capital at risk
        """
        if not legs:
            return 0.0
        
        # Calculate net credit/debit
        premiums = sum(l['ltp'] * l['qty'] for l in legs if l['side'] == 'SELL')
        debits = sum(l['ltp'] * l['qty'] for l in legs if l['side'] == 'BUY')
        net_credit = premiums - debits
        
        # Separate call and put legs
        ce_legs = sorted([l for l in legs if l['type'] == 'CE'], key=lambda x: x['strike'])
        pe_legs = sorted([l for l in legs if l['type'] == 'PE'], key=lambda x: x['strike'])
        
        call_risk = 0.0
        put_risk = 0.0
        
        # Calculate call side risk
        if len(ce_legs) >= 2:
            shorts = [l for l in ce_legs if l['side'] == 'SELL']
            longs = [l for l in ce_legs if l['side'] == 'BUY']
            
            if shorts and longs:
                # Width = Long strike - Short strike
                width = longs[-1]['strike'] - shorts[0]['strike']
                call_risk = width * qty
        
        # Calculate put side risk
        if len(pe_legs) >= 2:
            shorts = [l for l in pe_legs if l['side'] == 'SELL']
            longs = [l for l in pe_legs if l['side'] == 'BUY']
            
            if shorts and longs:
                # Width = Short strike - Long strike
                width = shorts[-1]['strike'] - longs[0]['strike']
                put_risk = width * qty
        
        # Max loss = Worst side - Net credit
        max_structural_risk = max(call_risk, put_risk)
        max_loss = max(0, max_structural_risk - net_credit)
        
        logger.info(
            f"🧮 Risk Calc: CallRisk={call_risk:.0f}, PutRisk={put_risk:.0f}, "
            f"Credit={net_credit:.0f} → MaxLoss={max_loss:.0f}"
        )
        
        return max_loss
    
    def generate(
        self,
        mandate: TradingMandate,
        chain: pd.DataFrame,
        lot_size: int,
        vol_metrics: VolMetrics,
        spot: float,
        struct_metrics: StructMetrics
    ) -> Tuple[List[Dict], float]:
        """
        MAIN ENTRY POINT - Generate strategy legs from mandate
        
        Args:
            mandate: Trading mandate with strategy type
            chain: Option chain DataFrame
            lot_size: Contract lot size (e.g., 50 for NIFTY)
            vol_metrics: Volatility metrics
            spot: Current spot price
            struct_metrics: Structure metrics
            
        Returns:
            (legs, max_loss) where legs is list of leg dicts, max_loss is rupees
            Returns ([], 0.0) if strategy cannot be constructed
        """
        if mandate.max_lots == 0 or chain.empty:
            return [], 0.0
        
        qty = mandate.max_lots * lot_size
        legs = []
        
        # =====================================================================
        # 1. IRON FLY
        # =====================================================================
        if mandate.suggested_structure == "IRON_FLY":
            logger.info(f"🦅 Constructing Iron Fly | DTE={mandate.dte} | Spot={spot:.2f}")
            
            # Find ATM strike
            atm_data = self._find_professional_atm(chain, spot)
            if not atm_data:
                return [], 0.0
            
            atm_strike = atm_data['strike']
            straddle_cost = atm_data['straddle_cost']
            interval = atm_data['interval']
            
            # Calculate wing width
            wing_width = self._calculate_pro_wing_width(straddle_cost, vol_metrics, interval)
            
            upper_wing = atm_strike + wing_width
            lower_wing = atm_strike - wing_width
            
            # Get all 4 legs
            atm_call = self._get_leg_details(chain, atm_strike, 'CE')
            atm_put = self._get_leg_details(chain, atm_strike, 'PE')
            wing_call = self._get_leg_details(chain, upper_wing, 'CE')
            wing_put = self._get_leg_details(chain, lower_wing, 'PE')
            
            if not all([atm_call, atm_put, wing_call, wing_put]):
                logger.error("Iron Fly incomplete: Missing liquid strikes")
                return [], 0.0
            
            # Construct legs
            legs = [
                {**atm_call, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'IRON_FLY'},
                {**atm_put, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'IRON_FLY'},
                {**wing_call, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'IRON_FLY'},
                {**wing_put, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'IRON_FLY'}
            ]
        
        # =====================================================================
        # 2. IRON CONDOR
        # =====================================================================
        elif mandate.suggested_structure == "IRON_CONDOR":
            logger.info(f"🦅 Constructing Iron Condor | DTE={mandate.dte}")
            
            # Select delta based on expiry type
            short_delta = (
                Config.DELTA_SHORT_MONTHLY if mandate.expiry_type == "MONTHLY"
                else Config.DELTA_SHORT_WEEKLY
            )
            
            # Find all 4 legs by delta
            short_call = self._find_leg_by_delta(chain, 'CE', short_delta)
            short_put = self._find_leg_by_delta(chain, 'PE', short_delta)
            long_call = self._find_leg_by_delta(chain, 'CE', Config.DELTA_LONG_HEDGE)
            long_put = self._find_leg_by_delta(chain, 'PE', Config.DELTA_LONG_HEDGE)
            
            if not all([short_call, short_put, long_call, long_put]):
                logger.error("Iron Condor incomplete")
                return [], 0.0
            
            # Construct legs
            legs = [
                {**short_call, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'IRON_CONDOR'},
                {**short_put, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'IRON_CONDOR'},
                {**long_call, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'IRON_CONDOR'},
                {**long_put, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'IRON_CONDOR'}
            ]
        
        # =====================================================================
        # 3. DIRECTIONAL CREDIT SPREADS
        # =====================================================================
        elif mandate.suggested_structure in ["CREDIT_SPREAD", "BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"]:
            
            # Determine direction
            is_uptrend = vol_metrics.spot_price > vol_metrics.ma20 * (1 + Config.TREND_BULLISH_THRESHOLD / 100)
            is_bullish_pcr = struct_metrics.pcr > Config.PCR_BULLISH_THRESHOLD
            
            if is_uptrend or mandate.directional_bias in ["BULLISH", "MILDLY_BULLISH"]:
                # BULL PUT SPREAD
                logger.info("📈 Direction: BULLISH. Deploying BULL PUT SPREAD.")
                
                short = self._find_leg_by_delta(chain, 'PE', Config.DELTA_CREDIT_SHORT)
                long = self._find_leg_by_delta(chain, 'PE', Config.DELTA_CREDIT_LONG)
                
                if not all([short, long]):
                    return [], 0.0
                
                legs = [
                    {**short, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'BULL_PUT_SPREAD'},
                    {**long, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'BULL_PUT_SPREAD'}
                ]
            
            else:
                # BEAR CALL SPREAD
                logger.info("📉 Direction: BEARISH. Deploying BEAR CALL SPREAD.")
                
                short = self._find_leg_by_delta(chain, 'CE', Config.DELTA_CREDIT_SHORT)
                long = self._find_leg_by_delta(chain, 'CE', Config.DELTA_CREDIT_LONG)
                
                if not all([short, long]):
                    return [], 0.0
                
                legs = [
                    {**short, 'side': 'SELL', 'role': 'CORE', 'qty': qty, 'structure': 'BEAR_CALL_SPREAD'},
                    {**long, 'side': 'BUY', 'role': 'HEDGE', 'qty': qty, 'structure': 'BEAR_CALL_SPREAD'}
                ]
        
        # =====================================================================
        # VALIDATION
        # =====================================================================
        if not legs:
            return [], 0.0
        
        # Validate all leg prices
        for leg in legs:
            if leg['ltp'] <= 0:
                logger.error(f"❌ Invalid Leg Price: {leg['strike']} = {leg['ltp']}")
                return [], 0.0
        
        # =====================================================================
        # CRITICAL: MAX LOSS CHECK
        # =====================================================================
        max_risk = self._calculate_defined_risk(legs, qty)
        
        if max_risk > Config.MAX_LOSS_PER_TRADE:
            logger.critical(
                f"⛔ Trade Rejected: Max Risk ₹{max_risk:,.2f} > "
                f"Limit ₹{Config.MAX_LOSS_PER_TRADE:,.2f}"
            )
            telegram.send(f"Trade Rejected: Risk ₹{max_risk:,.0f} exceeds limit", "WARNING")
            return [], 0.0
        
        return legs, max_risk
