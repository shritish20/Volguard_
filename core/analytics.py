"""
Analytics Engine - COMPLETE LOGIC PRESERVED FROM ORIGINAL
All volatility, structure, and edge calculations with FULL complexity
NOT THE SIMPLIFIED MVP VERSION
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from arch import arch_model
from scipy.stats import norm
from config import Config
from utils.logger import logger
from core.upstox import UpstoxFetcher
from models.domain import VolMetrics, StructMetrics, EdgeMetrics, ExternalMetrics

class AnalyticsEngine:
    """Market analytics with ALL metrics preserved from original v3.3"""
    
    def __init__(self, fetcher: UpstoxFetcher):
        self.fetcher = fetcher
        
    def get_vol_metrics(self, nifty_hist: pd.DataFrame = None, vix_hist: pd.DataFrame = None) -> Optional[VolMetrics]:
        """
        Calculate ALL volatility metrics - COMPLETE VERSION FROM ORIGINAL
        
        Includes:
        - Historical volatility (7, 28, 90 day)
        - GARCH forecasts (7 and 28 day)
        - Parkinson volatility (7 and 28 day)
        - VoV (Volatility of Volatility) with z-score
        - IV Percentile (30d, 90d, 1yr)
        - VIX momentum classification
        - Trend strength via ATR
        - Volatility regime classification
        """
        try:
            # Fetch historical data if not provided
            if nifty_hist is None:
                nifty_hist = self.fetcher.get_historical_data(Config.NIFTY_KEY, interval="day", days=365)
            if vix_hist is None:
                vix_hist = self.fetcher.get_historical_data(Config.VIX_KEY, interval="day", days=365)
                
            if nifty_hist is None or len(nifty_hist) < 252:
                logger.error("Insufficient NIFTY historical data")
                return None
            if vix_hist is None or len(vix_hist) < 252:
                logger.error("Insufficient VIX historical data")
                return None
                
            # Get current live prices
            spot_price = self.fetcher.get_ltp(Config.NIFTY_KEY)
            vix = self.fetcher.get_ltp(Config.VIX_KEY)
            
            # Fallback to last close if live not available
            is_fallback = False
            if not spot_price or spot_price <= 0:
                spot_price = nifty_hist.iloc[-1]['close']
                is_fallback = True
            if not vix or vix <= 0:
                vix = vix_hist.iloc[-1]['close']
                is_fallback = True
                
            # Calculate log returns
            returns = np.log(nifty_hist['close'] / nifty_hist['close'].shift(1)).dropna()
            
            # ========================================
            # REALIZED VOLATILITY (Multiple Windows)
            # ========================================
            rv7 = returns.rolling(7).std().iloc[-1] * np.sqrt(252) * 100 if len(returns) >= 7 else 0
            rv28 = returns.rolling(28).std().iloc[-1] * np.sqrt(252) * 100 if len(returns) >= 28 else 0
            rv90 = returns.rolling(90).std().iloc[-1] * np.sqrt(252) * 100 if len(returns) >= 90 else 0
            
            # ========================================
            # GARCH VOLATILITY FORECASTS
            # ========================================
            def fit_garch(horizon: int) -> float:
                """Fit GARCH(1,1) model and forecast volatility"""
                try:
                    if len(returns) < 100:
                        return 0
                    # Use recent 252 days for model
                    model = arch_model(returns.tail(252) * 100, vol='Garch', p=1, q=1, dist='normal')
                    result = model.fit(disp='off', show_warning=False)
                    forecast = result.forecast(horizon=horizon, reindex=False)
                    # Annualize the forecast variance
                    forecast_vol = np.sqrt(forecast.variance.values[-1, -1]) * np.sqrt(252)
                    return forecast_vol
                except Exception as e:
                    logger.warning(f"GARCH fit failed for horizon {horizon}: {e}")
                    return 0
                    
            garch7 = fit_garch(7) or rv7
            garch28 = fit_garch(28) or rv28
            
            # ========================================
            # PARKINSON VOLATILITY (Using High-Low Range)
            # ========================================
            # Parkinson estimator: more efficient than close-to-close
            # σ² = (1/(4ln2)) * E[(ln(H/L))²]
            const = 1.0 / (4.0 * np.log(2.0))
            
            if 'high' in nifty_hist.columns and 'low' in nifty_hist.columns:
                park7 = np.sqrt((np.log(nifty_hist['high'] / nifty_hist['low']) ** 2).tail(7).mean() * const) * np.sqrt(252) * 100 if len(nifty_hist) >= 7 else 0
                park28 = np.sqrt((np.log(nifty_hist['high'] / nifty_hist['low']) ** 2).tail(28).mean() * const) * np.sqrt(252) * 100 if len(nifty_hist) >= 28 else 0
            else:
                park7 = rv7
                park28 = rv28
                
            # ========================================
            # VOL-OF-VOL (VoV) with Z-Score
            # ========================================
            vix_returns = np.log(vix_hist['close'] / vix_hist['close'].shift(1)).dropna()
            
            # Current VoV (30-day rolling std of VIX returns)
            vov = vix_returns.rolling(30).std().iloc[-1] * np.sqrt(252) * 100 if len(vix_returns) >= 30 else 0
            
            # Historical VoV statistics for z-score
            vov_rolling = vix_returns.rolling(30).std() * np.sqrt(252) * 100 if len(vix_returns) >= 30 else pd.Series()
            vov_mean = vov_rolling.rolling(60).mean().iloc[-1] if len(vov_rolling) >= 60 else vov
            vov_std = vov_rolling.rolling(60).std().iloc[-1] if len(vov_rolling) >= 60 else 1.0
            
            # Calculate z-score (how many standard deviations from mean)
            vov_zscore = (vov - vov_mean) / vov_std if vov_std > 0 else 0
            
            # ========================================
            # IMPLIED VOLATILITY PERCENTILE (IVP)
            # ========================================
            def calc_ivp(window: int) -> float:
                """Calculate IV percentile over given window"""
                if len(vix_hist) < window:
                    return 0.0
                history = vix_hist['close'].tail(window)
                return (history < vix).mean() * 100
                
            ivp_30d = calc_ivp(30)
            ivp_90d = calc_ivp(90)
            ivp_1yr = calc_ivp(252)
            
            # ========================================
            # TREND STRENGTH (ATR-based)
            # ========================================
            ma20 = nifty_hist['close'].rolling(20).mean().iloc[-1] if len(nifty_hist) >= 20 else spot_price
            
            # True Range calculation
            true_range = pd.concat([
                nifty_hist['high'] - nifty_hist['low'],
                (nifty_hist['high'] - nifty_hist['close'].shift(1)).abs(),
                (nifty_hist['low'] - nifty_hist['close'].shift(1)).abs()
            ], axis=1).max(axis=1)
            
            atr14 = true_range.rolling(14).mean().iloc[-1] if len(true_range) >= 14 else 0
            
            # Trend strength: distance from MA relative to ATR
            trend_strength = abs(spot_price - ma20) / atr14 if atr14 > 0 else 0
            
            # ========================================
            # VIX MOMENTUM CLASSIFICATION
            # ========================================
            vix_5d_ago = vix_hist['close'].iloc[-6] if len(vix_hist) >= 6 else vix
            vix_change_5d = vix - vix_5d_ago
            
            # Classify momentum based on thresholds from Config
            if vix_change_5d > Config.VIX_MOMENTUM_BREAKOUT:
                vix_momentum = "EXPLOSIVE_UP"
            elif vix_change_5d < -Config.VIX_MOMENTUM_BREAKOUT:
                vix_momentum = "COLLAPSING"
            elif vix_change_5d > 2.0:
                vix_momentum = "RISING"
            elif vix_change_5d < -2.0:
                vix_momentum = "FALLING"
            else:
                vix_momentum = "STABLE"
                
            # ========================================
            # VOLATILITY REGIME CLASSIFICATION
            # ========================================
            if vov_zscore > Config.VOV_CRASH_ZSCORE:
                vol_regime = "EXPLODING"  # Extreme volatility of volatility
            elif ivp_1yr > Config.HIGH_VOL_IVP:
                vol_regime = "RICH"  # High IV percentile
            elif ivp_1yr < Config.LOW_VOL_IVP:
                vol_regime = "CHEAP"  # Low IV percentile
            else:
                vol_regime = "FAIR"  # Normal regime
                
            # ========================================
            # CONSTRUCT METRICS OBJECT
            # ========================================
            return VolMetrics(
                spot_price=spot_price,
                vix=vix,
                rv7=rv7,
                rv28=rv28,
                rv90=rv90,
                garch7=garch7,
                garch28=garch28,
                parkinson7=park7,
                parkinson28=park28,
                vov=vov,
                vov_zscore=vov_zscore,
                ivp_30d=ivp_30d,
                ivp_90d=ivp_90d,
                ivp_1yr=ivp_1yr,
                ma20=ma20,
                atr14=atr14,
                trend_strength=trend_strength,
                vol_regime=vol_regime,
                is_fallback=is_fallback,
                vix_change_5d=vix_change_5d,
                vix_momentum=vix_momentum
            )
            
        except Exception as e:
            logger.error(f"Vol metrics calculation failed: {e}", exc_info=True)
            return None
            
    def get_struct_metrics(self, option_chain: pd.DataFrame, spot: float, lot_size: int) -> Optional[StructMetrics]:
        """
        Calculate COMPLETE structure metrics - FULL VERSION FROM ORIGINAL
        
        Includes:
        - Gamma Exposure (GEX) calculation
        - GEX sticky ratio
        - Put-Call Ratio (total and ATM)
        - 25-delta skew
        - Max Pain level
        - ATM IV
        - GEX regime classification
        - Skew regime classification
        """
        try:
            if option_chain.empty or spot == 0:
                logger.warning("Empty option chain or invalid spot price")
                return StructMetrics(
                    gamma_exposure=0,
                    gex_sticky_level=0,
                    gex_ratio=0,
                    gex_regime="NEUTRAL",
                    pcr=1.0,
                    pcr_atm=1.0,
                    skew_25delta=0,
                    skew_regime="NEUTRAL",
                    max_pain=spot,
                    atm_iv=20.0,
                    lot_size=lot_size
                )
                
            # ========================================
            # GAMMA EXPOSURE (GEX) CALCULATION
            # ========================================
            # GEX = Σ (OI × Gamma × Spot² × 0.01)
            # Market makers hedge gamma, creates support/resistance
            
            total_call_gex = 0
            total_put_gex = 0
            
            for _, row in option_chain.iterrows():
                strike = row['strike']
                
                # Call GEX (positive for market makers when they're short)
                call_oi = row.get('ce_oi', 0)
                call_gamma = row.get('ce_gamma', 0)
                if call_oi > 0 and call_gamma > 0:
                    call_gex = call_oi * call_gamma * (spot ** 2) * 0.01
                    total_call_gex += call_gex
                    
                # Put GEX (negative for market makers when they're short)
                put_oi = row.get('pe_oi', 0)
                put_gamma = row.get('pe_gamma', 0)
                if put_oi > 0 and put_gamma > 0:
                    put_gex = put_oi * put_gamma * (spot ** 2) * 0.01
                    total_put_gex += put_gex
                    
            # Net GEX (positive = resistance above, negative = support below)
            net_gex = total_call_gex - total_put_gex
            
            # GEX sticky ratio (measure of price stickiness)
            gex_ratio = abs(net_gex) / (spot ** 2) if spot > 0 else 0
            
            # Find GEX concentration level
            gex_by_strike = {}
            for _, row in option_chain.iterrows():
                strike = row['strike']
                strike_gex = 0
                
                if row.get('ce_oi', 0) > 0:
                    strike_gex += row.get('ce_oi', 0) * row.get('ce_gamma', 0) * (spot ** 2) * 0.01
                if row.get('pe_oi', 0) > 0:
                    strike_gex -= row.get('pe_oi', 0) * row.get('pe_gamma', 0) * (spot ** 2) * 0.01
                    
                gex_by_strike[strike] = abs(strike_gex)
                
            # Find strike with max GEX concentration
            if gex_by_strike:
                gex_sticky_level = max(gex_by_strike, key=gex_by_strike.get)
            else:
                gex_sticky_level = spot
                
            # GEX regime classification
            if gex_ratio > Config.GEX_STICKY_RATIO:
                gex_regime = "STICKY"  # High GEX = price tends to stick
            else:
                gex_regime = "SLIPPERY"  # Low GEX = price can move freely
                
            # ========================================
            # PUT-CALL RATIOS
            # ========================================
            # Total PCR (all strikes)
            total_put_oi = option_chain['pe_oi'].sum()
            total_call_oi = option_chain['ce_oi'].sum()
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
            
            # ATM PCR (strikes within 2% of spot)
            atm_range = spot * 0.02
            atm_chain = option_chain[
                (option_chain['strike'] >= spot - atm_range) &
                (option_chain['strike'] <= spot + atm_range)
            ]
            
            if not atm_chain.empty:
                atm_put_oi = atm_chain['pe_oi'].sum()
                atm_call_oi = atm_chain['ce_oi'].sum()
                pcr_atm = atm_put_oi / atm_call_oi if atm_call_oi > 0 else 1.0
            else:
                pcr_atm = pcr
                
            # ========================================
            # VOLATILITY SKEW (25-Delta)
            # ========================================
            # Skew = IV(25Δ Put) - IV(25Δ Call)
            # Positive skew = fear of downside (crash protection expensive)
            
            # Find 25-delta options
            target_delta = 0.25
            
            # Find closest call to -0.25 delta (OTM call)
            call_chain = option_chain[
                (option_chain['ce_delta'].abs() > 0.20) &
                (option_chain['ce_delta'].abs() < 0.30) &
                (option_chain['ce_iv'] > 0)
            ].copy()
            
            # Find closest put to -0.25 delta (OTM put)  
            put_chain = option_chain[
                (option_chain['pe_delta'].abs() > 0.20) &
                (option_chain['pe_delta'].abs() < 0.30) &
                (option_chain['pe_iv'] > 0)
            ].copy()
            
            if not call_chain.empty and not put_chain.empty:
                call_chain['delta_diff'] = (call_chain['ce_delta'].abs() - target_delta).abs()
                put_chain['delta_diff'] = (put_chain['pe_delta'].abs() - target_delta).abs()
                
                otm_call = call_chain.nsmallest(1, 'delta_diff').iloc[0]
                otm_put = put_chain.nsmallest(1, 'delta_diff').iloc[0]
                
                put_iv = otm_put['pe_iv']
                call_iv = otm_call['ce_iv']
                
                skew_25delta = put_iv - call_iv
            else:
                skew_25delta = 0
                
            # Skew regime classification
            # High positive skew = crash fear (puts expensive)
            # Negative skew = melt-up fear (calls expensive)
            if skew_25delta > Config.SKEW_CRASH_FEAR:
                skew_regime = "CRASH_FEAR"
            elif skew_25delta < Config.SKEW_MELT_UP:
                skew_regime = "MELT_UP"
            else:
                skew_regime = "BALANCED"
                
            # ========================================
            # MAX PAIN CALCULATION
            # ========================================
            # Max Pain = strike where option sellers have minimum loss
            # Calculate total loss for option writers at each strike
            
            max_pain_by_strike = {}
            
            for strike in option_chain['strike'].unique():
                call_loss = 0
                put_loss = 0
                
                for _, row in option_chain.iterrows():
                    row_strike = row['strike']
                    
                    # Call writer loss if spot > strike at expiry
                    if strike > row_strike:
                        call_loss += row.get('ce_oi', 0) * (strike - row_strike)
                        
                    # Put writer loss if spot < strike at expiry
                    if strike < row_strike:
                        put_loss += row.get('pe_oi', 0) * (row_strike - strike)
                        
                max_pain_by_strike[strike] = call_loss + put_loss
                
            # Find strike with minimum pain
            if max_pain_by_strike:
                max_pain = min(max_pain_by_strike, key=max_pain_by_strike.get)
            else:
                max_pain = spot
                
            # ========================================
            # ATM IMPLIED VOLATILITY
            # ========================================
            # Find ATM strike
            atm_strikes = option_chain[
                (option_chain['strike'] - spot).abs() < spot * 0.01
            ]
            
            if not atm_strikes.empty:
                atm_row = atm_strikes.iloc[0]
                # Average of ATM call and put IV
                atm_iv = (atm_row.get('ce_iv', 20) + atm_row.get('pe_iv', 20)) / 2
            else:
                atm_iv = 20.0  # Default fallback
                
            # ========================================
            # CONSTRUCT METRICS OBJECT
            # ========================================
            return StructMetrics(
                gamma_exposure=net_gex,
                gex_sticky_level=gex_sticky_level,
                gex_ratio=gex_ratio,
                gex_regime=gex_regime,
                pcr=pcr,
                pcr_atm=pcr_atm,
                skew_25delta=skew_25delta,
                skew_regime=skew_regime,
                max_pain=max_pain,
                atm_iv=atm_iv,
                lot_size=lot_size
            )
            
        except Exception as e:
            logger.error(f"Struct metrics calculation failed: {e}", exc_info=True)
            return None
            
    def get_edge_metrics(self, vol_metrics: VolMetrics, weekly_dte: int, monthly_dte: int, next_weekly_dte: int) -> Optional[EdgeMetrics]:
        """
        Calculate COMPLETE edge metrics - FULL VERSION FROM ORIGINAL
        
        Includes:
        - Volatility Risk Premium (VRP) - realized vs implied
        - Weighted VRP for each expiry (accounts for DTE decay)
        - Term structure edge
        - Smart expiry selection
        """
        try:
            if not vol_metrics:
                logger.error("Vol metrics required for edge calculation")
                return None
                
            # ========================================
            # VOLATILITY RISK PREMIUM (VRP)
            # ========================================
            # VRP = Implied Vol (VIX) - Realized Vol
            # Positive VRP = selling premium is profitable on average
            
            # Use 28-day realized vol as baseline (matches typical monthly option)
            realized_vol = vol_metrics.rv28
            implied_vol = vol_metrics.vix
            
            vrp = implied_vol - realized_vol
            
            # ========================================
            # WEIGHTED VRP BY EXPIRY
            # ========================================
            # VRP degrades closer to expiry due to gamma risk
            # Apply DTE-based weighting
            
            def weight_vrp_by_dte(vrp: float, dte: int) -> float:
                """Weight VRP based on days to expiry"""
                if dte <= 0:
                    return 0
                elif dte == 1:
                    return vrp * 0.3  # Gamma week - high risk
                elif dte <= 2:
                    return vrp * 0.5  # Near expiry - elevated risk
                elif dte <= 7:
                    return vrp * 0.8  # Weekly - normal
                else:
                    return vrp * 1.0  # Monthly - full weight
                    
            weighted_vrp_weekly = weight_vrp_by_dte(vrp, weekly_dte)
            weighted_vrp_monthly = weight_vrp_by_dte(vrp, monthly_dte)
            weighted_vrp_next_weekly = weight_vrp_by_dte(vrp, next_weekly_dte)
            
            # ========================================
            # TERM STRUCTURE EDGE
            # ========================================
            # Compare near-term vs far-term implied volatility
            # Contango (upward slope) = normal
            # Backwardation (downward slope) = stress
            
            # Use GARCH forecasts as proxy for term structure
            if vol_metrics.garch7 > 0 and vol_metrics.garch28 > 0:
                # Positive = backwardation (near > far)
                # Negative = contango (far > near)
                term_structure_edge = vol_metrics.garch7 - vol_metrics.garch28
            else:
                term_structure_edge = 0
                
            # ========================================
            # SMART EXPIRY SELECTION
            # ========================================
            # Select optimal expiry based on:
            # - Weighted VRP
            # - DTE constraints
            # - Risk-adjusted returns
            
            expiry_scores = {}
            
            # Weekly score
            if weekly_dte > 0:
                expiry_scores['WEEKLY'] = weighted_vrp_weekly / (weekly_dte + 1)  # Normalize by DTE
                
            # Next weekly score
            if next_weekly_dte > 0:
                expiry_scores['NEXT_WEEKLY'] = weighted_vrp_next_weekly / (next_weekly_dte + 1)
                
            # Monthly score
            if monthly_dte > 0:
                expiry_scores['MONTHLY'] = weighted_vrp_monthly / (monthly_dte + 1)
                
            # Select best expiry
            if expiry_scores:
                smart_expiry_weekly = 'WEEKLY' if 'WEEKLY' in expiry_scores else None
                smart_expiry_monthly = max(expiry_scores, key=expiry_scores.get)
            else:
                smart_expiry_weekly = 'WEEKLY'
                smart_expiry_monthly = 'MONTHLY'
                
            # ========================================
            # CONSTRUCT METRICS OBJECT
            # ========================================
            return EdgeMetrics(
                vrp=vrp,
                weighted_vrp_weekly=weighted_vrp_weekly,
                weighted_vrp_monthly=weighted_vrp_monthly,
                weighted_vrp_next_weekly=weighted_vrp_next_weekly,
                term_structure_edge=term_structure_edge,
                smart_expiry_weekly=smart_expiry_weekly,
                smart_expiry_monthly=smart_expiry_monthly,
                weekly_dte=weekly_dte,
                monthly_dte=monthly_dte
            )
            
        except Exception as e:
            logger.error(f"Edge metrics calculation failed: {e}", exc_info=True)
            return None
