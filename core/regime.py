"""
Regime Engine - COMPLETE SCORING LOGIC PRESERVED
Dynamic weights, scoring, mandate generation
"""
from typing import Dict, Tuple, List, Optional
from models.domain import VolMetrics, StructMetrics, EdgeMetrics, ExternalMetrics, Score, TradingMandate
from config import Config
from utils.logger import logger
import numpy as np

class RegimeEngine:
    """Regime detection and mandate generation - ALL LOGIC PRESERVED"""
    
    @staticmethod
    def calculate_dynamic_weights(vol_metrics: VolMetrics, struct_metrics: StructMetrics) -> Dict[str, float]:
        """
        Calculate adaptive weights based on market conditions
        PRESERVED FROM ORIGINAL
        """
        base_weights = {
            'vol': Config.WEIGHT_VOL,
            'struct': Config.WEIGHT_STRUCT,
            'edge': Config.WEIGHT_EDGE,
            'risk': Config.WEIGHT_RISK
        }
        
        # Extreme volatility → increase vol weight
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            base_weights['vol'] = 0.50
            base_weights['struct'] = 0.25
            base_weights['edge'] = 0.15
            base_weights['risk'] = 0.10
        
        # Low vol environment → emphasize edge
        elif vol_metrics.iv_percentile < Config.LOW_VOL_IVP:
            base_weights['vol'] = 0.30
            base_weights['struct'] = 0.30
            base_weights['edge'] = 0.30
            base_weights['risk'] = 0.10
        
        # High vol → emphasize structure
        elif vol_metrics.iv_percentile > Config.HIGH_VOL_IVP:
            base_weights['vol'] = 0.45
            base_weights['struct'] = 0.35
            base_weights['edge'] = 0.10
            base_weights['risk'] = 0.10
        
        return base_weights
    
    @staticmethod
    def calculate_scores(
        vol_metrics: VolMetrics,
        struct_metrics: StructMetrics,
        edge_metrics: EdgeMetrics,
        external_metrics: ExternalMetrics
    ) -> Score:
        """
        Calculate all scores with detailed drivers
        PRESERVED FROM ORIGINAL - ALL FORMULAS INTACT
        """
        vol_drivers = []
        struct_drivers = []
        edge_drivers = []
        risk_factors = []
        
        # ===== VOL SCORE (0-100) =====
        vol_score = 50.0  # Base
        
        # IVP contribution
        if vol_metrics.iv_percentile > 75:
            vol_score += 20
            vol_drivers.append(f"High IVP ({vol_metrics.iv_percentile:.0f})")
        elif vol_metrics.iv_percentile > 50:
            vol_score += 10
            vol_drivers.append(f"Elevated IVP ({vol_metrics.iv_percentile:.0f})")
        elif vol_metrics.iv_percentile < 25:
            vol_score -= 15
            vol_drivers.append(f"Low IVP ({vol_metrics.iv_percentile:.0f})")
        
        # VoV contribution
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            vol_score -= 25
            vol_drivers.append(f"Extreme VoV ({vol_metrics.vov_zscore:.1f}σ)")
        elif vol_metrics.vov_zscore > Config.VOV_WARNING_ZSCORE:
            vol_score -= 10
            vol_drivers.append(f"Elevated VoV ({vol_metrics.vov_zscore:.1f}σ)")
        
        # VIX momentum
        if vol_metrics.vix_momentum and abs(vol_metrics.vix_momentum) > Config.VIX_MOMENTUM_BREAKOUT:
            if vol_metrics.vix_momentum > 0:
                vol_score -= 15
                vol_drivers.append(f"VIX surging (+{vol_metrics.vix_momentum:.1f}%)")
            else:
                vol_score += 10
                vol_drivers.append(f"VIX declining ({vol_metrics.vix_momentum:.1f}%)")
        
        vol_score = max(0, min(100, vol_score))
        
        # ===== STRUCT SCORE (0-100) =====
        struct_score = 50.0
        
        # PCR contribution
        if struct_metrics.put_call_ratio > 1.5:
            struct_score += 15
            struct_drivers.append(f"High PCR ({struct_metrics.put_call_ratio:.2f})")
        elif struct_metrics.put_call_ratio < 0.7:
            struct_score -= 10
            struct_drivers.append(f"Low PCR ({struct_metrics.put_call_ratio:.2f})")
        
        struct_score = max(0, min(100, struct_score))
        
        # ===== EDGE SCORE (0-100) =====
        edge_score = 50.0
        
        # VRP contribution
        if edge_metrics.vrp > 5:
            edge_score += 20
            edge_drivers.append(f"Strong VRP ({edge_metrics.vrp:.1f})")
        elif edge_metrics.vrp > 2:
            edge_score += 10
            edge_drivers.append(f"Positive VRP ({edge_metrics.vrp:.1f})")
        elif edge_metrics.vrp < -2:
            edge_score -= 15
            edge_drivers.append(f"Negative VRP ({edge_metrics.vrp:.1f})")
        
        edge_score = max(0, min(100, edge_score))
        
        # ===== RISK SCORE (0-100) =====
        risk_score = 50.0
        
        # FII position (informational)
        if external_metrics.fii_net > Config.FII_STRONG_LONG:
            risk_score += 10
            risk_factors.append(f"FII Long ({external_metrics.fii_net:,.0f})")
        elif external_metrics.fii_net < Config.FII_STRONG_SHORT:
            risk_score -= 10
            risk_factors.append(f"FII Short ({external_metrics.fii_net:,.0f})")
        
        risk_score = max(0, min(100, risk_score))
        
        # ===== COMPOSITE SCORE =====
        weights = RegimeEngine.calculate_dynamic_weights(vol_metrics, struct_metrics)
        composite = (
            vol_score * weights['vol'] +
            struct_score * weights['struct'] +
            edge_score * weights['edge'] +
            risk_score * weights['risk']
        )
        
        # Confidence
        score_variance = np.std([vol_score, struct_score, edge_score, risk_score])
        if score_variance < 10:
            confidence = "HIGH"
        elif score_variance < 20:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        return Score(
            vol_score=vol_score,
            struct_score=struct_score,
            edge_score=edge_score,
            risk_score=risk_score,
            composite=composite,
            confidence=confidence,
            score_stability=100 - score_variance,
            vol_drivers=vol_drivers,
            struct_drivers=struct_drivers,
            edge_drivers=edge_drivers,
            risk_factors=risk_factors
        )
    
    @staticmethod
    def generate_mandate(
        expiry_type: str,
        score: Score,
        vol_metrics: VolMetrics,
        veto_reasons: List[str],
        dynamic_weights: Dict[str, float]
    ) -> TradingMandate:
        """
        Generate trading mandate based on score
        PRESERVED FROM ORIGINAL - STRATEGY SELECTION INTACT
        """
        # Determine regime
        if vol_metrics.vov_zscore > Config.VOV_CRASH_ZSCORE:
            regime_name = "VOL_SPIKE"
        elif vol_metrics.iv_percentile > Config.HIGH_VOL_IVP:
            regime_name = "HIGH_VOL"
        elif vol_metrics.iv_percentile < Config.LOW_VOL_IVP:
            regime_name = "LOW_VOL"
        else:
            regime_name = "NORMAL"
        
        # Select strategy - PRESERVED LOGIC
        if score.composite >= 75:
            suggested_structure = "IRON_FLY"
            allocation_pct = 25.0
        elif score.composite >= 60:
            suggested_structure = "IRON_CONDOR"
            allocation_pct = 20.0
        elif score.composite >= 50:
            suggested_structure = "CREDIT_SPREAD"
            allocation_pct = 15.0
        else:
            suggested_structure = "NO_TRADE"
            allocation_pct = 0.0
        
        # Directional bias
        if vol_metrics.vix_momentum and vol_metrics.vix_momentum > 3:
            directional_bias = "BEARISH"
        elif vol_metrics.vix_momentum and vol_metrics.vix_momentum < -3:
            directional_bias = "BULLISH"
        else:
            directional_bias = "NEUTRAL"
        
        # Capital allocation
        deployment_amount = Config.BASE_CAPITAL * (allocation_pct / 100)
        max_lots = int(deployment_amount / Config.MARGIN_SELL_BASE)
        
        # Rationale
        rationale = [
            f"Regime: {regime_name}",
            f"Composite Score: {score.composite:.1f}/100",
            f"Vol Score: {score.vol_score:.0f} ({', '.join(score.vol_drivers) if score.vol_drivers else 'neutral'})",
            f"Allocation: {allocation_pct:.0f}% (₹{deployment_amount:,.0f})"
        ]
        
        # Warnings
        warnings = []
        if score.confidence == "LOW":
            warnings.append("Low confidence - conflicting signals")
        if vol_metrics.vov_zscore > Config.VOV_WARNING_ZSCORE:
            warnings.append("Elevated volatility of volatility")
        
        return TradingMandate(
            expiry_type=expiry_type,
            regime_name=regime_name,
            suggested_structure=suggested_structure,
            directional_bias=directional_bias,
            allocation_pct=allocation_pct,
            deployment_amount=deployment_amount,
            max_lots=max_lots,
            score=score,
            rationale=rationale,
            warnings=warnings,
            veto_reasons=veto_reasons,
            dynamic_weights=dynamic_weights,
            metrics_snapshot={}
        )
