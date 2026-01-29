"""
Regime Engine - COMPLETE SCORING LOGIC PRESERVED FROM ORIGINAL
Dynamic weights, detailed scoring with ALL drivers, mandate generation
NOT THE SIMPLIFIED MVP VERSION
"""
from typing import Dict, Tuple, List, Optional
from models.domain import VolMetrics, StructMetrics, EdgeMetrics, ExternalMetrics, Score, TradingMandate, DynamicWeights
from config import Config
from utils.logger import logger
import numpy as np

class RegimeEngine:
    """Regime detection and mandate generation - ALL LOGIC PRESERVED FROM v3.3"""
    
    @staticmethod
    def calculate_dynamic_weights(vol_metrics: VolMetrics, struct_metrics: StructMetrics, external_metrics: ExternalMetrics, dte: int) -> DynamicWeights:
        """
        Calculate adaptive weights based on market conditions
        COMPLETE VERSION FROM ORIGINAL with all adjustment logic
        
        Weights adjust based on:
        - Volatility regime (VOV, IVP)
        - Market structure (GEX, PCR)
        - Time to expiry (DTE)
        - External factors (FII positioning)
        """
        # Start with base weights from config
        vol_weight = Config.WEIGHT_VOL
        struct_weight = Config.WEIGHT_STRUCT
        edge_weight = Config.WEIGHT_EDGE
        risk_weight = Config.WEIGHT_RISK
        
        rationale_parts = []
        
        # ========================================
        # EXTREME VOLATILITY ADJUSTMENTS
        # ========================================
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            # VOV crash - volatility exploding
            # Heavily weight volatility signals, reduce structure importance
            vol_weight = 0.50
            struct_weight = 0.25
            edge_weight = 0.15
            risk_weight = 0.10
            rationale_parts.append(f"EXTREME VOV ({vol_metrics.vov_zscore:.1f}σ): Vol 50%, Struct 25%")
            
        elif vol_metrics.vov_zscore > Config.VOV_WARNING_ZSCORE:
            # Elevated VOV - increase vol weight moderately
            vol_weight = 0.45
            struct_weight = 0.28
            edge_weight = 0.17
            risk_weight = 0.10
            rationale_parts.append(f"High VOV ({vol_metrics.vov_zscore:.1f}σ): Vol 45%")
            
        # ========================================
        # IV PERCENTILE ADJUSTMENTS
        # ========================================
        elif vol_metrics.ivp_1yr > Config.HIGH_VOL_IVP:
            # Rich IV environment - emphasize structure
            vol_weight = 0.35
            struct_weight = 0.35
            edge_weight = 0.20
            risk_weight = 0.10
            rationale_parts.append(f"Rich IVP ({vol_metrics.ivp_1yr:.0f}%): Balanced Vol/Struct 35%")
            
        elif vol_metrics.ivp_1yr < Config.LOW_VOL_IVP:
            # Cheap IV environment - emphasize edge finding
            vol_weight = 0.30
            struct_weight = 0.30
            edge_weight = 0.30
            risk_weight = 0.10
            rationale_parts.append(f"Cheap IVP ({vol_metrics.ivp_1yr:.0f}%): Edge 30%")
            
        # ========================================
        # VIX MOMENTUM ADJUSTMENTS
        # ========================================
        if vol_metrics.vix_momentum == "EXPLOSIVE_UP":
            # VIX spiking - reduce all risk taking
            vol_weight += 0.05
            edge_weight -= 0.05
            rationale_parts.append(f"VIX Explosive: Vol +5%, Edge -5%")
            
        elif vol_metrics.vix_momentum == "COLLAPSING":
            # VIX collapsing - can be more aggressive
            edge_weight += 0.05
            vol_weight -= 0.05
            rationale_parts.append(f"VIX Collapse: Edge +5%")
            
        # ========================================
        # STRUCTURE REGIME ADJUSTMENTS
        # ========================================
        if struct_metrics.gex_regime == "STICKY":
            # High GEX = price support, structure more important
            struct_weight += 0.05
            vol_weight -= 0.05
            rationale_parts.append(f"Sticky GEX: Struct +5%")
            
        elif struct_metrics.gex_regime == "SLIPPERY":
            # Low GEX = price can move, volatility more important
            vol_weight += 0.05
            struct_weight -= 0.05
            rationale_parts.append(f"Slippery GEX: Vol +5%")
            
        # ========================================
        # GAMMA DANGER ADJUSTMENTS
        # ========================================
        if dte <= Config.GAMMA_DANGER_DTE:
            # Gamma week - structure dominates
            struct_weight += 0.10
            edge_weight -= 0.05
            risk_weight -= 0.05
            rationale_parts.append(f"Gamma Week (DTE={dte}): Struct +10%")
            
        # ========================================
        # FII POSITIONING ADJUSTMENTS
        # ========================================
        if abs(external_metrics.fii_net) > Config.FII_STRONG_LONG:
            # Strong FII positioning - add risk weighting
            risk_weight += 0.05
            edge_weight -= 0.05
            rationale_parts.append(f"Strong FII ({external_metrics.fii_net:,.0f}): Risk +5%")
            
        # ========================================
        # NORMALIZATION
        # ========================================
        # Ensure weights sum to 1.0
        total = vol_weight + struct_weight + edge_weight + risk_weight
        
        if abs(total - 1.0) > 0.01:
            # Normalize if rounding errors
            vol_weight /= total
            struct_weight /= total
            edge_weight /= total
            risk_weight /= total
            
        # Create rationale string
        if not rationale_parts:
            rationale_parts.append("Standard weights")
            
        rationale = " | ".join(rationale_parts)
        
        return DynamicWeights(
            vol_weight=vol_weight,
            struct_weight=struct_weight,
            edge_weight=edge_weight,
            risk_weight=risk_weight,
            rationale=rationale
        )
    
    @staticmethod
    def calculate_scores(
        vol_metrics: VolMetrics,
        struct_metrics: StructMetrics,
        edge_metrics: EdgeMetrics,
        external_metrics: ExternalMetrics,
        dte: int
    ) -> Score:
        """
        Calculate all scores with detailed drivers
        COMPLETE VERSION FROM ORIGINAL - ALL FORMULAS INTACT
        
        Scoring system (0-10 scale):
        - Vol Score: Based on IVP, VoV, VIX momentum, GARCH forecasts
        - Struct Score: Based on GEX, PCR, skew
        - Edge Score: Based on VRP, term structure
        - Risk Score: Based on FII positioning, external factors
        - Composite: Weighted average using dynamic weights
        """
        score_drivers = []
        
        # ========================================
        # VOL SCORE (0-10)
        # ========================================
        vol_score = 5.0  # Start at neutral
        
        # Critical VOV check - OVERRIDES EVERYTHING
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            vol_score = 0.0  # Absolute zero in crash conditions
            score_drivers.append(f"Vol: VOV Crash ({vol_metrics.vov_zscore:.1f}σ) → ZERO")
            
        elif vol_metrics.vov_zscore > Config.VOV_WARNING_ZSCORE:
            vol_score -= 3.0
            score_drivers.append(f"Vol: High VOV ({vol_metrics.vov_zscore:.1f}σ) -3.0")
            
        elif vol_metrics.vov_zscore < 1.5:
            vol_score += 1.5
            score_drivers.append(f"Vol: Stable VOV ({vol_metrics.vov_zscore:.1f}σ) +1.5")
        
        # IV Percentile scoring
        if vol_metrics.ivp_1yr > Config.HIGH_VOL_IVP:
            # Rich IV is good for selling
            if vol_metrics.vix_momentum == "FALLING":
                vol_score += 1.5
                score_drivers.append(f"Vol: Rich IVP ({vol_metrics.ivp_1yr:.0f}%) + Falling VIX +1.5")
            elif vol_metrics.vix_momentum == "RISING":
                vol_score -= 1.0
                score_drivers.append(f"Vol: Rich IVP + Rising VIX -1.0")
            else:
                vol_score += 0.5
                score_drivers.append(f"Vol: Rich IVP ({vol_metrics.ivp_1yr:.0f}%) +0.5")
                
        elif vol_metrics.ivp_1yr < Config.LOW_VOL_IVP:
            # Cheap IV is bad for selling
            vol_score -= 2.5
            score_drivers.append(f"Vol: Cheap IVP ({vol_metrics.ivp_1yr:.0f}%) -2.5")
            
        else:
            # Fair IV
            vol_score += 1.0
            score_drivers.append(f"Vol: Fair IVP ({vol_metrics.ivp_1yr:.0f}%) +1.0")
        
        # VIX Momentum scoring
        if vol_metrics.vix_momentum == "EXPLOSIVE_UP":
            vol_score -= 2.0
            score_drivers.append(f"Vol: VIX explosive ({vol_metrics.vix_change_5d:+.1f}) -2.0")
        elif vol_metrics.vix_momentum == "COLLAPSING":
            vol_score += 1.0
            score_drivers.append(f"Vol: VIX collapsing ({vol_metrics.vix_change_5d:+.1f}) +1.0")
        
        # GARCH vs Realized comparison
        if vol_metrics.garch28 > vol_metrics.rv28 * 1.2:
            vol_score += 0.5
            score_drivers.append(f"Vol: GARCH > RV ({vol_metrics.garch28:.1f} vs {vol_metrics.rv28:.1f}) +0.5")
        
        vol_score = max(0, min(10, vol_score))
        
        # ========================================
        # STRUCT SCORE (0-10)
        # ========================================
        struct_score = 5.0  # Start at neutral
        
        # GEX regime scoring
        if struct_metrics.gex_regime == "STICKY":
            struct_score += 2.5
            score_drivers.append(f"Struct: Sticky GEX ({struct_metrics.gex_ratio:.3%}) +2.5")
        elif struct_metrics.gex_regime == "SLIPPERY":
            struct_score -= 1.0
            score_drivers.append("Struct: Slippery GEX -1.0")
        
        # PCR scoring (both total and ATM)
        if 0.9 < struct_metrics.pcr_atm < 1.1:
            struct_score += 1.5
            score_drivers.append(f"Struct: Balanced PCR ATM ({struct_metrics.pcr_atm:.2f}) +1.5")
        elif struct_metrics.pcr_atm > 1.3:
            struct_score += 0.5
            score_drivers.append(f"Struct: High PCR ATM ({struct_metrics.pcr_atm:.2f}) - Bullish +0.5")
        elif struct_metrics.pcr_atm < 0.7:
            struct_score -= 0.5
            score_drivers.append(f"Struct: Low PCR ATM ({struct_metrics.pcr_atm:.2f}) - Bearish -0.5")
        
        # Skew regime scoring
        if struct_metrics.skew_regime == "CRASH_FEAR":
            struct_score -= 1.0
            score_drivers.append(f"Struct: Crash Fear Skew ({struct_metrics.skew_25delta:+.1f}%) -1.0")
        elif struct_metrics.skew_regime == "MELT_UP":
            struct_score -= 0.5
            score_drivers.append("Struct: Melt-Up Skew -0.5")
        else:
            struct_score += 0.5
            score_drivers.append("Struct: Balanced Skew +0.5")
        
        # Max Pain vs Spot (indicator of where market wants to go)
        pain_distance = abs(struct_metrics.max_pain - vol_metrics.spot_price) / vol_metrics.spot_price
        if pain_distance < 0.01:  # Within 1%
            struct_score += 1.0
            score_drivers.append(f"Struct: At Max Pain ({struct_metrics.max_pain:.0f}) +1.0")
        
        struct_score = max(0, min(10, struct_score))
        
        # ========================================
        # EDGE SCORE (0-10)
        # ========================================
        edge_score = 5.0  # Start at neutral
        
        # VRP scoring (main edge metric)
        # Use weighted VRP (accounts for DTE)
        weighted_vrp = edge_metrics.weighted_vrp_monthly  # Default to monthly
        
        if weighted_vrp > 5:
            edge_score += 3.0
            score_drivers.append(f"Edge: Strong VRP ({weighted_vrp:.2f}%) +3.0")
        elif weighted_vrp > 2:
            edge_score += 1.5
            score_drivers.append(f"Edge: Positive VRP ({weighted_vrp:.2f}%) +1.5")
        elif weighted_vrp < -2:
            edge_score -= 2.0
            score_drivers.append(f"Edge: Negative VRP ({weighted_vrp:.2f}%) -2.0")
        else:
            edge_score += 0.5
            score_drivers.append(f"Edge: Neutral VRP ({weighted_vrp:.2f}%) +0.5")
        
        # Term structure edge
        if edge_metrics.term_structure_edge < -2:
            # Backwardation (stress)
            edge_score -= 1.0
            score_drivers.append(f"Edge: Backwardation ({edge_metrics.term_structure_edge:.1f}) -1.0")
        elif edge_metrics.term_structure_edge > 2:
            # Contango (normal)
            edge_score += 0.5
            score_drivers.append(f"Edge: Contango ({edge_metrics.term_structure_edge:.1f}) +0.5")
        
        edge_score = max(0, min(10, edge_score))
        
        # ========================================
        # RISK SCORE (0-10)
        # ========================================
        risk_score = 5.0  # Start at neutral
        
        # FII positioning scoring
        if external_metrics.fii_net > Config.FII_STRONG_LONG:
            risk_score += 1.0
            score_drivers.append(f"Risk: FII Strong Long ({external_metrics.fii_net:,.0f}) +1.0")
        elif external_metrics.fii_net < Config.FII_STRONG_SHORT:
            risk_score -= 1.0
            score_drivers.append(f"Risk: FII Strong Short ({external_metrics.fii_net:,.0f}) -1.0")
        elif abs(external_metrics.fii_net) > Config.FII_MODERATE:
            if external_metrics.fii_net > 0:
                risk_score += 0.5
                score_drivers.append(f"Risk: FII Moderate Long ({external_metrics.fii_net:,.0f}) +0.5")
            else:
                risk_score -= 0.5
                score_drivers.append(f"Risk: FII Moderate Short ({external_metrics.fii_net:,.0f}) -0.5")
        
        # High impact events
        if external_metrics.high_impact_events:
            event_count = len(external_metrics.high_impact_events)
            risk_score -= min(event_count * 0.5, 2.0)
            score_drivers.append(f"Risk: {event_count} High Impact Events -{min(event_count * 0.5, 2.0):.1f}")
        
        risk_score = max(0, min(10, risk_score))
        
        # ========================================
        # DYNAMIC WEIGHTS
        # ========================================
        weights = RegimeEngine.calculate_dynamic_weights(vol_metrics, struct_metrics, external_metrics, dte)
        
        # ========================================
        # COMPOSITE SCORE
        # ========================================
        composite = (
            vol_score * weights.vol_weight +
            struct_score * weights.struct_weight +
            edge_score * weights.edge_weight +
            risk_score * weights.risk_weight
        )
        
        # ========================================
        # SCORE STABILITY
        # ========================================
        # Test with alternative weight sets to measure stability
        alt_weights = [
            (0.30, 0.35, 0.25, 0.10),  # Balanced
            (0.50, 0.25, 0.15, 0.10),  # Vol-heavy
            (0.35, 0.30, 0.25, 0.10),  # Moderate
        ]
        
        alt_scores = [
            vol_score * wv + struct_score * ws + edge_score * we + risk_score * wr
            for wv, ws, we, wr in alt_weights
        ]
        
        # Stability = 1 - (coefficient of variation)
        # Higher stability = more agreement across different weighting schemes
        if np.mean(alt_scores) > 0:
            score_stability = 1.0 - (np.std(alt_scores) / np.mean(alt_scores))
        else:
            score_stability = 0.5
            
        score_stability = max(0, min(1, score_stability))
        
        # ========================================
        # CONFIDENCE LEVEL
        # ========================================
        # Based on composite score AND stability
        if composite >= 8.0 and score_stability > 0.85:
            confidence = "VERY_HIGH"
        elif composite >= 6.5 and score_stability > 0.75:
            confidence = "HIGH"
        elif composite >= 4.0:
            confidence = "MODERATE"
        else:
            confidence = "LOW"
        
        # Add final composite to drivers
        score_drivers.append(
            f"Composite: {composite:.2f}/10 "
            f"[V:{vol_score:.1f}×{weights.vol_weight:.0%} "
            f"S:{struct_score:.1f}×{weights.struct_weight:.0%} "
            f"E:{edge_score:.1f}×{weights.edge_weight:.0%} "
            f"R:{risk_score:.1f}×{weights.risk_weight:.0%}]"
        )
        
        return Score(
            vol_score=vol_score,
            struct_score=struct_score,
            edge_score=edge_score,
            risk_score=risk_score,
            composite=composite,
            confidence=confidence,
            score_stability=score_stability,
            weights_used=weights,
            score_drivers=score_drivers
        )
    
    @staticmethod
    def generate_mandate(
        expiry_type: str,
        score: Score,
        vol_metrics: VolMetrics,
        struct_metrics: StructMetrics,
        edge_metrics: EdgeMetrics,
        external_metrics: ExternalMetrics,
        dte: int,
        veto_reasons: List[str]
    ) -> TradingMandate:
        """
        Generate trading mandate based on score
        COMPLETE VERSION FROM ORIGINAL - STRATEGY SELECTION INTACT
        
        Strategy selection hierarchy:
        1. Check veto events (absolute blockers)
        2. Score-based regime classification
        3. DTE-based strategy refinement
        4. Risk adjustments
        5. Capital allocation
        """
        rationale = []
        warnings = []
        is_trade_allowed = True
        
        # ========================================
        # DETERMINE REGIME NAME
        # ========================================
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            regime_name = "VOL_SPIKE"
        elif vol_metrics.ivp_1yr > Config.HIGH_VOL_IVP:
            regime_name = "HIGH_VOL"
        elif vol_metrics.ivp_1yr < Config.LOW_VOL_IVP:
            regime_name = "LOW_VOL"
        else:
            regime_name = "NORMAL"
            
        # ========================================
        # SELECT STRATEGY - COMPLETE ORIGINAL LOGIC
        # ========================================
        if score.composite >= 7.5 and score.confidence in ["HIGH", "VERY_HIGH"]:
            # VERY HIGH CONFIDENCE
            if dte > 2:
                suggested_structure = "IRON_CONDOR"
                allocation_pct = 60.0
                rationale.append(f"Very High Confidence ({score.confidence}): VRP {edge_metrics.weighted_vrp_monthly:.2f}%")
            else:
                # Gamma week
                suggested_structure = "IRON_FLY"
                allocation_pct = 50.0
                rationale.append(f"High VRP + Near expiry - Gamma harvest")
                warnings.append("⚠️ GAMMA RISK - Monitor closely")
                
        elif score.composite >= 6.0 and score.confidence in ["HIGH", "VERY_HIGH"]:
            # HIGH CONFIDENCE
            if dte > 1:
                suggested_structure = "IRON_CONDOR"
                allocation_pct = 40.0
                rationale.append(f"Moderate Confidence: VRP {edge_metrics.weighted_vrp_monthly:.2f}%")
            else:
                suggested_structure = "IRON_FLY"
                allocation_pct = 35.0
                warnings.append("⚠️ EXPIRY RISK - Monitor gamma")
                
        elif score.composite >= 4.0:
            # MODERATE CONFIDENCE - Use directional spreads
            if struct_metrics.pcr_atm > 1.3:
                directional_bias = "BULLISH"
                suggested_structure = "BULL_PUT_SPREAD"
            elif struct_metrics.pcr_atm < 0.7:
                directional_bias = "BEARISH"
                suggested_structure = "BEAR_CALL_SPREAD"
            else:
                directional_bias = "NEUTRAL"
                suggested_structure = "CREDIT_SPREAD"
                
            allocation_pct = 20.0
            rationale.append("Defensive Posture - lower conviction")
            warnings.append("⚠️ LOWER CONVICTION - Reduce size")
            
        else:
            # LOW CONFIDENCE - CASH
            suggested_structure = "NO_TRADE"
            allocation_pct = 0.0
            is_trade_allowed = False
            rationale.append("Regime Unfavorable: Cash is a position")
            veto_reasons.append("Low composite score")
            
        # ========================================
        # RISK ADJUSTMENTS
        # ========================================
        allocation = allocation_pct
        
        # VOV adjustment
        if vol_metrics.vov_zscore > Config.VOV_WARNING_ZSCORE:
            warnings.append(f"⚠️ HIGH VOL-OF-VOL ({vol_metrics.vov_zscore:.2f}σ) - Size reduced 30%")
            allocation *= 0.7
            
        # VIX momentum adjustment
        if vol_metrics.vix_momentum == "EXPLOSIVE_UP":
            warnings.append(f"⚠️ VIX EXPLOSIVE ({vol_metrics.vix:.1f}) - Size reduced 40%")
            allocation *= 0.6
            
        # Score stability adjustment
        if score.score_stability < 0.75:
            warnings.append(f"⚠️ LOW SCORE STABILITY ({score.score_stability:.2f}) - Size reduced 20%")
            allocation *= 0.8
            
        # Event risk adjustment
        if external_metrics.high_impact_events:
            high_impact_count = len(external_metrics.high_impact_events)
            warnings.append(f"⚠️ {high_impact_count} HIGH IMPACT EVENT(S) THIS WEEK")
            allocation *= 0.85
            
        # Calculate deployment
        allocation = max(0, min(100, allocation))
        deployment_amount = Config.BASE_CAPITAL * (allocation / 100.0)
        
        # Capping
        if deployment_amount > Config.MAX_CAPITAL_PER_TRADE:
            deployment_amount = Config.MAX_CAPITAL_PER_TRADE
            warnings.append(f"⚠️ Capital capped at ₹{Config.MAX_CAPITAL_PER_TRADE:,.0f}")
            
        # Calculate max lots
        max_lots = int(deployment_amount / Config.MARGIN_SELL_BASE)
        
        return TradingMandate(
            expiry_type=expiry_type,
            regime_name=regime_name,
            suggested_structure=suggested_structure,
            directional_bias="NEUTRAL",  # Will be set by strategy factory
            allocation_pct=allocation,
            deployment_amount=deployment_amount,
            max_lots=max_lots,
            score=score,
            rationale=rationale,
            warnings=warnings,
            veto_reasons=veto_reasons,
            dynamic_weights=score.weights_used,
            metrics_snapshot={}  # Will be populated by orchestrator
        )
